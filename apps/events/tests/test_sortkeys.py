"""並び順のソートキー（分数インデックス）の仕様。"""

from hypothesis import given, settings
from hypothesis import strategies as st

from apps.events.models import Category, Event
from apps.events.services.sortkeys import DIGITS, key_between, key_first, key_last

DB_MAX = Event._meta.get_field("sort_key").max_length


def test_DB_の列の長さは_Event_と_Category_で同じ():
    assert DB_MAX == Category._meta.get_field("sort_key").max_length == 64


def test_最初のキーの前後にキーを作れる():
    k = key_between(None, None)
    assert key_first(k) < k < key_last(k)


def test_先頭に1000回追加してもDBの列に収まる():
    # 新しいイベントとアーカイブから戻したイベントは先頭に入る（決定 008）
    k = key_between(None, None)
    for _ in range(1000):
        k = key_first(k)
        assert len(k) <= DB_MAX


def test_末尾に1000回追加してもDBの列に収まる():
    k = key_between(None, None)
    for _ in range(1000):
        k = key_last(k)
        assert len(k) <= DB_MAX


def test_同じ2つのキーの間に40回差し込んでもDBの列に収まる():
    lo, hi = key_between(None, None), None
    hi = key_last(lo)
    for _ in range(40):
        hi = key_between(lo, hi)
        assert len(hi) <= DB_MAX


@settings(max_examples=200)
@given(st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=200))
def test_どこに差し込んでも順序が保たれ重複しない(positions):
    keys: list[str] = []
    for p in positions:
        i = p % (len(keys) + 1)
        lo = keys[i - 1] if i > 0 else None
        hi = keys[i] if i < len(keys) else None
        k = key_between(lo, hi)
        assert (lo is None or lo < k) and (hi is None or k < hi)
        assert all(c in DIGITS for c in k)
        keys.insert(i, k)
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)
