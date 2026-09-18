from django.core.checks import Error, register
from .content import ContentError, load_tours

@register()
def check_tours(app_configs, **kwargs):
    try:
        load_tours()
    except (ContentError, OSError, ValueError) as exc:
        return [Error(str(exc), id="tours.E001")]
    return []
