"""Public database queries and the stable contract consumed by the viewer."""
import unicodedata
from django.conf import settings
from django.db.models import Prefetch
from django.templatetags.static import static
from django.urls import reverse
from .images import file_exists
from .models import Tour, Scene, NavigationPoint

def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))

def asset_url(path):
    # Unchanged site-wide hero configuration only; tour content comes from models.
    return settings.MEDIA_URL + path[6:] if path.startswith("media/") else static(path)

def public_tours(request):
    if not hasattr(request, "_public_tours"):
        scenes = Scene.objects.prefetch_related(Prefetch("hotspots", queryset=NavigationPoint.objects.select_related("destination")))
        tours = Tour.objects.exclude(status=Tour.Status.DRAFT).select_related("category", "initial_scene").prefetch_related(Prefetch("scenes", queryset=scenes))
        # Fail closed if originals disappear outside Admin.
        request._public_tours = [tour for tour in tours if not tour.published or not tour.publication_errors()]
    return request._public_tours

def present(tour):
    return {
        "name": tour.name, "slug": tour.slug, "description": tour.description,
        "category": tour.category.slug, "category_label": tour.category.name,
        "status": tour.status, "status_label": "Próximamente" if tour.status == Tour.Status.UPCOMING else tour.get_status_display(),
        "cover_url": tour.thumbnail.url if file_exists(tour.thumbnail) else (tour.cover.url if file_exists(tour.cover) else None),
        "scene_count": len(tour.scenes.all()),
    }

def filter_tours(tours, query="", category=""):
    words = normalized(query).split()
    return [tour for tour in tours if (not category or tour.category.slug == category) and all(word in normalized(f"{tour.name} {tour.description} {tour.category.name}") for word in words)]

def viewer_data(tour, *, private=False, panorama_url=None):
    return {
        "name": tour.name, "description": tour.description, "status": tour.status,
        "initial_scene": tour.initial_scene.key,
        "panorama_ratio_tolerance": settings.PANORAMA_RATIO_TOLERANCE,
        "scenes": [
            {"id": scene.key, "name": scene.name, "panorama": (panorama_url(scene) if panorama_url else reverse("admin:tours_scene_panorama", args=[scene.pk])) if private else scene.panorama.url,
             "orientation": {"yaw": scene.yaw, "pitch": scene.pitch}, "text": scene.text,
             "hotspots": [{"id": point.key, "label": point.label, "destination": point.destination.key, "position": point.position()} for point in scene.hotspots.all()]}
            for scene in tour.scenes.all()
        ],
    }
