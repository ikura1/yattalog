"""イベントの名前から、アイコンの絵文字の候補を出す（決定 065）。アプリの中の言葉の辞書で決める（AI は使わない）。"""

import pytest

from apps.events.services.emoji_hints import FALLBACK, HINTS, hints_for_client, suggest
from apps.events.services.events import is_single_emoji


@pytest.mark.parametrize(
    ("name", "first"),
    [
        ("シーツ交換", "🛏️"),
        ("美容院", "✂️"),
        ("実家に電話", "📞"),
        ("排水口の掃除", "🕳️"),
        ("推し活", "🎤"),
        ("歯医者", "🦷"),
    ],
)
def test_名前に含まれる言葉から_いちばん合いそうな絵文字を先頭に出す(name, first):
    assert suggest(name)[0] == first


def test_候補は重ならず_多くても5つ():
    found = suggest("お風呂とトイレの掃除")
    assert len(found) == len(set(found)) <= 5


def test_合う言葉がなければ_よく使う絵文字を出す():
    assert suggest("ピアノの練習") == FALLBACK and suggest("") == FALLBACK


def test_辞書の絵文字は_どれもアイコンに使える1文字():
    for words, emojis in HINTS:
        assert words and emojis
        assert all(is_single_emoji(e) for e in emojis)
    assert all(is_single_emoji(e) for e in FALLBACK)


def test_端末でも同じ候補を出せるよう_辞書をそのまま渡せる():
    data = hints_for_client()
    assert data["fallback"] == FALLBACK and data["hints"][0] == [list(HINTS[0][0]), list(HINTS[0][1])]
