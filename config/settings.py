"""Yattalog の設定。

値は環境変数から読む。開発では `.env` を使わず、既定値（SQLite・DEBUG）で動く。
本番（Render）では DATABASE_URL・SECRET_KEY などを環境変数で渡す。
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


DEBUG = env_bool("DJANGO_DEBUG", default=False)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("dev-insecure-secret-key-change-me" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY を設定してください（開発では DJANGO_DEBUG=1）")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
if render_host := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(render_host)
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in {"localhost", "127.0.0.1"}]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "apps.accounts",
    "apps.spaces",
    "apps.events",
    "apps.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.ratelimit.RateLimitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csp",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Neon のコネクションプーラー（PgBouncer のトランザクションモード）ではサーバー側カーソルが使えない
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "allauth.account.auth_backends.AuthenticationBackend",
]

# --- 国際化 ---------------------------------------------------------------
LANGUAGE_CODE = "ja"
TIME_ZONE = "UTC"  # DB は UTC。ユーザーごとのタイムゾーンはアプリ側で扱う（決定 023・026）
USE_I18N = True
USE_TZ = True

# --- 静的ファイル -----------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# --- 認証（Google ログインのみ、決定 016）-----------------------------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # User に username 欄はない（allauth の既定は "username"）
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # Google 側で確認済みのメールだけを受け付ける（adapter で検証）
ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAccountAdapter"
SOCIALACCOUNT_ONLY = True  # パスワードでの登録・ログインを無効にする
SOCIALACCOUNT_LOGIN_ON_GET = False  # ログインは POST で開始する（CSRF 対策）
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_STORE_TOKENS = False  # Google のアクセストークンは保存しない
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False  # メールアドレスでの照合はしない（sub で識別、レビュー S3）
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["openid", "email", "profile"],
        "AUTH_PARAMS": {"prompt": "select_account"},
        "OAUTH_PKCE_ENABLED": True,
        "APP": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        },
    }
}

# 登録できる人数の上限（決定 038）。達したら新しい登録を止める。登録済みの人はそのまま使える
MAX_USERS = int(os.environ.get("YATTALOG_MAX_USERS", "20"))

# --- セキュリティ（レビュー S5）---------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90日（スマホで毎回ログインさせない）
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# --- レート制限（レビュー S7、決定 037）---------------------------------------
# 名前: (回数, 秒)。ログインしていれば人ごと、していなければ接続元ごとに数える
RATE_LIMITS = {
    "record": (60, 60),  # 記録の追加
    "write": (120, 60),  # 書き込み全般（記録を含む）
    "login": (20, 60),  # ログインの入口と戻り先（/accounts/）
    "export": (5, 3600),  # データの書き出し（全データを読むので、1時間あたりで数える）
    "all": (300, 60),  # すべてのリクエスト（静的ファイルは除く）
}
# 回数はプロセス内に持つ。Cloud Run のインスタンスごとに別々に数える（最大2台）
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# CSP（Django 6.0 の標準機能）。インラインスクリプトは nonce 付きのものだけを許可する
from django.utils.csp import CSP  # noqa: E402

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE, "https://fonts.googleapis.com"],
    "font-src": [CSP.SELF, "https://fonts.gstatic.com"],
    "img-src": [CSP.SELF, "data:", "blob:"],
    "connect-src": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "form-action": [CSP.SELF, "https://accounts.google.com"],
    "base-uri": [CSP.SELF],
    "object-src": [CSP.NONE],
}

ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "admin").strip("/") + "/"  # 本番では推測しにくい値にする（レビュー S10）

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    # 本番は1行1件の JSON にして、重要度とトレースバックを Cloud Logging に伝える（決定 041）
    "formatters": {"cloud_run": {"()": "apps.core.logging.CloudRunFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", **({} if DEBUG else {"formatter": "cloud_run"})}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# email はログイン ID ではない（識別は Google の sub）ため、一意制約を付けていない
# HSTS preload はドメインが決まるまで有効にしない（取り消しに時間がかかるため）
SILENCED_SYSTEM_CHECKS = ["auth.W004", "security.W021"]
