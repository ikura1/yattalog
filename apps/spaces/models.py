from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Space(BaseModel):
    """イベント・カテゴリ・記録の持ち主（決定 004・032）。v1 はユーザーごとの個人用スペースだけ。"""

    class Kind(models.TextChoices):
        PERSONAL = "personal", "個人"

    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.PERSONAL)
    name = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = "スペース"
        verbose_name_plural = "スペース"

    def __str__(self) -> str:
        return self.name or f"space {self.id}"


class SpaceMember(BaseModel):
    class Role(models.TextChoices):
        OWNER = "owner", "オーナー"

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OWNER)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["space", "user"], name="uniq_space_member")]
