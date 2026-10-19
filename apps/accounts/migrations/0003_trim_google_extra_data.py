"""保存済みの Google の情報を、ポリシーに書いた項目（ID、メールアドレス、表示名）だけにする。"""

from django.db import migrations

GOOGLE_KEPT_FIELDS = ("sub", "email", "email_verified", "name")  # adapters.GOOGLE_KEPT_FIELDS と同じ


def trim_extra_data(apps, schema_editor):
    SocialAccount = apps.get_model("socialaccount", "SocialAccount")
    for account in SocialAccount.objects.filter(provider="google"):
        kept = {k: v for k, v in (account.extra_data or {}).items() if k in GOOGLE_KEPT_FIELDS}
        if kept != account.extra_data:
            account.extra_data = kept
            account.save(update_fields=["extra_data"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_achievements_synced"),
        ("socialaccount", "0006_alter_socialaccount_extra_data"),
    ]

    operations = [migrations.RunPython(trim_extra_data, migrations.RunPython.noop)]
