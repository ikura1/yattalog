from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel
from apps.spaces.models import Space

COLORS = ["tomato", "tangerine", "sun", "leaf", "teal", "sky", "grape", "pink"]


class SortKeyField(models.CharField):
    """並び順のキー（分数インデックス）の列。

    キーは ASCII のバイト順で比較する前提なので、PostgreSQL では列を "C" 照合にする。
    照合をフィールド自身に持たせることで、Django が生成するマイグレーションでも照合が保たれる。
    SQLite の既定（BINARY）はもともとバイト順なので何もしない。
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 64)
        super().__init__(*args, **kwargs)

    def db_parameters(self, connection):
        params = super().db_parameters(connection)
        if connection.vendor == "postgresql":
            params["collation"] = "C"
        return params


class StreakUnit(models.TextChoices):
    NONE = "none", "なし"
    DAY = "day", "毎日"
    WEEK = "week", "毎週"
    MONTH = "month", "毎月"


class Category(BaseModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=20)
    sort_key = SortKeyField()

    class Meta:
        verbose_name = "カテゴリ"
        verbose_name_plural = "カテゴリ"
        ordering = ["sort_key"]
        constraints = [models.UniqueConstraint(fields=["space", "name"], name="uniq_category_name")]
        indexes = [models.Index(fields=["space", "sort_key"])]

    def __str__(self) -> str:
        return self.name


class Event(BaseModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="events")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    name = models.CharField(max_length=40)
    emoji = models.CharField(max_length=16)
    color = models.CharField(max_length=16, choices=[(c, c) for c in COLORS], default="sky")
    streak_unit = models.CharField(max_length=8, choices=StreakUnit.choices, default=StreakUnit.DAY)
    sort_key = SortKeyField()
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    # --- キャッシュ（記録の追加・編集・削除のときにサービス層で更新する、決定 032）---
    last_local_date = models.DateField(null=True, blank=True)
    last_occurred_at = models.DateTimeField(null=True, blank=True)  # 最終記録日の、時刻ありの記録のうち最新の時刻
    log_count = models.PositiveIntegerField(default=0)
    streak_count = models.PositiveIntegerField(default=0)
    streak_period = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "イベント"
        verbose_name_plural = "イベント"
        ordering = ["sort_key"]
        constraints = [
            models.CheckConstraint(condition=Q(color__in=COLORS), name="event_color_valid"),
            models.CheckConstraint(condition=Q(streak_unit__in=StreakUnit.values), name="event_streak_unit_valid"),
        ]
        indexes = [
            models.Index(fields=["space", "is_archived", "sort_key"]),
            models.Index(fields=["space", "category", "is_archived", "sort_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.emoji} {self.name}"


class Log(BaseModel):
    """「いつやったか」の1回分。ID は端末で作る（決定 028）。"""

    class Source(models.TextChoices):
        APP = "app", "アプリ"
        AI = "ai", "AI"
        URL = "url", "記録用 URL"

    id = models.UUIDField(primary_key=True, editable=False)  # 端末が作った UUID をそのまま使う
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="logs")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="logs")
    local_date = models.DateField()  # 記録したときのタイムゾーンでの日付。後から変えない（決定 026）
    occurred_at = models.DateTimeField(null=True, blank=True)  # 時刻ありの記録だけ
    timezone = models.CharField(max_length=64, blank=True, default="")  # 時刻ありの記録だけ
    memo = models.TextField(blank=True, default="")
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.APP)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "記録"
        verbose_name_plural = "記録"
        ordering = ["-local_date", models.F("occurred_at").desc(nulls_last=True), "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(occurred_at__isnull=True) & Q(timezone=""))
                | (Q(occurred_at__isnull=False) & ~Q(timezone="")),
                name="log_time_and_timezone_together",
            ),
            models.CheckConstraint(condition=Q(memo__length__lte=1000), name="log_memo_max_1000"),
            models.CheckConstraint(condition=Q(source__in=["app", "ai", "url"]), name="log_source_valid"),
        ]
        indexes = [
            models.Index(fields=["event", "-local_date", "-occurred_at"], name="log_event_date_idx"),
            models.Index(fields=["space", "local_date"], name="log_space_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_id} @ {self.local_date}"

    @property
    def has_time(self) -> bool:
        return self.occurred_at is not None
