"""アイコンの PNG を、SVG（static/icons/*.svg）から作り直す。

    uv run python tools/build_icons.py

SVG や tools/og.html を差し替えたら（デザイナーから元データが届いたときなど）これを流して、できた PNG をコミットする。
ブラウザ（Playwright の Chromium）で描くので、E2E と同じ準備が要る。
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

ICONS = Path(__file__).resolve().parent.parent / "static" / "icons"
# 出力するファイル名: (元の SVG, 一辺の px)
TARGETS = {
    "icon-192.png": ("icon.svg", 192),
    "icon-512.png": ("icon.svg", 512),
    "icon-maskable-192.png": ("icon-maskable.svg", 192),
    "icon-maskable-512.png": ("icon-maskable.svg", 512),
    "apple-touch-icon.png": ("icon-square.svg", 180),
    "favicon-32.png": ("favicon.svg", 32),
}


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, (source, size) in TARGETS.items():
            page = browser.new_page(viewport={"width": size, "height": size})
            svg = (ICONS / source).read_text()
            page.set_content(
                f"<style>html,body{{margin:0;background:transparent}}svg{{display:block;width:{size}px;height:{size}px}}</style>{svg}"
            )
            page.screenshot(path=str(ICONS / name), omit_background=True)
            page.close()
            print(name, size)
        # リンクのプレビュー用の画像（1200×630）。tools/og.html に、角のないアイコンを差し込んで描く
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        html = (
            (Path(__file__).resolve().parent / "og.html")
            .read_text()
            .replace("<!--ICON-->", (ICONS / "icon-square.svg").read_text())
        )
        page.set_content(html, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(ICONS / "og.png"))
        page.close()
        print("og.png", "1200x630")
        browser.close()


if __name__ == "__main__":
    main()
