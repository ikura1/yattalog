"""実績の判定を始めたか（決定 063）。

いまいる人は False で入れる（最初の判定で、満たしている実績をまとめて静かに解除するため）。
そのあと既定値を True にする（これから登録する人は、1つずつ知らせる）。
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="achievements_synced",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="user",
            name="achievements_synced",
            field=models.BooleanField(default=True),
        ),
    ]
