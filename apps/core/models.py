"""全モデル共通の部品。"""

import uuid

from django.db import models


def new_id() -> uuid.UUID:
    """時刻順に並ぶ UUID v7（決定 032）。"""
    return uuid.uuid7()


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=new_id, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
