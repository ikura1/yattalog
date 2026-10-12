# Yattalog — Claude 向けメモ

「前にやったのいつだっけ？」を1タップで記録するアプリ。個人開発、一般公開予定。会話・コメント・コミットメッセージは**日本語**。

## まず読むもの
- `docs/handoff.md` — これまでの経緯・現状・次にやること（引き継ぎ資料）
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
- タイルの経過時間は `services/dates.py` の `elapsed()`。今日の記録は「さっき」「N時間」、それ以外は暦日（決定 034）
- アイコンとカテゴリの絵文字は「絵文字1つ」。判定は `services/events.py` の `is_single_emoji()`（`regex` を使用、決定 035・036）
- データの書き出しは `services/export.py`。その場で ZIP を作って返す（写真が入るまで、決定 039）
- 退会は `apps/accounts/services.py` の `delete_account()`。その場で全データを消す（写真が入るまで、決定 040）
- 規約とポリシーの本文は `templates/web/legal/`（変えるときの手順は `docs/legal/README.md`、決定 041）
- はじめて使う人向けのテンプレートは `services/starter.py`。イベントが0個のホームに一覧を出す（決定 042）
- アイコンの元データは `static/icons/*.svg`。PNG は `uv run python tools/build_icons.py` で作り直す（決定 043）
- 管理画面の入口は `apps/accounts/admin_site.py`（メールアドレスの許可と2段階認証、決定 045）。手順は `deploy/README.md`
- レート制限は `apps/core/ratelimit.py` のミドルウェア。上限は `settings.RATE_LIMITS`、回数はプロセス内に持つ（決定 037）

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
- PR を作って CI が通ってから main へ。main に入ると Cloud Run へ自動デプロイ（2〜3分）
  - main は保護されている（PR 必須、CI の `test`・`e2e`・`docker` が必須、直接の push は不可）
  - **マージは Yuki さんが行う**（Claude からの `gh pr merge` は権限で止められる）。マージ後は、Deploy の成功と新しいリビジョンを確認して報告する
- 見た目や操作に関わる変更は、ブラウザで実際に表示して確かめる（E2E のフィクスチャでスクリーンショットを撮るのが手早い）。必要なら触れる PoC を出す
- Dependabot が週1回、更新の PR を作る。Actions はコミット ID で固定しているので、更新はその PR で取り込む

## ハマりどころ
- Python 3.14：`ruff format` が `except (A, B):` を `except A, B:` に書き換える（3.14 では正しい構文）
- インラインスクリプトは CSP で禁止。JS は `static/js/app.js` に書く
- `HX-Trigger` に日本語を入れるときは `json.dumps`（ASCII エスケープ）を使う
- Neon はプール接続なので `DISABLE_SERVER_SIDE_CURSORS=True`
- allauth：`User` に username 欄がないので `ACCOUNT_USER_MODEL_USERNAME_FIELD = None` が必要（外すとログイン完了時に 500）
- E2E は `force_login` でログインするので、Google ログインの流れは通らない。ログインまわりは `apps/accounts/tests/test_google_login.py` で確かめる
- 通常のテスト用クライアントは CSRF の検査を省く。確かめるときは `Client(enforce_csrf_checks=True)`
- この開発機（Ubuntu 20.04）は Playwright の対応外。ブラウザの取得と E2E の実行には `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu22.04-x64` を付ける
- 手元（SQLite）の E2E は `database table is locked` でときどき落ちる（#52）。CI では落ちない。落ちたら流し直して見分ける
- レート制限の回数はキャッシュに残る。テストでは `conftest.py` の `empty_cache` が毎回消している
- 秘密の値を端末で貼り付けるとき（`read -rs`）は画面に出ないので、二重に貼りやすい。登録したら長さと形だけを確かめる（値は表示しない）

## 現状（2026-10-12）
- **α は本番で動いている**：https://yattalog-332057063162.asia-southeast1.run.app （Cloud Run シンガポール + Neon、Google Cloud のプロジェクトは `yattalog-511302`）
  - ログインできるのは、OAuth のテストユーザー（いまは Yuki さんだけ）
- 経緯・やり残し・次の候補は `docs/handoff.md`。リリース計画は `SPEC.md` 7章（α → β → v1 → v1.x）
- PoC（`poc/index.html`）は仕様確認用。本体とは別物
