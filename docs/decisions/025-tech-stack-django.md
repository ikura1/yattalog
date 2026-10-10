# 025. サーバーは Django（＋ Django Ninja）で作る

- 日付：2026-10-10
- 状態：決定

## 背景
Python の Web フレームワークでは、FastAPI の利用が伸びている（JetBrains の調査、2024年の利用データで FastAPI 38%、Django 35%、Flask 34%）。
Django と FastAPI のどちらで作るかを比べた。

## 決定
- サーバーは **Django 6.x** で作る
- API（019）は **Django Ninja** で書く。型ヒントで書けて、OpenAPI のドキュメントも自動で出る
- 画面は Django テンプレート ＋ htmx ＋ template partials（Django 6.0 の新機能）で作る
- 主なライブラリ
  - Google ログイン：django-allauth
  - バックグラウンド処理（書き出し・退会時の削除）：Django 6.0 の Tasks フレームワーク＋ワーカー
  - MCP 用の OAuth 2.1（v1.x）：django-oauth-toolkit
  - 写真の保存：django-storages（S3 互換で R2 に保存する）
- MCP サーバー（v1.x）は、公式の Python SDK（ASGI）を Django の ASGI アプリと一緒に動かす

## 理由
- 今回の仕様で必要なもの（Google ログイン、管理画面、マイグレーション、バックグラウンド処理、OAuth）が、Django では本体か定番のライブラリでそろう
- FastAPI では、DB・認証・管理画面などを自分で選んで組み合わせる手間が増える
- Django Ninja を使えば、API 部分は FastAPI と同じような書き方ができる

## 影響・トレードオフ
- Django は FastAPI に比べると、非同期処理への対応がまだ部分的。ただし、この規模のアプリで問題になることはない
- Tasks フレームワークにはワーカーが含まれないので、実行用のバックエンド（django-tasks のデータベースバックエンドなど）を選ぶ必要がある（ステップ6で決める）
