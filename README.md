# Yattalog（やったログ）

「あれ、前にやったのいつだっけ？」に答えるアプリ。やったら1タップで記録し、前回からの日数がひと目でわかる。

- 仕様：[SPEC.md](SPEC.md)
- 決定記録：[docs/decisions/](docs/decisions/)
- データモデル：[docs/data-model.md](docs/data-model.md)
- PoC（仕様確認用のプロトタイプ）：[poc/](poc/)

## 開発

必要なもの：[uv](https://docs.astral.sh/uv/)（Python 3.14 は uv が入れてくれる）

```sh
uv sync
export DJANGO_DEBUG=1
uv run python manage.py migrate
uv run python manage.py runserver
```

開発では SQLite を使う。PostgreSQL で動かすときは `DATABASE_URL=postgres://...` を設定する。

### Google ログインを手元で試す

1. Google Cloud Console で OAuth クライアント（ウェブ アプリケーション）を作る
   - 承認済みのリダイレクト URI：`http://127.0.0.1:8000/accounts/google/login/callback/`
2. 環境変数 `GOOGLE_CLIENT_ID` と `GOOGLE_CLIENT_SECRET` を設定して起動する

### テストと lint

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## 構成

| 場所 | 中身 |
|---|---|
| `config/` | 設定・URL |
| `apps/accounts/` | ユーザー（Google ログインのみ）、allauth のアダプタ |
| `apps/spaces/` | スペース（持ち主）と権限チェック |
| `apps/events/` | イベント・カテゴリ・記録のモデルと**サービス層**（`services/`） |
| `apps/web/` | 画面（Django テンプレート＋htmx）。処理はサービス層を呼ぶだけ（決定 027） |
| `templates/`、`static/` | テンプレート、CSS、JS |

## デプロイ（Cloud Run ＋ Neon）

試験運用はほぼ0円の構成で動かす。手順は [deploy/README.md](deploy/README.md)。main にマージすると GitHub Actions が自動でデプロイする。
