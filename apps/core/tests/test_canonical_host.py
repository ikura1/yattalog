"""独自のドメインへの寄せ（yattalog.ikura1.dev、決定 064）。古い run.app に来た人を、新しいドメインへ送る。"""

from django.test import override_settings

OLD = "yattalog-332057063162.asia-southeast1.run.app"
NEW = "yattalog.ikura1.dev"
HOSTS = [OLD, NEW, "testserver"]


@override_settings(ALLOWED_HOSTS=HOSTS, CANONICAL_HOST=NEW)
def test_古いホストに来たら_同じ道のりのまま新しいドメインへ送る(client, db):
    r = client.get("/terms/?from=x", HTTP_HOST=OLD)
    assert r.status_code == 301 and r["Location"] == f"https://{NEW}/terms/?from=x"


@override_settings(ALLOWED_HOSTS=HOSTS, CANONICAL_HOST=NEW)
def test_新しいドメインに来たら_そのまま出す(client, db):
    assert client.get("/terms/", HTTP_HOST=NEW).status_code == 200


@override_settings(ALLOWED_HOSTS=HOSTS, CANONICAL_HOST=NEW)
def test_死活監視の_health_は_どちらのホストでも送らない(client, db):
    assert client.get("/health", HTTP_HOST=OLD).status_code == 200


@override_settings(ALLOWED_HOSTS=HOSTS, CANONICAL_HOST=NEW)
def test_送るのは_読むだけの操作だけ_書き込みは送らない(client, db):
    """POST を 301 で送ると、ブラウザは中身を捨てて GET でやり直す。開いたままの画面からの記録を失わないように。"""
    assert client.post("/timezone/", HTTP_HOST=OLD).status_code != 301


@override_settings(ALLOWED_HOSTS=HOSTS, CANONICAL_HOST="")
def test_寄せ先を決めていなければ_何もしない(client, db):
    assert client.get("/terms/", HTTP_HOST=OLD).status_code == 200
