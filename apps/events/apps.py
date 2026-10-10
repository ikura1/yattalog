from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = "apps.events"
    verbose_name = "イベント"

    def ready(self) -> None:
        from django.db.models import CharField, TextField
        from django.db.models.functions import Length

        CharField.register_lookup(Length)
        TextField.register_lookup(Length)
