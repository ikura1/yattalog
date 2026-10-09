# 005. デプロイ先は Render と Cloudflare R2

- 日付：2026-10-10
- 状態：決定

## 背景
旧版は GAE、Cloud SQL、GCS の構成だった。設定が多く、個人開発では重かった。
デプロイ先の選定は Claude に任された。

## 決定
- アプリと DB：**Render**（Web Service と Render Postgres）
- 画像：**Cloudflare R2**（S3 互換 API。django-storages の S3 バックエンドで扱う）
- 構成はリポジトリの `render.yaml`（Blueprint）でコード管理する

## 理由
- git push だけでデプロイでき、プレビュー環境も作れる
- Web、DB、環境変数を1ファイルで宣言できるので、構成の再現と見直しがしやすい
- R2 は転送料（egress）が無料なので、画像を配信してもコストが読みやすい
- どちらも小さく始められ、規模に合わせて有料プランに上げられる

## 影響・トレードオフ
- 最初の連携（Render と GitHub の接続、R2 のバケットと API キーの作成）は、オーナーのアカウントで手作業が必要
- Render の無料 Web Service はアクセスがないとスリープするため、公開時は有料の Starter 以上を想定する
- 後で Fly.io や Cloud Run に移す場合も、Docker 化しておけば移行は難しくない
