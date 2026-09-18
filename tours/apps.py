from django.apps import AppConfig

class ToursConfig(AppConfig):
    name = "tours"
    verbose_name = "Contenido de Esquipulas 360°"

    def ready(self):
        from . import checks  # noqa: F401
