"""他人のデータに触れないこと（レビュー S4）。ID を受け取る URL は、すべてここで確かめる。"""

import uuid

import pytest

from apps.events.models import Event, Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc


@pytest.fixture
def theirs(other_user):
    e = ev_svc.create_event(other_user, name="散髪", emoji="✂️", color="grape")
    lid = uuid.uuid4()
    log_svc.record(other_user, e.id, lid)
    return e, lid


# ID を受け取る URL と、他人の ID を渡したときに 404 になることを確かめるメソッド
NOT_YOURS_ROUTES = [
    ("get", "/events/{e}/"),
    ("get", "/events/{e}/record-sheet/"),
    ("post", "/events/{e}/record-sheet/"),
    ("post", "/events/{e}/record/"),
    ("get", "/events/{e}/edit/"),
    ("post", "/events/{e}/edit/"),
    ("get", "/events/{e}/remove/"),
    ("post", "/events/{e}/remove/"),
    ("post", "/events/{e}/restore/"),
    ("post", "/events/{e}/move/"),
    ("get", "/logs/{l}/edit/"),
    ("post", "/logs/{l}/edit/"),
    ("post", "/logs/{l}/delete/"),
    ("get", "/logs/{l}/share/"),
]


# 取り消しは再送に備えて「何も起きない」で返す（404 にはしない）。下のテストで別に確かめている
UNDO_ROUTE = "/logs/{l}/undo/"


def test_IDを受け取るURLは_すべて他人のデータのテストに入っている():
    """URL を足したのにテストを足し忘れる、を防ぐ（レビュー S4）。"""
    from apps.web.urls import urlpatterns

    routes = {"/" + str(p.pattern) for p in urlpatterns if "<uuid:" in str(p.pattern)}
    with_id = {r.replace("<uuid:event_id>", "{e}").replace("<uuid:log_id>", "{l}") for r in routes}
    assert with_id == {path for _, path in NOT_YOURS_ROUTES} | {UNDO_ROUTE}


@pytest.mark.parametrize("method,path", NOT_YOURS_ROUTES)
def test_他人のイベントと記録は404(client_in, theirs, method, path):
    e, lid = theirs
    r = getattr(client_in, method)(path.format(e=e.id, l=lid), {"log_id": str(uuid.uuid4()), "action": "delete"})
    assert r.status_code == 404
    assert Event.objects.filter(id=e.id).exists() and Log.objects.filter(id=lid).exists()


def test_他人の記録の取り消しは何も起きない(client_in, theirs):
    _, lid = theirs
    assert client_in.post(f"/logs/{lid}/undo/").json() == {"tile_html": None}
    assert Log.objects.filter(id=lid).exists()


@pytest.mark.parametrize("action", ["up", "down", "rename", "delete"])
def test_他人や存在しないカテゴリの操作は404(client_in, other_user, action):
    theirs = ev_svc.create_category(other_user, "趣味")
    for cid in (theirs.id, uuid.uuid4()):
        r = client_in.post("/categories/", {"action": action, "id": str(cid), "name": "x"})
        assert r.status_code == 404


def test_並べ替えの位置に他人のイベントを渡すと422(client_in, user, theirs, event):
    other, _ = theirs
    assert client_in.post(f"/events/{event.id}/move/", {"before": str(other.id)}).status_code == 422
