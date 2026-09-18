"""Private scene editor. All routes are additionally wrapped by AdminSite.admin_view."""
import hashlib
import json
import re
from functools import wraps

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from .content import present, viewer_data
from .images import file_exists
from .models import Scene, NavigationPoint


def can_preview(user):
    return user.is_active and user.is_staff and all(
        user.has_perm(f"tours.view_{model}") or user.has_perm(f"tours.change_{model}")
        for model in ("tour", "scene", "navigationpoint")
    )


def editor_permissions(user):
    return {"add": user.has_perm("tours.add_navigationpoint"),
            "change": user.has_perm("tours.change_navigationpoint"),
            "delete": user.has_perm("tours.delete_navigationpoint"),
            "orientation": user.has_perm("tours.change_scene")}


def can_edit(user):
    return can_preview(user) and any(editor_permissions(user).values())


def access(*, editing=True, permission=None):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            allowed = can_edit(request.user) if editing else can_preview(request.user)
            if not allowed or (permission and not request.user.has_perm(permission)):
                return JsonResponse({"error": "No tienes permiso para realizar esta operación."}, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


def revision(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, allow_nan=False).encode()).hexdigest()


def point_data(point):
    values = {"label": point.label, "destination": point.destination_id, "yaw": point.yaw, "pitch": point.pitch}
    return {**values, "id": point.pk, "key": point.key, "revision": revision(values)}


def orientation_data(scene):
    values = {"yaw": scene.yaw, "pitch": scene.pitch}
    return {**values, "revision": revision(values)}


def scene_data(scene, user):
    return {
        "scene": {"id": scene.pk, "name": scene.name, "orientation": orientation_data(scene),
                  "panorama": reverse("admin:tours_scene_panorama", args=[scene.pk]) if file_exists(scene.panorama) else None},
        "points": [point_data(p) for p in scene.hotspots.all()],
        "destinations": list(scene.tour.scenes.exclude(pk=scene.pk).values("id", "name")),
        "permissions": editor_permissions(user),
        "tolerance": settings.PANORAMA_RATIO_TOLERANCE,
        "urls": {"points": reverse("admin:tours_scene_points", args=[scene.pk]),
                 "orientation": reverse("admin:tours_scene_orientation", args=[scene.pk]),
                 "preview": reverse("admin:tours_scene_preview", args=[scene.pk])},
    }


