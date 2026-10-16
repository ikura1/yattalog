from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone as dj_timezone

from apps.core.models import new_id

TERMS_VERSION = "2026-10-12"
PRIVACY_VERSION = "2026-10-17"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, **extra):
        if not email:
            raise ValueError("email は必須です")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_unusable_password()  # パスワードは使わない（決定 016）
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)  # 管理画面用（本番では 2 段階認証を必須にする、レビュー S10）
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Yattalog のユーザー。Google ログインのみ。識別は allauth の SocialAccount.uid（Google の sub）。"""

    id = models.UUIDField(primary_key=True, default=new_id, editable=False)
    email = models.EmailField("メールアドレス", max_length=254)  # 表示と連絡用。識別には使わない
    display_name = models.CharField("表示名", max_length=100, blank=True)
    timezone = models.CharField("タイムゾーン", max_length=64, default="Asia/Tokyo")
    timezone_kept_for = models.CharField(max_length=64, blank=True)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    # 実績の判定を始めたか（決定 063）。False の人（機能が入る前からの人）は、最初の判定でまとめて静かに解除する
    achievements_synced = models.BooleanField(default=True)
    terms_version = models.CharField(max_length=20, blank=True)
    privacy_version = models.CharField(max_length=20, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=dj_timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"  # 管理用（createsuperuser）。一意制約は付けない（識別は Google の sub）
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "ユーザー"
        verbose_name_plural = "ユーザー"

    def __str__(self) -> str:
        return self.display_name or self.email
