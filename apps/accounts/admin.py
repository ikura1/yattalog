"""管理画面で扱うもの（決定 045）。ユーザーの一覧と、停止・削除だけ。記録の中身を見る画面は用意しない。"""

from django.contrib import admin

from apps.accounts.models import User
from apps.accounts.services import delete_account
from apps.events.models import Event, Log


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "display_name", "created_at", "last_login", "is_active", "event_count", "log_count"]
    list_filter = ["is_active"]
    search_fields = ["email", "display_name"]
    ordering = ["-created_at"]
    fields = ["email", "display_name", "timezone", "created_at", "last_login", "terms_version", "is_active"]
    readonly_fields = ["email", "display_name", "timezone", "created_at", "last_login", "terms_version"]

    @admin.display(description="イベント数")
    def event_count(self, user: User) -> int:
        return Event.objects.filter(space__members__user=user).count()

    @admin.display(description="記録数")
    def log_count(self, user: User) -> int:
        return Log.objects.filter(space__members__user=user).count()

    def has_add_permission(self, request) -> bool:
        return False  # 登録は Google ログインからだけ

    def has_delete_permission(self, request, obj=None) -> bool:
        return obj is None or obj != request.user  # 自分自身は、アプリのメニューの「退会する」から

    def delete_model(self, request, obj: User) -> None:
        delete_account(obj)  # 退会と同じ。その人のデータもすべて消す

    def delete_queryset(self, request, queryset) -> None:
        for user in queryset:
            delete_account(user)
