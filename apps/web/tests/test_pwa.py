"""ホーム画面への追加（PWA）：アイコン・マニフェスト・案内（SPEC 3.13、決定 031・043）。"""

import json
import struct
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders

ICONS = Path(settings.BASE_DIR) / "static" / "icons"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


@pytest.fixture
def client_in(client, user):
    client.force_login(user)
    return client


@pytest.mark.parametrize(
    "name,size",
    [
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("icon-maskable-192.png", 192),
        ("icon-maskable-512.png", 512),
        ("apple-touch-icon.png", 180),
        ("favicon-32.png", 32),
    ],
)
def test_アイコンの画像が_決まった大きさでそろっている(name, size):
    assert png_size(ICONS / name) == (size, size)


def test_マニフェストは_ログインしなくても取れて_アプリとして追加できる内容になっている(client, db):
    r = client.get("/manifest.webmanifest")

    assert r.status_code == 200 and r["Content-Type"] == "application/manifest+json"
    m = json.loads(r.content)
    assert (m["name"], m["short_name"], m["lang"]) == ("Yattalog", "Yattalog", "ja")
    assert (m["start_url"], m["scope"], m["display"]) == ("/", "/", "standalone")
    assert m["background_color"] == "#EEF1F6" and m["theme_color"] == "#EEF1F6"


def test_マニフェストのアイコンは_ふつうの形と_切り抜き用の両方がある(client, db):
    icons = json.loads(client.get("/manifest.webmanifest").content)["icons"]

    assert {(i["sizes"], i["purpose"]) for i in icons} == {
        ("192x192", "any"),
        ("512x512", "any"),
        ("192x192", "maskable"),
        ("512x512", "maskable"),
    }
    assert all(i["type"] == "image/png" and i["src"].startswith("/static/icons/") for i in icons)
    for icon in icons:
        assert finders.find(icon["src"].removeprefix("/static/")), icon["src"]


@pytest.mark.parametrize("path", ["/login/", "/terms/"])
def test_どのページにも_マニフェストとアイコンへのリンクがある(client, db, path):
    body = client.get(path).content.decode()
    assert '<link rel="manifest" href="/manifest.webmanifest">' in body
    assert 'rel="apple-touch-icon"' in body and "apple-touch-icon" in body
    assert 'rel="icon"' in body and "favicon" in body
    assert '<meta name="apple-mobile-web-app-title" content="Yattalog">' in body


def test_ホームには_追加の案内のバナーが_隠れた状態で入っている(client_in):
    body = client_in.get("/").content.decode()
    assert 'id="installBanner" hidden' in body and "ホーム画面に追加すると、1タップで開けます" in body
    assert 'data-install-url="/install/"' in body


def test_ログイン画面には_追加の案内を出さない(client, db):
    assert "installBanner" not in client.get("/login/").content.decode()


def test_メニューから_いつでも追加の方法を開ける(client_in):
    assert "ホーム画面に追加する方法" in client_in.get("/menu/").content.decode()


@pytest.mark.parametrize(
    "platform,expected,unexpected",
    [
        ("ios", "共有ボタン", "Safari で開き直"),
        ("ios-other", "Safari で開き直", "共有ボタン"),
        ("android", "インストール", "共有ボタン"),
    ],
)
def test_追加の方法は_端末に合わせて出し分ける(client_in, platform, expected, unexpected):
    body = client_in.get(f"/install/?p={platform}").content.decode()
    assert expected in body and unexpected not in body and "ホーム画面に追加" in body


def test_端末が分からないときは_すべての方法を並べる(client_in):
    body = client_in.get("/install/").content.decode()
    assert "iPhone・iPad" in body and "Android" in body and "パソコン" in body


def test_追加の方法は_ログインしていなければ開けない(client, db):
    assert "/login/" in client.get("/install/")["Location"]


# --- リンクを貼ったときの見え方（シェアの投稿文に URL が付く。決定 053） ---


def test_リンクのプレビュー用の画像が_1200x630_である():
    assert png_size(ICONS / "og.png") == (1200, 630)


@pytest.mark.parametrize("path", ["/login/", "/terms/"])
def test_ログイン前の画面に_リンクのプレビューの情報がある(client, db, path):
    body = client.get(path).content.decode()

    assert '<meta property="og:site_name" content="Yattalog">' in body
    assert '<meta property="og:title" content="Yattalog（やったログ）">' in body
    assert '<meta property="og:type" content="website">' in body
    assert '<meta name="twitter:card" content="summary_large_image">' in body
    assert "前にやったの、いつだっけ？" in body and '<meta name="description" content="' in body


def test_プレビューの画像と_URL_は_http_から始まる完全な形で出す(client, db):
    """X や LINE は、相対パスの画像を読めない。"""
    body = client.get("/login/").content.decode()

    assert '<meta property="og:image" content="http://testserver/static/icons/og.png">' in body
    assert '<meta property="og:url" content="http://testserver/">' in body
    assert '<meta property="og:image:width" content="1200">' in body
