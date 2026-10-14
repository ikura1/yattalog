"""シェアの画面（SPEC 3.8、決定 053）。"""

import uuid
from datetime import timedelta

from apps.core.testing import TODAY
from apps.events.services import logs as log_svc
from apps.events.services.logs import When


def test_シェアのシートには_画像を作る材料と_投稿文と_X_への入口がある(client_in, user, event):
    lid = uuid.uuid4()
    log_svc.record(user, event.id, lid, memo="冬用に替えた")

    body = client_in.get(f"/logs/{lid}/share/").content.decode()

    assert 'id="shareCard"' in body and 'data-name="シーツ交換"' in body and 'data-headline="はじめての記録"' in body
    assert 'data-color="sky"' in body and 'data-memo="冬用に替えた"' in body
    assert "投稿文" in body and "#Yattalog" in body
    assert 'href="https://x.com/intent/post?text=' in body and "メモも載せる" in body


def test_メモのない記録では_メモを載せるチェックは選べない(client_in, user, event):
    lid = uuid.uuid4()
    log_svc.record(user, event.id, lid)

    assert 'id="shareMemo" disabled' in client_in.get(f"/logs/{lid}/share/").content.decode()


def test_詳細画面と履歴から_シェアを開ける(client_in, user, event):
    lid = uuid.uuid4()
    log_svc.record(user, event.id, lid)

    body = client_in.get(f"/events/{event.id}/").content.decode()

    assert body.count(f'hx-get="/logs/{lid}/share/"') == 2  # 見出しの「シェア」と、履歴の行の「シェア」


def test_記録がないイベントの詳細には_シェアを出さない(client_in, event):
    assert "/share/" not in client_in.get(f"/events/{event.id}/").content.decode()


def test_記録したときの返事に_シェアの入口を入れる(client_in, event):
    lid = str(uuid.uuid4())
    data = client_in.post(f"/events/{event.id}/record/", {"log_id": lid}).json()
    assert data["share_url"] == f"/logs/{lid}/share/"


def test_連続記録のときは_通算の回数を添え書きとして画像に渡す(client_in, user, event):
    for days in (14, 7):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=TODAY - timedelta(days)))
    lid = uuid.uuid4()
    log_svc.record(user, event.id, lid)

    body = client_in.get(f"/logs/{lid}/share/").content.decode()

    assert 'data-headline="🔥 3週連続"' in body and 'data-sub="通算 3回目"' in body
    assert "シェア画像のプレビュー：シーツ交換、やった！、🔥 3週連続、通算 3回目" in body
