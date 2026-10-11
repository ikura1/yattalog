"""スペースと権限のサービス層（決定 027、レビュー S4）。"""

from django.db import transaction
from django.http import Http404

from apps.spaces.models import Space, SpaceMember


@transaction.atomic
def ensure_personal_space(user) -> Space:
    """ユーザーの個人用スペースを返す。なければ作る。"""
    member = SpaceMember.objects.select_related("space").filter(user=user, space__kind=Space.Kind.PERSONAL).first()
    if member:
        return member.space
    space = Space.objects.create(kind=Space.Kind.PERSONAL)
    SpaceMember.objects.create(space=space, user=user, role=SpaceMember.Role.OWNER)
    return space


def personal_space(user) -> Space:
    space = Space.objects.filter(members__user=user, kind=Space.Kind.PERSONAL).first()
    if space is None:
        space = ensure_personal_space(user)
    return space


def require_member(user, space_id) -> Space:
    """ユーザーがメンバーでないスペースは「存在しない」扱いにする（404）。"""
    try:
        return Space.objects.get(id=space_id, members__user=user)
    except Space.DoesNotExist, ValueError:
        raise Http404 from None
