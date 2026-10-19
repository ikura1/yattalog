# Yattalog — Claude 向けメモ

「前にやったのいつだっけ？」を1タップで記録するアプリ。個人開発、一般公開予定。会話・コメント・コミットメッセージは**日本語**。

## まず読むもの
- `docs/handoff.md` — これまでの経緯・現状・次にやること（引き継ぎ資料）
- `SPEC.md` — 仕様（正）。仕様を変えるときはここと決定記録を一緒に直す
- `docs/decisions/NNN-*.md` — 決定記録（ADR）。新しい判断は次の番号で追加し、`docs/decisions/README.md` の索引も更新
- `docs/data-model.md` — データモデル
- `docs/wording.md` — 画面に出す文言の型と一覧。文言を足す・直すときに合わせる
- 未決事項・レビュー指摘は GitHub Issues（ラベル `area:*` / `priority:*` / `review`）

## 構成
- Django 6.1 + Python 3.14、uv で管理。画面は Django テンプレート + htmx（`static/vendor/` に同梱）
- **処理はサービス層** `apps/events/services/`・`apps/accounts/services.py` に置く。ビュー（`apps/web/views/`、機能ごとにファイルを分けている）と将来の API はサービスを呼ぶだけ（決定 027）。ビューから DB を直接読まない（一覧も `list_events()` などを通す）
- 他人のデータは**サービス層で** `DoesNotExist` にし、ビューは `@owned_or_404` で 404 にする
- 記録の ID は端末で作る UUID（冪等・楽観的更新、決定 028）。`local_date` は記録時点の日付で固定（決定 026）
- 並び順は分数インデックス（`services/sortkeys.py`）。列は `SortKeyField`（PostgreSQL では "C" 照合。外すと順序が壊れる）
- タイルの経過時間は `services/dates.py` の `elapsed()`。今日の記録は「さっき」「N時間」、それ以外は暦日（決定 034）
- アイコンとカテゴリの絵文字は「絵文字1つ」。判定は `services/events.py` の `is_single_emoji()`（`regex` を使用、決定 035・036）
- データの書き出しは `services/export.py`。その場で ZIP を作って返す（写真が入るまで、決定 039）
- 退会は `apps/accounts/services.py` の `delete_account()`。その場で全データを消す（写真が入るまで、決定 040）
- 規約とポリシーの本文は `templates/web/legal/`（変えるときの手順は `docs/legal/README.md`、決定 041）
- 主な対象は**独身・一人暮らしの20〜30代**（決定 065）。はじめて使う人向けのテンプレートは `services/starter.py`（5つの組）。イベントが0個のホームに一覧を出す（決定 042）
- アイコンの絵文字は、名前から `services/emoji_hints.py` の辞書で候補を出す（同じ辞書を app.js にも渡す、決定 065）
- アイコンの元データは `static/icons/*.svg`。絵は 057 のスタンプ風で、SVG は `uv run python tools/draw_icons.py` で書き出す。PNG は `uv run python tools/build_icons.py` で作り直す（決定 043）。リンクのプレビュー用の画像（`og.png`）の元は `tools/og.html`
- 管理画面の入口は `apps/accounts/admin_site.py`（メールアドレスの許可と2段階認証、決定 045）。手順は `deploy/README.md`
- アクセス解析は Umami Cloud。ログイン前の画面だけで、`UMAMI_WEBSITE_ID` があるときに読み込む（`templates/web/_analytics.html`、決定 047）
- Service Worker は `templates/web/sw.js`（`/sw.js`）。しまうのは静的ファイルとオフラインの案内だけ。ログインした人の画面はしまわない（決定 049）
- 利用状況の集計は `apps/accounts/usage.py`（人数と件数だけ。管理画面の「利用状況」に出す、決定 051）。費用の上限は月 1,000円（決定 052）
- ふりかえり（1年の草）は `services/review.py` と `presenters.year_months()`。濃さは、その日にやったイベントの種類の数（決定 058）
- イベント詳細の「そのイベントのくせ」（よくやる曜日・時間帯・日にち）は `services/stats.py` の `weekday_tendency()` などで、見出しは `_tendency()` で共通（決定 060）
- 実績バッジは `services/achievements.py`（定義と判定）。記録・編集・イベントの追加のあとに `check()` を呼び、知らせに添える。機能より前からの人は `User.achievements_synced=False` で、最初の判定で静かに解除（決定 063）
- シェアは、見出しと投稿文を `services/share.py` が決め、画像は `app.js` の `drawShareCard()` が端末の Canvas で作る（サーバーには送らない、決定 053）
- レート制限は `apps/core/ratelimit.py` のミドルウェア。上限は `settings.RATE_LIMITS`、回数はプロセス内に持つ（決定 037）
- 監視と運用は `docs/operations.md`（決定 046）。Claude は Google Cloud に入れないので、Actions の「Ops report」を手動で実行してサマリーと Issue（ラベル `ops`）を読む。報告は `apps/core/ops_report.py` で伏せる（リポジトリは公開）
- 本番のログは1行1件の JSON（`apps/core/logging.py`）。`/health` は DB に触れない（`/healthz` は使えない。Cloud Run が z で終わる経路の一部を横取りして 404 を返す）

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
- テストは機能ごとにファイルを分けている（`apps/web/tests/test_*_views.py`、`e2e/test_*.py`）。画面のテストで共有するもの（`client_in`・`event`）は `apps/web/tests/conftest.py`、E2E の `home` は `e2e/conftest.py`
- PR を作って CI が通ってから main へ。main に入ると Cloud Run へ自動デプロイ（2〜3分）
  - main は保護されている（PR 必須、CI の `test`・`e2e`・`docker` が必須、直接の push は不可）
  - **マージは Yuki さんが行う**（Claude からの `gh pr merge` は権限で止められる）。マージ後は、Deploy の成功と新しいリビジョンを確認して報告する
  - **PR は積まない。向き先は必ず main。** ほかの PR のブランチに向けると、マージしても main に入らない（画面には「Merged」と出るので気づきにくい。#99・#100 で起きた）。同じ資料を触る変更が続くときは、1つの PR にまとめるか、前の PR がマージされてから main から切る
  - マージされたら、**本番の画面やスクリプトに中身が入ったこと**まで確かめる（「Merged」の表示だけで判断しない）
