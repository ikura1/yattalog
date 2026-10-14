"""アイコンの SVG（static/icons/*.svg）を書き出す。4つのファイルで、同じ絵を使い回すため。

    uv run python tools/draw_icons.py && uv run python tools/build_icons.py

絵を変えるときは、ここの数字を直して、上の2つを流す（SVG → PNG の順）。
デザイナーから SVG の元データが届いたら、このスクリプトは使わず、SVG を直接差し替える。
"""

from pathlib import Path

ICONS = Path(__file__).resolve().parent.parent / "static" / "icons"
GREEN, CREAM = "#1F6F5C", "#FFF6D6"


def _num(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _pt(x: float, y: float) -> str:
    return f"{_num(x)} {_num(y)}"


def cushion(cx: float, cy: float, w: float, h: float, k: tuple[float, float, float, float]) -> str:
    """丸みのある四角（辺が少しふくらむ）の線。

    k は角ごとの丸み（0.55 で楕円、1 に近いほど四角）。上 → 右 → 下 → 左の順に結ぶ。
    角ごとに少し変えると、手で押したような、ゆがんだ形になる。
    """
    k1, k2, k3, k4 = k
    return (
        f"M{_pt(cx, cy - h)} "
        f"C{_pt(cx + w * k1, cy - h)} {_pt(cx + w, cy - h * k1)} {_pt(cx + w, cy)} "
        f"C{_pt(cx + w, cy + h * k2)} {_pt(cx + w * k2, cy + h)} {_pt(cx, cy + h)} "
        f"C{_pt(cx - w * k3, cy + h)} {_pt(cx - w, cy + h * k3)} {_pt(cx - w, cy)} "
        f"C{_pt(cx - w, cy - h * k4)} {_pt(cx - w * k4, cy - h)} {_pt(cx, cy - h)}Z"
    )


TILE = cushion(50, 57.5, 28, 25.5, (0.78, 0.82, 0.76, 0.84))
BLOB = cushion(50, 50, 48.5, 48, (0.8, 0.76, 0.82, 0.74))  # 外形。少しゆがんだ、丸い四角
CHECK = "M39.5 58.5 L46.8 65.8 L61.5 47.5"
RAYS = ["M63.4 22.6 L64.6 16.6", "M72.4 27.4 L76.4 22.4", "M79.4 34.8 L85.4 32.6"]


def stamp(check_width: float = 9.5, ray_width: float = 6.4) -> str:
    """クリーム色のスタンプ（少し傾いた、丸みのある四角）と、緑のチェック、右上の3本の線。"""
    check = (
        f'<path d="{CHECK}" fill="none" stroke="{GREEN}" stroke-width="{check_width}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    rays = "\n".join(f'    <path d="{ray}"/>' for ray in RAYS)
    return f"""<g transform="rotate(-8 50 57.5)">
    <path d="{TILE}" fill="{CREAM}"/>
    {check}
  </g>
  <g fill="none" stroke="{CREAM}" stroke-width="{ray_width}" stroke-linecap="round">
{rays}
  </g>"""


def svg(body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">\n  {body}\n</svg>\n'


def scaled(scale: float, body: str) -> str:
    """絵の中心（52, 48）を、画像のまん中に合わせて、大きさを変える。"""
    return f'<g transform="translate(50 50) scale({scale}) translate(-52 -48)">\n  {body}\n  </g>'


def main() -> None:
    blob = f'<path d="{BLOB}" fill="{GREEN}"/>'
    full = f'<rect width="100" height="100" fill="{GREEN}"/>'
    files = {
        # そのままの形で出る場所用（アプリの中、オフラインの案内）。外形は、少しゆがんだ丸い四角
        "icon.svg": f"{blob}\n  {stamp()}",
        # iOS のホーム画面用。端まで塗る（OS が角を丸める）
        "icon-square.svg": f"{full}\n  {stamp()}",
        # Android 用。端まで塗り、絵を中央の円（直径 80%）に収める
        "icon-maskable.svg": f"{full}\n  {scaled(0.78, stamp())}",
        # タブ用。同じ絵を少し大きくし、線を太くして、16px でもつぶれないようにする
        "favicon.svg": f"{blob}\n  {scaled(1.1, stamp(check_width=11.5, ray_width=7.6))}",
    }
    for name, body in files.items():
        (ICONS / name).write_text(svg(body))
        print(name)


if __name__ == "__main__":
    main()
