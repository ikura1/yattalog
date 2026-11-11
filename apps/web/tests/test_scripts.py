"""画面のスクリプト（`static/js/`）の分け方と、本番での配り方（決定 070）。"""

import re
import shutil
from pathlib import Path

import pytest
from django.conf import settings as conf

from apps.core.testing import collect_static

JS_DIR = Path(conf.BASE_DIR) / "static" / "js"
MODULES = sorted(p.name for p in JS_DIR.glob("*.js"))
PARTS = [name for name in MODULES if name != "app.js"]
# Django が本番で書き換えられる形（1行、同じ場所のファイル、; で終わる）
IMPORT_LINE = re.compile(r'^import \{ [^;{}]+ \} from "\./([a-z-]+\.js)";$')
MAX_LINES = 400


def test_スクリプトは_機能ごとのファイルに分かれている():
    assert len(PARTS) >= 5
    too_long = {name: n for name in MODULES if (n := len((JS_DIR / name).read_text().splitlines())) > MAX_LINES}
    assert too_long == {}


def test_入口は_モジュールとして読み込む(client, db):
    html = client.get("/login/").content.decode()

    assert '<script type="module" src="/static/js/app.js"></script>' in html


def test_分けたファイルは_入口と一緒に取りにいかせる(client, db):
    """入口を読んでから順に取りにいくと、往復のぶんだけ画面が動き出すのが遅れる。"""
    html = client.get("/login/").content.decode()

    missing = [name for name in PARTS if f'<link rel="modulepreload" href="/static/js/{name}">' not in html]
    assert missing == []


@pytest.mark.parametrize("name", MODULES)
def test_読み込む先は_同じ場所にあるファイルで_本番で書き換えられる形にしている(name):
    lines = [line for line in (JS_DIR / name).read_text().splitlines() if re.match(r"\s*import\b", line)]

    for line in lines:
        found = IMPORT_LINE.match(line)
        assert found, f"{name}: {line}"
        assert found[1] in MODULES, f"{name}: {found[1]} がない"


def test_入口から_すべてのファイルにたどり着ける():
    """どこからも読み込まれないファイルは、動かないまま残る。"""
    seen, todo = set(), ["app.js"]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        todo += re.findall(r'from "\./([a-z-]+\.js)";', (JS_DIR / name).read_text())

    assert sorted(seen) == MODULES


@pytest.fixture
def source(tmp_path):
    """スクリプトだけを写した、書き換えてよい置き場。"""
    shutil.copytree(JS_DIR, tmp_path / "src" / "js")
    return tmp_path / "src"


def test_本番では_読み込む先の名前にも_中身のハッシュが入る(source, tmp_path):
    """入らないと、ブラウザが古いファイルを使い続ける（静的ファイルは、長くしまわせている）。"""
    paths = collect_static(source, tmp_path / "out")

    for name in MODULES:
        built = (tmp_path / "out" / paths[f"js/{name}"]).read_text()
        targets = re.findall(r'from\s*"\./([^"]+)"', built)
        assert len(targets) == len(re.findall(r"(?m)^import ", (JS_DIR / name).read_text()))
        assert all(re.fullmatch(r"[a-z-]+\.[0-9a-f]{12}\.js", t) for t in targets), f"{name}: {targets}"


@pytest.mark.parametrize("changed", PARTS)
def test_どのファイルを変えても_入口の名前が変わる(source, tmp_path, changed):
    """開いたままの画面は、入口の名前（一覧の data-app-js）を見て、新しい版に切り替える。"""
    before = collect_static(source, tmp_path / "before")["js/app.js"]

    with (source / "js" / changed).open("a") as f:
        f.write("// changed\n")

    assert collect_static(source, tmp_path / "after")["js/app.js"] != before
