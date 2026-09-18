"""Originals are immutable uploads; previews are small, disposable derivatives."""
import io
import math
import warnings
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}

def cover_path(instance, filename):
    return f"covers/originals/{uuid4().hex}{Path(filename).suffix.lower()}"

def panorama_path(instance, filename):
    return f"panoramas/originals/{uuid4().hex}{Path(filename).suffix.lower()}"

def validate_image(value, *, panorama=False):
    if not value:
        return
    prefix = "PANORAMA" if panorama else "COVER"
    formats = {"JPEG", "PNG"} if panorama else {"JPEG", "PNG", "WEBP"}
    extension_format = FORMATS.get(Path(value.name).suffix.lower())
    if extension_format not in formats:
        raise ValidationError("Usa una imagen JPEG o PNG." if panorama else "Usa una portada JPEG, PNG o WebP.")
    try:
        if value.size > getattr(settings, f"{prefix}_MAX_BYTES"):
            raise ValidationError(f"El archivo supera el máximo de {getattr(settings, f'{prefix}_MAX_BYTES') / 1048576:g} MiB.")
        value.open("rb")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            value.seek(0)
            image = Image.open(value)
            width, height = image.size
            if image.format not in formats or image.format != extension_format:
                raise ValidationError("El contenido real de la imagen no coincide con un formato permitido y su extensión.")
            if getattr(image, "is_animated", False):
                raise ValidationError("Usa una imagen estática; no se admiten imágenes animadas.")
            if width < getattr(settings, f"{prefix}_MIN_WIDTH") or height < getattr(settings, f"{prefix}_MIN_HEIGHT"):
                raise ValidationError(f"La imagen debe medir al menos {getattr(settings, f'{prefix}_MIN_WIDTH')} × {getattr(settings, f'{prefix}_MIN_HEIGHT')} píxeles.")
            if max(width, height) > settings.IMAGE_MAX_DIMENSION or width * height > settings.IMAGE_MAX_PIXELS:
                raise ValidationError(f"La imagen supera el límite de {settings.IMAGE_MAX_DIMENSION} píxeles por lado o {settings.IMAGE_MAX_PIXELS} píxeles totales.")
            if panorama and abs(width / (2 * height) - 1) > settings.PANORAMA_RATIO_TOLERANCE + 1e-12:
                raise ValidationError(f"La panorámica debe tener proporción 2:1 (tolerancia {settings.PANORAMA_RATIO_TOLERANCE * 100:g}%). Recibida: {width} × {height}.")
            image.verify()
            value.seek(0)
            # verify() checks structure; load() also rejects truncated pixel data.
            decoded = Image.open(value)
            if panorama and decoded.getexif().get(274, 1) not in (1, None):
                raise ValidationError("Exporta la panorámica con orientación EXIF normal; no debe requerir rotación automática.")
            decoded.load()
    except ValidationError:
        raise
    except (OSError, ValueError, RuntimeError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("No se pudo leer la imagen completa. El archivo falta, está dañado o no es una imagen válida.") from exc
    finally:
        try:
            value.seek(0)
        except (OSError, ValueError):
            pass

def validate_cover(value):
    validate_image(value)

def validate_panorama(value):
    validate_image(value, panorama=True)

def validate_angle(value):
    if not math.isfinite(value):
        raise ValidationError("Introduce un ángulo numérico finito.")

def thumbnail_content(original):
    try:
        original.open("rb")
        with Image.open(original) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((640, 360), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.convert("RGB").save(output, "WEBP", quality=75)
        return ContentFile(output.getvalue(), name=f"thumbnails/{uuid4().hex}.webp")
    except (OSError, ValueError):
        # A preview failure must never discard a valid original.
        return None

def file_exists(field):
    try:
        return bool(field and field.storage.exists(field.name))
    except OSError:
        return False
