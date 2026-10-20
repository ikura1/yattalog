"""イベントとカテゴリの画面（追加・編集、アイコン、絵文字、タブ、詳細）。"""

import uuid
from datetime import date, timedelta

import pytest

from apps.events.models import Category, Event
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When


def test_前回やった日つきでイベントを作り詳細を開ける(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "散髪", "emoji": "✂️", "color": "grape", "streak_unit": "month", "last_done": "2026-09-01"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    e = Event.objects.get(name="散髪")
    assert "よくやる時期" in client_in.get(f"/events/{e.id}/").content.decode()


def test_前回やった日が壊れていたらフォームにエラーを出す(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "散髪", "emoji": "✂️", "color": "grape", "streak_unit": "month", "last_done": "nope"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200 and not Event.objects.exists()


def test_おすすめのアイコンはすべて絵文字として通る(user):
    from apps.web.views import EMOJIS

    for emoji in EMOJIS:
        assert ev_svc.create_event(user, name="x", emoji=emoji, color="sky").emoji == emoji


def test_入力欄に絵文字を入れると_おすすめの選択より優先される(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "ぎょうざ", "emoji": "✂️", "emoji_custom": "🥟", "color": "sky", "streak_unit": "day"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204 and Event.objects.get(name="ぎょうざ").emoji == "🥟"


def test_入力欄だけでアイコンを決められる(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "ぎょうざ", "emoji_custom": "🥟", "color": "sky", "streak_unit": "day"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204 and Event.objects.get(name="ぎょうざ").emoji == "🥟"


def test_入力欄が絵文字でなければ_フォームにエラーを出して入力を残す(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "ぎょうざ", "emoji": "✂️", "emoji_custom": "ぎょ", "color": "sky", "streak_unit": "day"},
        HTTP_HX_REQUEST="true",
    )
    body = r.content.decode()
    assert r.status_code == 200 and not Event.objects.exists()
    assert "絵文字を1つ" in body and 'name="emoji_custom" value="ぎょ"' in body


def test_編集シートでは_おすすめにないアイコンが入力欄に入っている(client_in, user):
    e = ev_svc.create_event(user, name="ぎょうざ", emoji="🥟", color="sky")
    body = client_in.get(f"/events/{e.id}/edit/").content.decode()
    recommended = body.split('class="emojis"')[1].split("</div>")[0]
    assert 'name="emoji_custom" value="🥟"' in body and " checked" not in recommended


def test_編集シートでは_おすすめにあるアイコンは一覧で選ばれ_入力欄は空(client_in, event):
    body = client_in.get(f"/events/{event.id}/edit/").content.decode()
    assert 'name="emoji_custom" value=""' in body and 'value="🛏️" checked' in body


def test_編集で入力欄の絵文字に変えられる(client_in, event):
    r = client_in.post(
        f"/events/{event.id}/edit/",
        {"name": "シーツ交換", "emoji_custom": "🧸", "color": "sky", "streak_unit": "week"},
        HTTP_HX_REQUEST="true",
    )
    event.refresh_from_db()
    assert r.status_code == 204 and event.emoji == "🧸"


def test_詳細の壊れたクエリは無視して表示する(client_in, event):
    r = client_in.get(f"/events/{event.id}/?y=abc&m=13&sy=x&day=nope")
    assert r.status_code == 200


def test_タイムゾーンを設定できる(client_in, user):
    assert client_in.post("/timezone/", {"tz": "America/Los_Angeles"}).status_code == 200
    user.refresh_from_db()
    assert user.timezone == "America/Los_Angeles" and user.onboarded_at is not None


def test_正しくないタイムゾーンは400(client_in, user):
    assert client_in.post("/timezone/", {"tz": "Not/AZone"}).status_code == 400


def test_DBのソートキーが壊れていても並べ替えは500ではなく422(client_in, user, event):
    other = ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape")
    Event.objects.filter(id=other.id).update(sort_key="!!")
    assert client_in.post(f"/events/{event.id}/move/", {"after": str(other.id)}).status_code == 422


@pytest.mark.parametrize("path", ["/events/{id}/", "/events/{id}/edit/", "/events/{id}/restore/", "/logs/{id}/edit/"])
def test_存在しないIDは404(client_in, path):
    method = client_in.post if path.endswith("restore/") else client_in.get
    assert method(path.format(id=uuid.uuid4())).status_code == 404


def test_カテゴリを絵文字つきで作ると_タブとイベントのシートに絵文字が出る(client_in, user):
    r = client_in.post("/categories/", {"action": "create", "name": "家事", "emoji": "🧹"})
    assert r.status_code == 200 and Category.objects.get(name="家事").emoji == "🧹"
    assert "🧹</span>家事" in client_in.get("/").content.decode()
    assert "🧹</span>家事" in client_in.get("/events/new/").content.decode()


def test_絵文字なしのカテゴリは_名前だけが出る(client_in, user):
    ev_svc.create_category(user, "家事")
    assert 'class="cat-emo"' not in client_in.get("/").content.decode()


def test_カテゴリの一覧で絵文字を変えたり外したりできる(client_in, user):
    house = ev_svc.create_category(user, "家事", emoji="🧹")
    client_in.post("/categories/", {"action": "rename", "id": str(house.id), "name": "家事", "emoji": "🧺"})
    house.refresh_from_db()
    assert house.emoji == "🧺"

    client_in.post("/categories/", {"action": "rename", "id": str(house.id), "name": "家事", "emoji": ""})
    house.refresh_from_db()
    assert house.emoji == ""


def test_カテゴリの絵文字が正しくなければ_エラーを出して保存しない(client_in, user):
    r = client_in.post("/categories/", {"action": "create", "name": "家事", "emoji": "そうじ"})
    assert "絵文字を1つ" in r.content.decode() and not Category.objects.exists()
    assert "HX-Trigger" not in r


def test_カテゴリがあって_入っていないイベントもあれば_カテゴリなしのタブが件数つきで出る(client_in, user, event):
    house = ev_svc.create_category(user, "家事")
    ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", category_id=house.id)
    ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape")

    body = client_in.get("/").content.decode()

    assert 'data-tab="none"' in body and 'カテゴリなし<span class="n">2</span>' in body
    assert body.index('data-tab="none"') > body.index(f'data-tab="{house.id}"')


def test_カテゴリが1つもなければ_カテゴリなしのタブは出さない(client_in, event):
    assert 'data-tab="none"' not in client_in.get("/").content.decode()


def test_どのイベントもカテゴリに入っていれば_カテゴリなしのタブは出さない(client_in, user):
    house = ev_svc.create_category(user, "家事")
    ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", category_id=house.id)

    assert 'data-tab="none"' not in client_in.get("/").content.decode()


def test_カテゴリなしのタブから追加するときは_カテゴリの欄で_なし_が選ばれている(client_in, user):
    ev_svc.create_category(user, "家事")

    body = client_in.get("/events/new/?category=none").content.decode()

    assert '<input type="radio" name="category" value="" checked>' in body


def test_詳細画面では_2か月前と一緒に_正確な日数と日付も出る(client_in, user):
    from datetime import timedelta

    from apps.core.testing import TODAY

    e = ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape", last_done=TODAY - timedelta(63))

    body = client_in.get(f"/events/{e.id}/").content.decode()

    assert "2<small>か月前</small>" in body and "前回 8月8日（63日前）" in body


def test_詳細の統計に_最高連続を出す_単位がなしのイベントには出さない(client_in, user, event):
    for d in (date(2026, 9, 28), date(2026, 10, 5)):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=d))
    dentist = ev_svc.create_event(user, name="歯医者", emoji="🦷", color="pink", streak_unit="none")

    body = client_in.get(f"/events/{event.id}/").content.decode()
    assert "最高連続" in body and "2週連続" in body
    assert "最高連続" not in client_in.get(f"/events/{dentist.id}/").content.decode()


def test_詳細に_はじめて記録した日と_どれくらい前かを出す(client_in, user, event):
    log_svc.record(user, event.id, uuid.uuid4(), When(date=date(2025, 8, 3)))
    log_svc.record(user, event.id, uuid.uuid4())

    body = client_in.get(f"/events/{event.id}/").content.decode()

    assert "はじめての記録 2025年8月3日（1年2か月前）" in body


def test_詳細に_よくやる曜日と時間帯と日にちを出す(client_in, user, event):
    from datetime import time

    for d in (date(2026, 9, 26), date(2026, 10, 3)):  # 土曜
        log_svc.record(user, event.id, uuid.uuid4(), When(date=d, time=time(8)))
    log_svc.record(user, event.id, uuid.uuid4(), When(date=date(2026, 10, 1), time=time(21)))

    body = client_in.get(f"/events/{event.id}/").content.decode()

    assert ">曜日</button>" in body and "よくやるのは 土曜" in body and 'aria-label="土曜：2回"' in body
    assert ">時間帯</button>" in body and "よくやるのは 朝" in body and 'aria-label="朝：2回"' in body
    assert ">日にち</button>" in body and 'aria-label="3日：1回"' in body and 'aria-label="26日：1回"' in body
    assert "style=" not in body


def test_よくやるは_1枚のカードにまとめ_時期だけを開いておく(client_in, user, event):
    log_svc.record(user, event.id, uuid.uuid4())

    body = client_in.get(f"/events/{event.id}/").content.decode()

    assert body.count('class="card tend-card"') == 1 and 'class="card tendency"' not in body
    assert 'role="tablist"' in body
    assert 'data-tend-panel="season">' in body
    for key in ("wd", "tod", "md"):
        assert f'data-tend-panel="{key}" hidden>' in body


def test_記録の履歴は_はじめ20件で_もっと見るで続きを出す(client_in, user, event):
    for i in range(25):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=date(2026, 9, 1) + timedelta(i)))

    first = client_in.get(f"/events/{event.id}/?y=2026&m=9").content.decode()
    more = client_in.get(f"/events/{event.id}/?y=2026&m=9&n=40").content.decode()

    assert first.count('aria-label="この記録を削除"') == 20
    assert "もっと見る（あと 5件）" in first and 'hx-get="?y=2026&amp;m=9&amp;n=40"' in first
    assert more.count('aria-label="この記録を削除"') == 25 and "もっと見る" not in more


