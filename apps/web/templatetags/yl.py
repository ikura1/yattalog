from datetime import date

from django import template

from apps.events.models import Log
from apps.events.services.dates import zone

register = template.Library()


@register.filter
def log_when(log: Log, today: date) -> str:
    """記録の日時。時刻ありの記録は、記録したときのタイムゾーンでの時刻を出す（決定 026）。"""
    d = log.local_date
    s = f"{d.month:02d}/{d.day:02d}" if d.year == today.year else f"{d.year}/{d.month:02d}/{d.day:02d}"
    if log.occurred_at:
        t = log.occurred_at.astimezone(zone(log.timezone))
        s += f" {t.hour:02d}:{t.minute:02d}"
    return s


@register.filter
def rel_day(d: date, today: date) -> str:
    diff = (today - d).days
    if diff == 0:
        return "今日"
    if diff == 1:
        return "昨日"
    if diff == 2:
        return "一昨日"
    return f"{d.month}月{d.day}日"


@register.filter
def iso(d: date) -> str:
    return d.isoformat() if d else ""
