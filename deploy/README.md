# デプロイ（Cloud Run ＋ Neon、決定 033）

試験運用（α・β）の構成。月額はほぼ0円（無料枠の範囲）。

```
スマホ ──HTTPS──▶ Cloud Run（シンガポール、使われていないときは0台）──▶ Neon PostgreSQL（AWS シンガポール、無料プラン）
                     ▲
GitHub（main に入る）──▶ GitHub Actions：イメージを作る → マイグレーション → デプロイ
```

## 初回だけやること

### 1. Neon
1. https://neon.com で無料アカウントを作り、プロジェクトを作る（リージョン：**AWS Asia Pacific (Singapore)**）
2. 「Connection string」で **Pooled connection** を選び、接続文字列（`postgresql://...-pooler...?sslmode=require`）を控える

### 2. Google Cloud のプロジェクト
1. 新しいプロジェクトを作り、請求先アカウントを紐づける（無料枠内でも必要）
2. **予算アラート**を設定する（例：月 ¥500 で通知）。「お支払い → 予算とアラート」
3. ダッシュボードの「プロジェクト番号」（数字）を控える

### 3. Google ログイン用の OAuth クライアント
1. 「API とサービス → OAuth 同意画面」を設定する（ユーザーの種類：外部、公開ステータス：テスト中。テストユーザーに自分のアドレスを追加）
2. 「認証情報 → 認証情報を作成 → OAuth クライアント ID」（種類：ウェブ アプリケーション）
3. 承認済みのリダイレクト URI に次を入れる（`<プロジェクト番号>` は 2-3. で控えた数字）
   ```
   https://yattalog-<プロジェクト番号>.asia-southeast1.run.app/accounts/google/login/callback/
   ```
4. 表示された**クライアント ID** と**クライアントシークレット**を控える

### 4. 初期設定のスクリプト
Cloud Shell（コンソール右上の `>_`）で流す。途中で Neon の接続文字列と、3. のクライアントシークレットを聞かれる。
```sh
git clone https://github.com/ikura1/yattalog && cd yattalog
bash deploy/gcp-setup.sh <PROJECT_ID>
```
何度流しても大丈夫（作成済みのものはそのまま使う）。

### 5. GitHub
`gcp-setup.sh` の最後に表示された値（`GOOGLE_CLIENT_ID` は 3. で控えたもの）を、リポジトリの **Settings → Secrets and variables → Actions → Variables** に登録する。
登録したら Actions の「Deploy」を手動で実行する（以後は main にマージするたびに自動でデプロイされる）。

## 監視
死活監視・毎朝の報告・Error Reporting の通知。設定と、Claude への頼み方は `docs/operations.md`（決定 041）。

## 費用を抑えるための設定
- Cloud Run：最小0台・最大2台、リクエストを処理している間だけ課金
- Artifact Registry：イメージは新しい5つだけを残す（無料枠0.5GBに収める）
- Neon：無料プラン（1GB、5分使わないと休止）

## 将来
- 写真（β）：Cloudflare R2（決定 005・024）
- 利用者が増えて待ち時間が気になったら：Cloud Run の最小インスタンスを1にする、または Render などの常時起動に移す
