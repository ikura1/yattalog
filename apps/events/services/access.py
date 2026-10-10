"""権限つきの取得（レビュー S4）。ユーザーがメンバーでないスペースのものは「存在しない」扱いにする。

events.py と logs.py の両方から使うので、ここに分けて循環 import をなくしている。
"""

from django.core.exceptions import ValidationError

from apps.events.models import Category, Event, Log


def event_for(user, event_id, *, lock: bool = False) -> Event:
    qs = Event.objects.select_for_update(of=("self",)) if lock else Event.objects
    try:
        return qs.get(id=event_id, space__members__user=user)
    except Event.DoesNotExist, ValueError, ValidationError:
        raise Event.DoesNotExist from None


def log_for(user, log_id) -> Log:
    try:
        return Log.objects.select_related("event").get(id=log_id, space__members__user=user)
    except Log.DoesNotExist, ValueError, ValidationError:
        raise Log.DoesNotExist from None


def category_for(user, category_id) -> Category:
    try:
        return Category.objects.get(id=category_id, space__members__user=user)
    except Category.DoesNotExist, ValueError, ValidationError:
        raise Category.DoesNotExist from None
