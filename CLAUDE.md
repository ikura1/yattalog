# Yattalog — Claude 向けメモ

「前にやったのいつだっけ？」を1タップで記録するアプリ。個人開発、一般公開予定。会話・コメント・コミットメッセージは**日本語**。

## まず読むもの
- `SPEC.md` — 仕様（正）。仕様を変えるときはここと決定記録を一緒に直す
- `docs/decisions/NNN-*.md` — 決定記録（ADR）。新しい判断は次の番号で追加し、`docs/decisions/README.md` の索引も更新
- `docs/data-model.md` — データモデル
- 未決事項・レビュー指摘は GitHub Issues（ラベル `area:*` / `priority:*` / `review`）

## 構成
- Django 6.1 + Python 3.14、uv で管理。画面は Django テンプレート + htmx（`static/vendor/` に同梱）
- **処理はサービス層** `apps/events/services/` に置く。ビュー（`apps/web/views.py`）と将来の API はサービスを呼ぶだけ（決定 027）
- 他人のデータは**サービス層で** `DoesNotExist` にし、ビューは `@owned_or_404` で 404 にする
- 記録の ID は端末で作る UUID（冪等・楽観的更新、決定 028）。`local_date` は記録時点の日付で固定（決定 026）
- 並び順は分数インデックス（`services/sortkeys.py`）。列は `SortKeyField`（PostgreSQL では "C" 照合。外すと順序が壊れる）

## コマンド
```sh
export DJANGO_DEBUG=1
uv run pytest                     # 単体・結合（E2E は除外される）
uv run pytest -m e2e              # Playwright の E2E（初回は uv run playwright install chromium）
uv run ruff check . && uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
```
- 本番と同じ PostgreSQL で回すなら `docker compose up -d` して `DATABASE_URL=postgres://yattalog:yattalog@localhost:5432/yattalog`
- CI（`.github/workflows/ci.yml`）：lint、マイグレーション検査、PostgreSQL 17 でのテスト、`check --deploy`、E2E、Docker ビルド

## 進め方
- **テストを先に書き、落ちることを確かめてから直す**（t_wada 流の TDD）。テスト名は日本語で振る舞いを書く
- テストの時計は `conftest.py` で `2026-10-10 03:00 UTC` に固定（E2E は固定しない）。共通の値・`new_user` は `apps/core/testing.py`
- PR を作って CI が通ってから main へ。main に入ると Cloud Run へ自動デプロイ（GCP の Variables 未登録の間はスキップ）

## ハマりどころ
- Python 3.14：`ruff format` が `except (A, B):` を `except A, B:` に書き換える（3.14 では正しい構文）
- インラインスクリプトは CSP で禁止。JS は `static/js/app.js` に書く
- `HX-Trigger` に日本語を入れるときは `json.dumps`（ASCII エスケープ）を使う
- Neon はプール接続なので `DISABLE_SERVER_SIDE_CURSORS=True`

## 現状（2026-10-11）
- α の土台は main にマージ済み（PR #37）。デプロイ（Cloud Run シンガポール + Neon）は `deploy/README.md` の初回設定待ち
- 次の候補：デプロイ後の動作確認、Issues の `priority:medium` から順に。リリース計画は `SPEC.md` 7章（α → β → v1 → v1.x）
- PoC（`poc/index.html`）は仕様確認用。本体とは別物
