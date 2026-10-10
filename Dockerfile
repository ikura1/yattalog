# Cloud Run 用のイメージ（決定 033）
FROM python:3.14-slim
RUN pip install --no-cache-dir uv==0.11.32
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# 依存関係だけを先に入れて、レイヤーのキャッシュを効かせる
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
# 静的ファイルはイメージに含めて whitenoise で配信する（ビルド時だけのダミーの秘密鍵）
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput \
 && useradd --create-home --uid 10001 app && chown -R app /app
USER app

# Cloud Run は PORT を渡してくる。1プロセス＋スレッドにして、起動（コールドスタート）を速くする
CMD exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 0