- 読み上げ・コントラスト・見出しの抜けは、`e2e/test_accessibility.py`（axe）が CI で毎回確かめる。新しい画面を足したら、ここにも足す
- 見た目や操作に関わる変更は、ブラウザで実際に表示して確かめる（E2E のフィクスチャでスクリーンショットを撮るのが手早い）。必要なら触れる PoC を出す
- Dependabot が週1回、更新の PR を作る。Actions はコミット ID で固定しているので、更新はその PR で取り込む

## ハマりどころ
- Python 3.14：`ruff format` が `except (A, B):` を `except A, B:` に書き換える（3.14 では正しい構文）
- インラインスクリプトは CSP で禁止。JS は `static/js/app.js` に書く
- 開いたままの画面は、デプロイの後も古い `app.js` で動き続ける（ホーム画面に追加したアプリは特に）。HTML と JS の両方を変える機能は、**古い JS ＋ 新しい HTML** の組み合わせでも壊れないかを考える。一覧（`#grid`）の `data-app-js` が変わると、画面は自分で読み込み直す
- ログイン中の画面と応答は、ブラウザに保存させない（`Cache-Control: no-store`、`apps/core/private_pages.py`）。そのため、JS で `fetch` した応答の中身を使わないときも、`drain()` で読み切る（読まないと受け取りが終わらず、E2E の「通信が静かになるまで待つ」が終わらない）
- `HX-Trigger` に日本語を入れるときは `json.dumps`（ASCII エスケープ）を使う
- `HX-Trigger` の合図は、書いた順に、操作した要素から送られる。**シートを閉じる合図（`yl:close-sheet`）は最後に置く**。先に閉じると要素が消え、後の合図（知らせなど）がどこにも届かない（`_refresh()` がこの順を守っている）
- Neon はプール接続なので `DISABLE_SERVER_SIDE_CURSORS=True`
- allauth：`User` に username 欄がないので `ACCOUNT_USER_MODEL_USERNAME_FIELD = None` が必要（外すとログイン完了時に 500）
- E2E は `force_login` でログインするので、Google ログインの流れは通らない。ログインまわりは `apps/accounts/tests/test_google_login.py` で確かめる
- 通常のテスト用クライアントは CSRF の検査を省く。確かめるときは `Client(enforce_csrf_checks=True)`
- この開発機（Ubuntu 20.04）は Playwright の対応外。ブラウザの取得と E2E の実行には `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu22.04-x64` を付ける
- E2E で DB を読むのは、サーバーが書き終わったことを画面（成功のトーストなど）で確かめてから。「さっき」は返事の前に出る（楽観的更新）ので、それを合図にすると、書き込みの途中にぶつかって SQLite が `table is locked` を返す（#52 の原因だった）
- レート制限の回数はキャッシュに残る。テストでは `conftest.py` の `empty_cache` が毎回消している
- 秘密の値を端末で貼り付けるとき（`read -rs`）は画面に出ないので、二重に貼りやすい。登録したら長さと形だけを確かめる（値は表示しない）

## 現状（2026-10-14）
- **本番で動いている**：https://yattalog.ikura1.dev （決定 064。古い https://yattalog-332057063162.asia-southeast1.run.app は、GET を新しいドメインへ転送する。Variable `CANONICAL_HOST`）（Cloud Run シンガポール + Neon、Google Cloud のプロジェクトは `yattalog-511302`）
  - **β を 2026-10-19 に始めた**。Google の同意画面は「本番」で、誰でも登録できる（先着20人、決定 038）。成功の基準は「続けて使っている人が5人以上」（決定 051、管理画面の「利用状況」）
  - 残りは Yuki さんの手作業で、**Issue #117（固定）にチェックリストとしてまとめている**。終わったと聞いたら、Claude がチェックを付ける
- **ほかのセッションも、このリポジトリで PR を出している。** 作業の前に `gh pr list` と `git pull`。決定記録の番号は、取る前に `docs/decisions/` と開いている PR を確かめる
- 経緯・やり残し・次の候補は `docs/handoff.md`。リリース計画は `SPEC.md` 7章（α → β → v1 → v1.x）
- PoC（`poc/index.html`）は仕様確認用。本体とは別物
