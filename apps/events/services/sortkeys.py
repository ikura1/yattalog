"""並び順のソートキー（分数インデックス、レビュー E6）。

キーは「整数部＋小数部」の文字列（BASE62・ASCII 順）。
- 整数部の先頭の1文字が、整数部の長さを表す（a〜z は 2〜27文字、A〜Z は 27〜2文字）
- 先頭・末尾への追加では整数部を1つ進める（戻す）だけなので、キーはほとんど伸びない
- 2つのキーの間に入れるときだけ小数部が伸びる

rocicorp/fractional-indexing（CC0）のアルゴリズムを Python に移したもの。
"""

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_INDEX = {c: i for i, c in enumerate(DIGITS)}
_SMALLEST_INTEGER = "A" + "0" * 26


def _midpoint(a: str, b: str | None) -> str:
    """小数部どうしの中間。a < b、どちらも末尾が "0" ではないこと。"""
    if b is not None and a >= b:
        raise ValueError(f"{a!r} >= {b!r}")
    if a.endswith("0") or (b and b.endswith("0")):
        raise ValueError("trailing zero")
    if b is not None:
        n = 0
        while n < len(b) and (a[n] if n < len(a) else "0") == b[n]:
            n += 1
        if n > 0:
            return b[:n] + _midpoint(a[n:], b[n:])
    da = _INDEX[a[0]] if a else 0
    db = _INDEX[b[0]] if b is not None else len(DIGITS)
    if db - da > 1:
        return DIGITS[(da + db) // 2]
    if b is not None and len(b) > 1:
        return b[0]
    return DIGITS[da] + _midpoint(a[1:], None)


def _integer_length(head: str) -> int:
    if "a" <= head <= "z":
        return ord(head) - ord("a") + 2
    if "A" <= head <= "Z":
        return ord("Z") - ord(head) + 2
    raise ValueError(f"invalid head: {head!r}")


def _integer_part(key: str) -> str:
    n = _integer_length(key[0])
    if n > len(key):
        raise ValueError(f"invalid key: {key!r}")
    return key[:n]


def _validate(key: str) -> None:
    if key == _SMALLEST_INTEGER:
        raise ValueError("smallest key")
    i = _integer_part(key)
    if key[len(i) :].endswith("0"):
        raise ValueError(f"invalid key: {key!r}")


def _increment(x: str) -> str | None:
    head, digs = x[0], list(x[1:])
    carry = True
    for i in range(len(digs) - 1, -1, -1):
        if not carry:
            break
        d = _INDEX[digs[i]] + 1
        if d == len(DIGITS):
            digs[i] = "0"
        else:
            digs[i] = DIGITS[d]
            carry = False
    if carry:
        if head == "Z":
            return "a0"
        if head == "z":
            return None
        h = chr(ord(head) + 1)
        if h > "a":
            digs.append("0")
        else:
            digs.pop()
        return h + "".join(digs)
    return head + "".join(digs)


def _decrement(x: str) -> str | None:
    head, digs = x[0], list(x[1:])
    borrow = True
    for i in range(len(digs) - 1, -1, -1):
        if not borrow:
            break
        d = _INDEX[digs[i]] - 1
        if d == -1:
            digs[i] = DIGITS[-1]
        else:
            digs[i] = DIGITS[d]
            borrow = False
    if borrow:
        if head == "a":
            return "Z" + DIGITS[-1]
        if head == "A":
            return None
        h = chr(ord(head) - 1)
        if h < "Z":
            digs.append(DIGITS[-1])
        else:
            digs.pop()
        return h + "".join(digs)
    return head + "".join(digs)


def key_between(before: str | None, after: str | None) -> str:
    """before と after の間に入るキー。None は端（先頭または末尾）を表す。"""
    a, b = before, after
    if a is not None:
        _validate(a)
    if b is not None:
        _validate(b)
    if a is not None and b is not None and a >= b:
        raise ValueError(f"{a!r} >= {b!r}")
    if a is None:
        if b is None:
            return "a0"
        ib = _integer_part(b)
        fb = b[len(ib) :]
        if ib == _SMALLEST_INTEGER:
            return ib + _midpoint("", fb)
        if ib < b:
            return ib
        res = _decrement(ib)
        if res is None:
            raise ValueError("cannot decrement any more")
        return res
    if b is None:
        ia = _integer_part(a)
        fa = a[len(ia) :]
        i = _increment(ia)
        return ia + _midpoint(fa, None) if i is None else i
    ia, ib = _integer_part(a), _integer_part(b)
    fa, fb = a[len(ia) :], b[len(ib) :]
    if ia == ib:
        return ia + _midpoint(fa, fb)
    i = _increment(ia)
    if i is None:
        raise ValueError("cannot increment any more")
    if i < b:
        return i
    return ia + _midpoint(fa, None)


def key_first(current_first: str | None) -> str:
    """先頭に入れるキー（新しく作ったイベントは先頭、決定 008）。"""
    return key_between(None, current_first)


def key_last(current_last: str | None) -> str:
    return key_between(current_last, None)
