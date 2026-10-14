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
    if d.year != today.year:
        return f"{d.year}年{d.month}月{d.day}日"
    return f"{d.month}月{d.day}日"


WEEKDAYS = "月火水木金土日"


@register.filter
def md_wd(d: date) -> str:
    """「10月10日（土）」"""
    return f"{d.month}月{d.day}日（{WEEKDAYS[d.weekday()]}）"


@register.filter
def log_time(log: Log) -> str:
    """時刻ありの記録だけ、記録したときのタイムゾーンでの時刻（「8:05」）。時刻なしなら空。"""
    if not log.occurred_at:
        return ""
    t = log.occurred_at.astimezone(zone(log.timezone))
    return f"{t.hour}:{t.minute:02d}"


@register.filter
def iso(d: date) -> str:
    return d.isoformat() if d else ""
