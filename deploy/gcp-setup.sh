#!/usr/bin/env bash
# Yattalog を Cloud Run で動かすための Google Cloud の初期設定（決定 033）。
# Cloud Shell（https://shell.cloud.google.com）で実行する想定。何度実行しても壊れないように書いてある。
#
#   bash deploy/gcp-setup.sh <PROJECT_ID>
#
# 実行の途中で、Neon の接続文字列と Google OAuth のクライアントシークレットを聞かれる（画面には表示されない）。
set -euo pipefail

PROJECT_ID="${1:?使い方: bash deploy/gcp-setup.sh <PROJECT_ID>}"
REGION="asia-southeast1"           # Neon（AWS シンガポール）の近く
GITHUB_REPO="ikura1/yattalog"
POOL="github"
PROVIDER="yattalog-repo"
RUNTIME_SA="yattalog-run"
DEPLOY_SA="yattalog-deploy"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

gcloud config set project "$PROJECT_ID" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

say "API を有効にする"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com iam.googleapis.com

say "コンテナの置き場所（Artifact Registry）"
gcloud artifacts repositories describe yattalog --location "$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create yattalog --repository-format docker --location "$REGION" \
    --description "Yattalog のコンテナイメージ"
# 無料枠（0.5GB）に収まるよう、新しい5つだけを残す（1日より古いものが削除の対象。"0s" は条件なしとみなされて弾かれる）
cat > /tmp/yattalog-cleanup.json <<'JSON'
[{"name":"keep-recent","action":{"type":"Keep"},"mostRecentVersions":{"keepCount":5}},
 {"name":"delete-old","action":{"type":"Delete"},"condition":{"tagState":"ANY","olderThan":"1d"}}]
JSON
gcloud artifacts repositories set-cleanup-policies yattalog --location "$REGION" \
  --policy /tmp/yattalog-cleanup.json --no-dry-run >/dev/null

say "サービスアカウント"
for sa in "$RUNTIME_SA" "$DEPLOY_SA"; do
  gcloud iam service-accounts describe "$sa@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1 || \
    gcloud iam service-accounts create "$sa" --display-name "$sa"
done
RUNTIME_EMAIL="$RUNTIME_SA@$PROJECT_ID.iam.gserviceaccount.com"
DEPLOY_EMAIL="$DEPLOY_SA@$PROJECT_ID.iam.gserviceaccount.com"
for role in roles/run.admin roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$DEPLOY_EMAIL" --role "$role" --condition None >/dev/null
done
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_EMAIL" \
  --member "serviceAccount:$DEPLOY_EMAIL" --role roles/iam.serviceAccountUser >/dev/null

say "秘密の値（Secret Manager）"
put_secret() {  # $1=名前 $2=値
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    printf '%s' "$2" | gcloud secrets versions add "$1" --data-file=- >/dev/null
  else
    printf '%s' "$2" | gcloud secrets create "$1" --replication-policy automatic --data-file=- >/dev/null
  fi
  gcloud secrets add-iam-policy-binding "$1" --member "serviceAccount:$RUNTIME_EMAIL" \
    --role roles/secretmanager.secretAccessor >/dev/null
}
gcloud secrets describe django-secret-key >/dev/null 2>&1 || put_secret django-secret-key "$(openssl rand -base64 48)"
gcloud secrets describe django-admin-url >/dev/null 2>&1 || put_secret django-admin-url "manage-$(openssl rand -hex 8)"
if ! gcloud secrets describe database-url >/dev/null 2>&1; then
  read -rsp "Neon の接続文字列（Pooled connection、postgresql://... ?sslmode=require）: " DBURL; echo
  put_secret database-url "$DBURL"
fi
if ! gcloud secrets describe google-client-secret >/dev/null 2>&1; then
  echo "Google OAuth のリダイレクト URI: https://yattalog-$PROJECT_NUMBER.$REGION.run.app/accounts/google/login/callback/"
  read -rsp "Google OAuth のクライアントシークレット（まだなら空のまま Enter。あとでこのスクリプトをもう一度流す）: " GSECRET; echo
  if [ -n "$GSECRET" ]; then put_secret google-client-secret "$GSECRET"; else MISSING_GSECRET=1; fi
fi

say "GitHub Actions からのキーなし認証（Workload Identity 連携）"
gcloud iam workload-identity-pools describe "$POOL" --location global >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create "$POOL" --location global --display-name "GitHub Actions"
gcloud iam workload-identity-pools providers describe "$PROVIDER" --location global --workload-identity-pool "$POOL" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --location global --workload-identity-pool "$POOL" \
    --display-name "ikura1/yattalog" --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition "assertion.repository == '$GITHUB_REPO' && assertion.ref == 'refs/heads/main'"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_EMAIL" --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/attribute.repository/$GITHUB_REPO" >/dev/null

HOST="yattalog-$PROJECT_NUMBER.$REGION.run.app"
say "完了。GitHub の Settings → Secrets and variables → Actions → Variables に次を登録してください"
cat <<OUT
  GCP_PROJECT_ID        = $PROJECT_ID
  GCP_WIF_PROVIDER      = projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER
  GCP_DEPLOY_SA         = $DEPLOY_EMAIL
  GCP_RUNTIME_SA        = $RUNTIME_EMAIL
  DJANGO_ALLOWED_HOSTS  = $HOST
  GOOGLE_CLIENT_ID      = （OAuth クライアント ID）

Google OAuth クライアントの「承認済みのリダイレクト URI」:
  https://$HOST/accounts/google/login/callback/
OUT
if [ -n "${MISSING_GSECRET:-}" ]; then
  echo "⚠ Google OAuth のクライアントシークレットが未登録です。OAuth クライアントを作ってから、もう一度このスクリプトを流してください（作成済みのものはそのまま使われます）"
fi
