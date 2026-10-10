"""ソートキーの列を "C" 照合にする（PostgreSQL のみ）。

分数インデックスのキーは ASCII のバイト順で比較する前提なので、
en_US.UTF-8 などの照合（大文字小文字を区別しない辞書順）では並び順が変わってしまう。
SQLite の既定（BINARY）はもともとバイト順なので何もしない。
"""

from django.db import migrations

TABLES = ["events_event", "events_category"]


def to_c(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for t in TABLES:
        schema_editor.execute(f'ALTER TABLE {t} ALTER COLUMN sort_key TYPE varchar(64) COLLATE "C"')


def to_default(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for t in TABLES:
        schema_editor.execute(f'ALTER TABLE {t} ALTER COLUMN sort_key TYPE varchar(64) COLLATE "default"')


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]
    operations = [migrations.RunPython(to_c, to_default)]
