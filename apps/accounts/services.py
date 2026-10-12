"""アカウントの処理（退会、管理者かどうか）。"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.spaces.models import Space


@transaction.atomic
def delete_account(user) -> None:
    """退会。ユーザーと、その人の個人用スペースのデータをすべて消す（SPEC 3.11.3、決定 040）。

    スペースを消すと、カテゴリ・イベント・記録も一緒に消える。ユーザーを消すと、Google との連携情報も消える。
    セッションはユーザーに結びついているので、ほかの端末のログインも使えなくなる。
    """
    Space.objects.filter(members__user=user, kind=Space.Kind.PERSONAL).delete()
    user.delete()


def is_admin(user) -> bool:
    """管理者かどうか。設定（ADMIN_EMAILS）にあるメールアドレスの人だけ（決定 045）。

    メールアドレスは、Google が確認済みとしたものだけを登録している（adapters.py）。
    """
    if not (user.is_authenticated and user.is_active):
        return False
    return user.email.lower() in {e.lower() for e in settings.ADMIN_EMAILS}


def sync_admin_flag(user):
    """Django の権限の印（is_staff / is_superuser）を、設定に合わせる。外した人からは取り上げる。

    渡されたオブジェクトの値は古いことがある（ログインの途中など）ので、DB の値と比べて直す。
    """
    wanted = is_admin(user)
    stale = get_user_model().objects.filter(pk=user.pk).exclude(is_staff=wanted, is_superuser=wanted)
    stale.update(is_staff=wanted, is_superuser=wanted)
    user.is_staff = user.is_superuser = wanted
    return user
