"""デプロイの設定（.github/workflows/deploy.yml）。"""

from pathlib import Path

from django.conf import settings

DEPLOY = Path(settings.BASE_DIR, ".github", "workflows", "deploy.yml").read_text()


def test_環境変数は_カンマを含む値でも壊れない区切りで渡す():
    """許可するホストや管理者のメールアドレスは、カンマで区切って複数入れる。

    gcloud の --set-env-vars は、既定ではカンマを「次の変数」の区切りと読むので、値にカンマがあるとデプロイが止まる
    （2026-10-17 に、DJANGO_ALLOWED_HOSTS に2つ目のホストを足して起きた）。区切りを ;; に変えて渡す。
    """
    lines = [line for line in DEPLOY.splitlines() if "--set-env-vars" in line]
    assert lines and all('--set-env-vars "^;;^' in line for line in lines)
    assert all(",YATTALOG_" not in line and ",GOOGLE_" not in line for line in lines)
