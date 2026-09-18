from django.core.checks import Error, register
from django.conf import settings
import math

@register()
def check_upload_limits(app_configs, **kwargs):
    errors = []
    for name in ("COVER_MAX_BYTES", "PANORAMA_MAX_BYTES", "COVER_MIN_WIDTH", "COVER_MIN_HEIGHT", "PANORAMA_MIN_WIDTH", "PANORAMA_MIN_HEIGHT", "IMAGE_MAX_DIMENSION", "IMAGE_MAX_PIXELS"):
        if getattr(settings, name) <= 0:
            errors.append(Error(f"{name} debe ser positivo.", id="tours.E002"))
    tolerance = settings.PANORAMA_RATIO_TOLERANCE
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 0.05:
        errors.append(Error("PANORAMA_RATIO_TOLERANCE debe estar entre 0 y 0.05.", id="tours.E003"))
    return errors
