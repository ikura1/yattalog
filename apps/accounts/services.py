"""アカウントの処理（退会）。"""

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
