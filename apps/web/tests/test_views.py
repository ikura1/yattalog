import json
import uuid

import pytest

from apps.events.models import Log
from apps.events.services import events as ev_svc


@pytest.fixture
def client_in(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def event(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")


def test_home_requires_login(client, db):
    r = client.get("/")
    assert r.status_code == 302 and "/login/" in r["Location"]


def test_login_page_renders(client, db):
    r = client.get("/login/")
    assert r.status_code == 200 and "Google でログイン" in r.content.decode()


def test_home_lists_events(client_in, event):
    r = client_in.get("/")
    body = r.content.decode()
    assert r.status_code == 200 and "シーツ交換" in body and "まだ" in body


def test_csp_blocks_inline_scripts(client_in, event):
    r = client_in.get("/")
    csp = r["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp


def test_record_endpoint_is_idempotent(client_in, event):
    lid = str(uuid.uuid4())
    r1 = client_in.post(f"/events/{event.id}/record/", {"log_id": lid})
    r2 = client_in.post(f"/events/{event.id}/record/", {"log_id": lid})
    assert r1.status_code == 200 and r1.json()["created"] is True
    assert r2.status_code == 200 and r2.json()["created"] is False
    assert Log.objects.count() == 1
    assert "今日" in r1.json()["tile_html"]


def test_record_rejects_bad_id(client_in, event):
    assert client_in.post(f"/events/{event.id}/record/", {"log_id": "x"}).status_code == 400


def test_undo(client_in, event):
    lid = str(uuid.uuid4())
    client_in.post(f"/events/{event.id}/record/", {"log_id": lid})
    r = client_in.post(f"/logs/{lid}/undo/")
    assert r.status_code == 200 and Log.objects.count() == 0


def test_other_users_event_is_404(client, other_user, event):
    client.force_login(other_user)
    assert client.get(f"/events/{event.id}/").status_code == 404
    assert client.post(f"/events/{event.id}/record/", {"log_id": str(uuid.uuid4())}).status_code == 404
    assert client.get(f"/events/{event.id}/record-sheet/").status_code == 404
    assert client.post(f"/events/{event.id}/remove/", {"action": "delete"}).status_code == 404


def test_record_sheet_past_date(client_in, event):
    r = client_in.post(
        f"/events/{event.id}/record-sheet/",
        {"log_id": str(uuid.uuid4()), "when": "pick", "date": "2026-01-02", "time": "", "memo": "メモ"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    trig = json.loads(r["HX-Trigger"])
    assert trig["yl:changed"] and trig["yl:close-sheet"]
    log = Log.objects.get()
    assert str(log.local_date) == "2026-01-02" and log.occurred_at is None and log.memo == "メモ"


def test_record_sheet_future_date_shows_error(client_in, event):
    r = client_in.post(
        f"/events/{event.id}/record-sheet/",
        {"log_id": str(uuid.uuid4()), "when": "pick", "date": "2999-01-01"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200 and "未来の日付" in r.content.decode()
    assert Log.objects.count() == 0


def test_event_new_and_detail(client_in, user):
    r = client_in.post(
        "/events/new/",
        {"name": "散髪", "emoji": "✂️", "color": "grape", "streak_unit": "month", "last_done": "2026-09-01"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    from apps.events.models import Event

    e = Event.objects.get(name="散髪")
    d = client_in.get(f"/events/{e.id}/")
    assert d.status_code == 200 and "よくやる時期" in d.content.decode()


def test_timezone_setting(client_in, user):
    r = client_in.post("/timezone/", {"tz": "America/Los_Angeles"})
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.timezone == "America/Los_Angeles" and user.onboarded_at is not None
    assert client_in.post("/timezone/", {"tz": "Not/AZone"}).status_code == 400


def test_logout_is_post_only(client_in):
    assert client_in.get("/logout/").status_code == 405
    r = client_in.post("/logout/")
    assert r.status_code == 302 and "Clear-Site-Data" in r