def test_履歴の件数の指定がおかしくても_表示できる(client_in, user, event):
    log_svc.record(user, event.id, uuid.uuid4())
    for n in ("abc", "-5", "999999"):
        assert client_in.get(f"/events/{event.id}/?n={n}").status_code == 200


def test_詳細に_いちばんよくやった月を出す(client_in, user, event):
    for d in (date(2026, 4, 2), date(2026, 4, 20)):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=d))
    assert "いちばんよくやったのは 2026年4月（2回）" in client_in.get(f"/events/{event.id}/").content.decode()


def test_年の端のカレンダーでも_表示できる(client_in, user, event):
    """9999年12月の日曜始まりのカレンダーは、10000年の日付を作ろうとして落ちていた。"""
    log_svc.record(user, event.id, uuid.uuid4())
    assert client_in.get(f"/events/{event.id}/?y=9999&m=12").status_code == 200
    assert client_in.get(f"/events/{event.id}/?y=1900&m=1").status_code == 200


def test_もっと見るは_上限まで来たら出さない(client_in, user, event, settings):
    from apps.web.views import events as event_views

    event_views.HISTORY_MAX, saved = 30, event_views.HISTORY_MAX
    try:
        for i in range(35):
            log_svc.record(user, event.id, uuid.uuid4(), When(date=date(2026, 9, 1) + timedelta(i % 30)))
        at_max = client_in.get(f"/events/{event.id}/?n=30").content.decode()
        assert at_max.count('aria-label="この記録を削除"') == 30 and "もっと見る" not in at_max
        below = client_in.get(f"/events/{event.id}/?n=20").content.decode()
        assert 'n=30"' in below  # 上限を超える数（40）にはしない
    finally:
        event_views.HISTORY_MAX = saved


