"""並び順のソートキー（分数インデックス、レビュー E6）。

キーは BASE62（ASCII 順）の文字列で、末尾が "0" にならない。
2つのキーの間に、新しいキーをいくらでも作れるので、並べ替えで動かした1件だけを更新すればよい。
"""

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(DIGITS)
_INDEX = {c: i for i, c in enumerate(DIGITS)}


def _midpoint(a: str, b: str | None) -> str:
    if b is not None and a >= b:
        raise ValueError(f"{a!r} >= {b!r}")
    if a.endswith("0") or (b is not None and b.endswith("0")):
        raise ValueError("trailing zero")
    if b is not None:
        n = 0
        while n < len(b) and (a[n] if n < len(a) else "0") == b[n]:
            n += 1
        if n > 0:
            return b[:n] + _midpoint(a[n:], b[n:])
    da = _INDEX[a[0]] if a else 0
    db = _INDEX[b[0]] if b is not None else BASE
    if db - da > 1:
        return DIGITS[(da + db) // 2]
    if b is not None and len(b) > 1:
        return b[0]
    return DIGITS[da] + _midpoint(a[1:], None)


def key_between(before: str | None, after: str | None) -> str:
    """before と after の間に入るキー。None は端（先頭または末尾）を表す。"""
    return _midpoint(before or "", after)


def key_first(current_first: str | None) -> str:
    """先頭に入れるキー（新しく作ったイベントは先頭、決定 008）。"""
    return key_between(None, current_first)


def key_last(current_last: str | None) -> str:
    return key_between(current_last, None)