class PointForm(forms.ModelForm):
    class Meta:
        model = NavigationPoint
        fields = ["label", "destination", "yaw", "pitch"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination"].queryset = Scene.objects.filter(tour_id=self.instance.origin.tour_id).exclude(pk=self.instance.origin_id)


def read_json(request, fields):
    if request.content_type != "application/json":
        raise ValidationError("Envía los cambios como JSON.")
    if len(request.body) > 8192:
        raise ValidationError("La solicitud es demasiado grande.")
    def invalid_constant(value):
        raise ValueError(value)
    try:
        data = json.loads(request.body, parse_constant=invalid_constant)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError("Los datos no son válidos. Los ángulos deben ser números finitos.") from exc
    if not isinstance(data, dict) or set(data) != set(fields):
        raise ValidationError("Faltan campos o la solicitud contiene campos no permitidos.")
    for angle, limit in (("yaw", 180), ("pitch", 90)):
        if angle in data and (type(data[angle]) not in (int, float) or not -limit <= data[angle] <= limit):
            raise ValidationError(f"El ángulo {angle} debe ser un número finito entre −{limit} y {limit} grados.")
    if "label" in data and not isinstance(data["label"], str):
        raise ValidationError("La etiqueta debe ser texto.")
    if "destination" in data and (type(data["destination"]) is not int or data["destination"] <= 0):
        raise ValidationError("Selecciona una escena de destino válida del mismo recorrido.")
    return data


def invalid(exc):
    errors = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
    return JsonResponse({"error": "No se guardaron los cambios. Revisa los datos.", "errors": errors}, status=400)


def conflict():
    return JsonResponse({"error": "Este contenido cambió en otra ventana. Conservamos tu edición; revisa la versión guardada en otra pestaña antes de recargar."}, status=409)


@require_GET
@access()
def page(request, scene_id):
    scene = get_object_or_404(Scene.objects.select_related("tour"), pk=scene_id)
    return render(request, "tours/editor.html", {"scene": scene, "editor_data": scene_data(scene, request.user)})


@require_GET
@access()
def data(request, scene_id):
    scene = get_object_or_404(Scene.objects.select_related("tour"), pk=scene_id)
    return JsonResponse(scene_data(scene, request.user))


@require_http_methods(["POST"])
@access(permission="tours.add_navigationpoint")
def create_point(request, scene_id):
    try:
        payload = read_json(request, ["key", "label", "destination", "yaw", "pitch"])
        if not isinstance(payload["key"], str) or not re.fullmatch(r"[0-9a-f]{32}", payload["key"]):
            raise ValidationError("Identificador de guardado inválido. Cancela y vuelve a añadir el punto.")
        with transaction.atomic():
            scene = get_object_or_404(Scene.objects.select_for_update(), pk=scene_id)
            existing = scene.hotspots.filter(key=payload["key"]).first()
            point = NavigationPoint(origin=scene, key=payload["key"])
            form = PointForm(payload, instance=point)
            if not form.is_valid():
                return JsonResponse({"error": "Revisa la etiqueta, el destino y la posición.", "errors": form.errors}, status=400)
            if existing:
                # A lost response may be retried without creating a duplicate.
                wanted = {k: getattr(form.instance, k) for k in ("label", "destination_id", "yaw", "pitch")}
                if any(getattr(existing, k) != value for k, value in wanted.items()):
                    return conflict()
                return JsonResponse({"point": point_data(existing)})
            point = form.save()
            return JsonResponse({"point": point_data(point)}, status=201)
    except ValidationError as exc:
        return invalid(exc)


@require_http_methods(["PATCH", "DELETE"])
@access()
def point_detail(request, scene_id, point_id):
    permission = "delete_navigationpoint" if request.method == "DELETE" else "change_navigationpoint"
    if not request.user.has_perm(f"tours.{permission}"):
        return JsonResponse({"error": "No tienes permiso para modificar este punto."}, status=403)
    try:
        fields = ["revision"] if request.method == "DELETE" else ["revision", "label", "destination", "yaw", "pitch"]
        payload = read_json(request, fields)
        with transaction.atomic():
            get_object_or_404(Scene.objects.select_for_update(), pk=scene_id)
            point = get_object_or_404(NavigationPoint.objects.select_for_update(), pk=point_id, origin_id=scene_id)
            current = point_data(point)
            if payload["revision"] != current["revision"]:
                if request.method == "PATCH" and all(payload[k] == current[k] for k in ("label", "destination", "yaw", "pitch")):
                    return JsonResponse({"point": current})
                return conflict()
            if request.method == "DELETE":
                point.delete()
                return JsonResponse({"deleted": point_id})
            form = PointForm(payload, instance=point)
            if not form.is_valid():
                return JsonResponse({"error": "Revisa la etiqueta, el destino y la posición.", "errors": form.errors}, status=400)
            return JsonResponse({"point": point_data(form.save())})
    except ValidationError as exc:
        return invalid(exc)


@require_http_methods(["PATCH"])
@access(permission="tours.change_scene")
def orientation(request, scene_id):
    try:
        payload = read_json(request, ["revision", "yaw", "pitch"])
        with transaction.atomic():
            scene = get_object_or_404(Scene.objects.select_for_update(), pk=scene_id)
            current = orientation_data(scene)
            if payload["revision"] != current["revision"]:
                if all(payload[k] == current[k] for k in ("yaw", "pitch")):
                    return JsonResponse({"orientation": current})
                return conflict()
            scene.yaw, scene.pitch = payload["yaw"], payload["pitch"]
            scene.save()  # Includes all phase 2 image, relationship and angle checks.
            return JsonResponse({"orientation": orientation_data(scene)})
    except ValidationError as exc:
        return invalid(exc)


@require_GET
@access(editing=False)
def panorama(request, scene_id):
    scene = get_object_or_404(Scene, pk=scene_id)
    if not file_exists(scene.panorama):
        raise Http404("Esta escena todavía no tiene panorámica.")
    try:
        return FileResponse(scene.panorama.open("rb"), content_type="image/png" if scene.panorama.name.lower().endswith(".png") else "image/jpeg")
    except OSError as exc:
        raise Http404("La panorámica no está disponible.") from exc


@require_GET
@access(editing=False)
def preview(request, scene_id):
    scene = get_object_or_404(Scene.objects.select_related("tour"), pk=scene_id)
    tour = scene.tour
    # Preview starts at the scene being edited, even before an initial scene is chosen.
    tour.initial_scene = scene
    payload = viewer_data(tour, private=True)
    return render(request, "tours/viewer.html", {
        "tour": {**present(tour), "scenes": payload["scenes"]}, "tour_data": payload,
        "private_preview": True,
        "editor_url": reverse("admin:tours_scene_editor" if can_edit(request.user) else "admin:tours_scene_change", args=[scene.pk]),
        "preview_back_label": "Volver al editor" if can_edit(request.user) else "Volver al admin",
    })