def test_集計の画面は_htmx_かどうかで中身が変わるので_キャッシュを分ける(client_in, user, event):
    response = client_in.get(f"/events/{event.id}/")
    assert "HX-Request" in response["Vary"]
    assert "HX-Request" in client_in.get("/review/")["Vary"]


def test_追加シートでは_候補の行を出し_24個の一覧と入力欄は畳んでおく(client_in):
    body = client_in.get("/events/new/").content.decode()
    row = body.split('class="emo-row"')[1].split("</div>")[0]
    assert " checked" in row  # 候補の先頭を、最初から選んでおく
    assert 'data-emoji-hints="' in body and 'data-auto="1"' in body
    more = body.split('<details class="emo-more"')[1].split("</details>")[0]
    assert 'class="emojis"' in more and 'id="evEmoji"' in more


def test_追加に失敗して戻ってきたら_名前からの候補を出し直す(client_in):
    r = client_in.post("/events/new/", {"name": "シーツ交換", "emoji": "", "color": "nope"})
    row = r.content.decode().split('class="emo-row"')[1].split("</div>")[0]
    assert 'value="🛏️"' in row


def test_編集シートでは_いまのアイコンを候補の先頭で選び_名前を変えても勝手に変えない(client_in, event):
    body = client_in.get(f"/events/{event.id}/edit/").content.decode()
    row = body.split('class="emo-row"')[1].split("</div>")[0]
    assert row.index('value="🛏️" checked') < row.index("</label>")
    assert 'data-auto="1"' not in body


def test_カテゴリは_前後を指定して並べ替えられる_タブも更新する(client_in, user):
    a, b, c = (ev_svc.create_category(user, n) for n in ("家のこと", "身だしなみ", "からだ"))

    r = client_in.post("/categories/", {"action": "move", "id": c.id, "before": a.id, "after": b.id})

    assert r.status_code == 200 and "yl:changed" in r["HX-Trigger"]
    assert [x.name for x in ev_svc.list_categories(user)] == ["家のこと", "からだ", "身だしなみ"]


def test_カテゴリの一覧には_並べ替えの取っ手がある_矢印のボタンはない(client_in, user):
    ev_svc.create_category(user, "家のこと")
    body = client_in.get("/categories/").content.decode()
    assert (
        'class="iconbtn cat-handle"' in body and 'aria-label="「家のこと」を並べ替え（↑↓キーでも動かせます）"' in body
    )
    assert 'aria-label="上へ"' not in body and 'aria-label="下へ"' not in body


def test_タブの右のボタンは_追加ではなく編集と分かる見た目にする(client_in, user, event):
    """「＋」だと追加だけに見えるのに、名前の変更や並べ替え・削除までできる画面が開いていた。"""
    ev_svc.create_category(user, "家のこと")
    body = client_in.get("/").content.decode()
    assert 'class="tab-add" aria-label="カテゴリを編集" title="カテゴリを編集"' in body and ">✎</button>" in body


def test_詳細のカレンダーは_週の始まりの曜日から並ぶ(client_in, user, event):
    def first_dow():
        body = client_in.get(f"/events/{event.id}/").content.decode()
        return body.split('<span class="dow">')[1][0]

    assert first_dow() == "月"
    ev_svc.set_week_start(user, "sun")
    assert first_dow() == "日"
