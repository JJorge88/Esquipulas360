from django.apps import AppConfig

class ToursConfig(AppConfig):
    name = "tours"

    def ready(self):
        from . import checks  # noqa: F401
