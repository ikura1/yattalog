"""管理画面の保護（レビュー S10、決定 045）。入れるのは、決めたメールアドレスの人が、2段階認証を通したときだけ。"""

from datetime import timedelta

import freezegun
import pytest
from django.test import Client, override_settings
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts.models import User
from apps.accounts.services import sync_admin_flag
from apps.accounts.tests.test_google_login import GOOGLE_USER, login_with_google
from apps.core.testing import NOW, new_user
from apps.events.models import Event, Log
from apps.events.services import events as ev_svc

ADMIN = "/admin/"  # テストでの管理画面の URL（本番では推測しにくい値にしている）
OTP = "/admin/otp/"
BOSS = "boss@example.com"

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("admin_emails")]


@pytest.fixture
def admin_emails():
    with override_settings(ADMIN_EMAILS=[BOSS]):
        yield


@pytest.fixture
def boss():
    return sync_admin_flag(new_user(email=BOSS))


@pytest.fixture
def boss_client(boss):
    c = Client()
    c.force_login(boss)
    return c


def code_for(user) -> str:
    d = TOTPDevice.objects.get(user=user)
    return f"{totp(d.bin_key, step=d.step, t0=d.t0, digits=d.digits):06d}"


def enroll(client, user):
    """初回の登録：画面を開いて鍵を作り、正しいコードを入れる。"""
    client.get(OTP)
    return client.post(OTP, {"code": code_for(user)})


# --- だれが入れるか ---


def test_ログインしていなければ_ログイン画面へ送る(client):
    for path in (ADMIN, OTP):
        r = client.get(path)
        assert r.status_code == 302 and r["Location"].startswith("/login/")


def test_管理者でない人には_管理画面があることも見せない(client, user):
    client.force_login(user)
    assert [client.get(p).status_code for p in (ADMIN, OTP, ADMIN + "accounts/user/")] == [404, 404, 404]
    assert client.post(OTP, {"code": "123456"}).status_code == 404
    assert not TOTPDevice.objects.exists()


def test_管理者でも_2段階認証を通すまでは入れない(boss_client):
    r = boss_client.get(ADMIN)
    assert r.status_code == 302 and r["Location"] == OTP
    assert boss_client.get(ADMIN + "accounts/user/")["Location"] == OTP


def test_パスワードでは入れない(client, boss):
    boss.set_password("correct horse battery staple")
    boss.save()

    r = client.post(ADMIN + "login/", {"username": BOSS, "password": "correct horse battery staple"})

    assert r.status_code == 302 and r["Location"].startswith("/login/")
    assert client.get(ADMIN).status_code == 302


# --- 2段階認証 ---


def test_はじめて開くと_認証アプリに登録する鍵が出る(boss_client, boss):
    body = boss_client.get(OTP).content.decode()

    device = TOTPDevice.objects.get(user=boss)
    assert not device.confirmed
    assert "otpauth://totp/" in body and "認証アプリ" in body and 'name="code"' in body


def test_正しいコードを入れると_登録が済んで管理画面に入れる(boss_client, boss):
    r = enroll(boss_client, boss)

    assert r.status_code == 302 and r["Location"] == ADMIN
    assert TOTPDevice.objects.get(user=boss).confirmed
    assert boss_client.get(ADMIN).status_code == 200


def test_間違ったコードでは入れない(boss_client, boss):
    boss_client.get(OTP)

    r = boss_client.post(OTP, {"code": "000000"})

    assert r.status_code == 200 and "コードが違います" in r.content.decode()
    assert not TOTPDevice.objects.get(user=boss).confirmed
    assert boss_client.get(ADMIN)["Location"] == OTP


def test_登録が済んだあとは_鍵をもう見せない(boss_client, boss):
    enroll(boss_client, boss)
    other_session = Client()
    other_session.force_login(boss)

    body = other_session.get(OTP).content.decode()

    assert "otpauth://" not in body and 'name="code"' in body
    assert TOTPDevice.objects.filter(user=boss).count() == 1


