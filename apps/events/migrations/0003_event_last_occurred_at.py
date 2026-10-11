from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def fill_last_occurred_at(apps, schema_editor):
    """すでにある記録から、最終記録日の最新の時刻を入れる（refresh_event_cache と同じ規則）。"""
    Event = apps.get_model("events", "Event")
    Log = apps.get_model("events", "Log")
    latest = (
        Log.objects.filter(event=OuterRef("pk"), local_date=OuterRef("last_local_date"), occurred_at__isnull=False)
        .order_by("-occurred_at")
        .values("occurred_at")[:1]
    )
    Event.objects.filter(last_local_date__isnull=False).update(last_occurred_at=Subquery(latest))


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0002_sort_key_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="last_occurred_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(fill_last_occurred_at, migrations.RunPython.noop),
    ]
