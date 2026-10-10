import random

from hypothesis import given, settings
from hypothesis import strategies as st

from apps.events.services.sortkeys import DIGITS, key_between, key_first, key_last


def test_first_key():
    assert key_between(None, None) == "V"


def test_before_and_after():
    k = key_between(None, None)
    assert key_first(k) < k < key_last(k)


@settings(max_examples=200)
@given(st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=200))
def test_random_inserts_keep_order(positions):
    keys: list[str] = []
    for p in positions:
        i = p % (len(keys) + 1)
        lo = keys[i - 1] if i > 0 else None
        hi = keys[i] if i < len(keys) else None
        k = key_between(lo, hi)
        assert (lo is None or lo < k) and (hi is None or k < hi)
        assert not k.endswith("0")
        assert all(c in DIGITS for c in k)
        keys.insert(i, k)
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)


def test_repeated_insert_at_front_stays_short_enough():
    first = key_between(None, None)
    for _ in range(500):
        first = key_first(first)
    assert len(first) < 120  # 500回先頭に足しても、DB の列（64文字）に収まる目安
    random.seed(0)
