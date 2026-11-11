"""本番と同じ形に集めたスクリプト（名前に中身のハッシュが入り、読み込む先も書き換わる）が、ブラウザで動く（決定 070）。

ほかの E2E は、書き換える前のファイルで動かしている。書き換えで壊れても、そちらでは気づけない。
"""

import shutil
from pathlib import Path

import pytest
from django.conf import settings
from playwright.sync_api import expect

from apps.core.testing import collect_static

pytestmark = pytest.mark.e2e


def serve_built_scripts(page, tmp_path) -> list[str]:
    """スクリプトの求めに、集めたあとのファイルを返す。ブラウザが求めた名前を、順に残す。"""
    shutil.copytree(Path(settings.BASE_DIR) / "static" / "js", tmp_path / "src" / "js")
    out = tmp_path / "out"
    paths = collect_static(tmp_path / "src", out)
    asked = []

    def handle(route):
        name = "js/" + route.request.url.rsplit("/", 1)[1]
        built = paths.get(name, name)  # 入口はハッシュなしの名前で求められる。その先は、書き換えたあとの名前
        asked.append(name)
        route.fulfill(path=out / built, content_type="text/javascript")

    page.route("**/static/js/*.js", handle)
    return asked


# Service Worker が受け持った求めは、テストから差し替えられない。このテストでは登録させない
@pytest.mark.browser_context_args(service_workers="block")
def test_本番と同じ形に集めたスクリプトで_記録できる(home, tmp_path):
    page = home
    errors = []
    page.on("pageerror", lambda error: errors.append(error))
    asked = serve_built_scripts(page, tmp_path)
    page.reload()

    page.locator("#grid .tile", has_text="シーツ交換").click()

    expect(page.locator(".toast", has_text="やった！")).to_be_visible()
    assert errors == []
    hashed = {name for name in asked if name.count(".") == 2}
    assert (
        len(hashed) == len(list((Path(settings.BASE_DIR) / "static" / "js").glob("*.js"))) - 1
    )  # 入口のほかは、すべてハッシュ入りで読み込む
