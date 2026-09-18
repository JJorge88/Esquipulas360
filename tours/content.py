"""Structured content, validation and URL resolution; no template-owned tour data."""
import json
import math
import re
import unicodedata
from pathlib import PurePosixPath
from django.conf import settings
from django.templatetags.static import static

CONTENT_FILE = settings.BASE_DIR / "content" / "tours.json"
CATEGORIES = {"demostracion": "Demostración", "vistas": "Vistas", "patrimonio": "Patrimonio", "espacios": "Espacios públicos"}
STATUS_LABELS = {"demo": "Demostración", "available": "Disponible", "upcoming": "Próximamente"}

class ContentError(ValueError):
    pass

def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))

def require(condition, message):
    if not condition:
        raise ContentError(message)

def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value)

def asset_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "?" in value or "#" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def validate_content(tours):
    require(isinstance(tours, list) and bool(tours), "El catálogo debe ser una lista no vacía.")
    ids, slugs = set(), set()
    for tour in tours:
        require(isinstance(tour, dict), "Recorrido inválido.")
        for key, seen in (("id", ids), ("slug", slugs)):
            value = tour.get(key)
            require(identifier(value) and value not in seen, f"{key} inválido o duplicado: {value}")
            seen.add(value)
        require(all(isinstance(tour.get(k), str) and tour[k].strip() for k in ("name", "description")), "Nombre y descripción requeridos.")
        require(isinstance(tour.get("category"), str) and tour["category"] in CATEGORIES, "Categoría desconocida.")
        require(isinstance(tour.get("status"), str) and tour["status"] in STATUS_LABELS, "Estado desconocido.")
        require(not tour.get("cover") or asset_path(tour["cover"]), "Portada inválida.")
        scenes = tour.get("scenes")
        require(isinstance(scenes, list), "Escenas debe ser una lista.")
        scene_ids = set()
        for scene in scenes:
            require(isinstance(scene, dict), "Escena inválida.")
            sid = scene.get("id")
            require(identifier(sid) and sid not in scene_ids, f"ID de escena inválido o duplicado: {sid}")
            scene_ids.add(sid)
            require(isinstance(scene.get("name"), str) and bool(scene["name"].strip()), "Nombre de escena requerido.")
            require(asset_path(scene.get("panorama")), f"Panorama inválido: {sid}")
            orientation = scene.get("orientation", {})
            require(isinstance(orientation, dict), "Orientación inválida.")
            require(number(orientation.get("yaw")) and -180 <= orientation["yaw"] <= 180, "Yaw fuera de rango.")
            require(number(orientation.get("pitch")) and -90 <= orientation["pitch"] <= 90, "Pitch fuera de rango.")
            require(not scene.get("audio") or asset_path(scene["audio"]), "Audio inválido.")
            require(isinstance(scene.get("text", ""), str), "Texto inválido.")
            hotspots = scene.get("hotspots")
            require(isinstance(hotspots, list), "Puntos interactivos debe ser una lista.")
            hids = set()
            for hotspot in hotspots:
                require(isinstance(hotspot, dict), "Punto inválido.")
                hid = hotspot.get("id")
                require(identifier(hid) and hid not in hids, "ID de punto inválido o duplicado.")
                hids.add(hid)
                require(isinstance(hotspot.get("label"), str) and bool(hotspot["label"].strip()), "Etiqueta de punto requerida.")
                pos = hotspot.get("position")
                require(isinstance(pos, list) and len(pos) == 3 and all(number(n) for n in pos) and sum(n*n for n in pos) > 0, "Posición de punto inválida.")
        if tour["status"] == "upcoming":
            require(not scenes and tour.get("initial_scene") is None, "Un próximo recorrido no debe exponer escenas.")
        else:
            require(bool(scenes) and identifier(tour.get("initial_scene")) and tour["initial_scene"] in scene_ids, "Escena inicial inexistente.")
        for scene in scenes:
            for hotspot in scene["hotspots"]:
                require(identifier(hotspot.get("destination")) and hotspot["destination"] in scene_ids, f"Destino inexistente: {hotspot.get('destination')}")
    return tours

def load_tours():
    with CONTENT_FILE.open(encoding="utf-8") as source:
        return validate_content(json.load(source))

def asset_url(path):
    return settings.MEDIA_URL + path[6:] if path.startswith("media/") else static(path)

def present(tour):
    return {**tour, "category_label": CATEGORIES[tour["category"]], "status_label": STATUS_LABELS[tour["status"]], "cover_url": asset_url(tour["cover"]) if tour.get("cover") else None}

def filter_tours(tours, query="", category=""):
    words = normalized(query).split()
    return [tour for tour in tours if (not category or tour["category"] == category) and all(word in normalized(f"{tour['name']} {tour['description']} {CATEGORIES[tour['category']]}") for word in words)]

def viewer_data(tour):
    return {**tour, "scenes": [{**s, "panorama": asset_url(s["panorama"]), "audio": asset_url(s["audio"]) if s.get("audio") else None} for s in tour["scenes"]]}