def test_別の端末では_あらためてコードが要る(boss_client, boss):
    enroll(boss_client, boss)
    laptop = Client()
    laptop.force_login(boss)
    assert laptop.get(ADMIN)["Location"] == OTP

    with freezegun.freeze_time(NOW + timedelta(seconds=90)):  # 同じコードは2回使えないので、次のコードで
        r = laptop.post(OTP, {"code": code_for(boss)})
        assert r["Location"] == ADMIN and laptop.get(ADMIN).status_code == 200


def test_同じコードは_2回使えない(boss_client, boss):
    enroll(boss_client, boss)
    laptop = Client()
    laptop.force_login(boss)

    r = laptop.post(OTP, {"code": code_for(boss)})  # 時計は止まっているので、登録に使ったのと同じコード

    assert r.status_code == 200 and laptop.get(ADMIN)["Location"] == OTP


# --- 管理者の決め方 ---


def test_管理者かどうかは_設定のメールアドレスで決まり_Google_でログインしたときにそろえる(rf):
    with override_settings(ADMIN_EMAILS=[GOOGLE_USER["email"].upper()]):
        login_with_google(rf, GOOGLE_USER)
        user = User.objects.get()
        assert (user.is_staff, user.is_superuser) == (True, True)

    with override_settings(ADMIN_EMAILS=[]):
        login_with_google(rf, GOOGLE_USER)
        user.refresh_from_db()
        assert (user.is_staff, user.is_superuser) == (False, False)


def test_ふつうに登録した人は_管理者にならない(rf):
    login_with_google(rf, GOOGLE_USER)
    assert not User.objects.get().is_staff


def test_設定から外すと_2段階認証を通していても_すぐ入れなくなる(boss_client, boss):
    enroll(boss_client, boss)
    assert boss_client.get(ADMIN).status_code == 200

    with override_settings(ADMIN_EMAILS=[]):
        assert boss_client.get(ADMIN).status_code == 404


# --- 管理画面でできること ---


@pytest.fixture
def inside(boss_client, boss):
    enroll(boss_client, boss)
    return boss_client


def test_ユーザーの一覧には_メールアドレスと件数だけが出て_記録の中身は出ない(inside):
    someone = new_user(email="someone@example.com")
    e = ev_svc.create_event(someone, name="ひみつの習慣", emoji="🤫", color="pink")
    Log.objects.create(id=e.id, space=e.space, event=e, local_date=NOW.date(), memo="ないしょのメモ")

    body = inside.get(ADMIN + "accounts/user/").content.decode()

    assert "someone@example.com" in body
    assert "ひみつの習慣" not in body and "ないしょのメモ" not in body


def test_イベントや記録を見る画面は_用意しない(inside):
    assert inside.get(ADMIN + "events/event/").status_code == 404
    assert inside.get(ADMIN + "events/log/").status_code == 404


def test_管理画面からユーザーを消すと_その人のデータもすべて消える(inside, boss):
    someone = new_user(email="someone@example.com")
    ev_svc.create_event(someone, name="シーツ交換", emoji="🛏️", color="sky")

    r = inside.post(ADMIN + f"accounts/user/{someone.id}/delete/", {"post": "yes"})

    assert r.status_code == 302
    assert list(User.objects.values_list("email", flat=True)) == [BOSS] and not Event.objects.exists()


def test_管理画面から_ユーザーを作ることはできない(inside):
    assert inside.get(ADMIN + "accounts/user/add/").status_code == 403


def test_ポリシーに_運営者がデータを見る条件を書いている(client):
    body = client.get("/privacy/").content.decode()
    assert "問い合わせへの対応" in body and "閲覧する" in body


def test_管理画面に_2段階認証の鍵を見る画面は置かない(inside, boss):
    """django-otp は、鍵の一覧と QR コードの画面を管理画面に足す。登録が済んだ鍵は、どこにも出さない。"""
    device = TOTPDevice.objects.get(user=boss)

    assert inside.get(ADMIN + "otp_totp/totpdevice/").status_code == 404
    assert inside.get(ADMIN + f"otp_totp/totpdevice/{device.id}/change/").status_code == 404
    assert device.key not in inside.get(ADMIN).content.decode()
    assert "otp_totp" not in inside.get(ADMIN).content.decode()
