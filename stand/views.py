import json
from functools import wraps

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from redis.exceptions import RedisError

from tours import panel
from tours.content import present
from tours.images import file_exists
from tours.models import Scene, Tour
from . import services as service
from .models import StandSession


def unavailable(request):
    return render(request, "stand/unavailable.html", {"reason": "La sesión terminó o este dispositivo no tiene acceso. Vuelve a vincularte con el operador."}, status=403)


def notify(sid):
    # Updates are notifications only. Consumers always read the newest authoritative state.
    try:
        async_to_sync(get_channel_layer().group_send)(f"stand.{sid}", {"type": "state.changed"})
    except RedisError:
        pass  # Periodic state recovery remains authoritative once Redis is reachable again.


def config(session, role):
    return {"id": str(session.pk), "role": role, "socket": f"/stand/{session.pk}/socket/{role}/",
        "state": reverse("stand:state", args=[session.pk, role])}


@panel.panel_access
@require_http_methods(["GET", "POST"])
def index(request):
    if not (service.permitted(request.user, "view") or service.permitted(request.user, "add")):
        return panel.denied(request)
    error = ""
    if request.method == "POST":
        if not service.permitted(request.user, "add"):
            return panel.denied(request)
        try:
            tour_id = int(request.POST.get("tour", ""))
            session = service.create(request.user, tour_id)
            return redirect("stand:operator", sid=session.pk)
        except (ValueError, Tour.DoesNotExist, ValidationError):
            error = "Selecciona un recorrido disponible o de demostración que esté completo."
        except RedisError:
            error = "La sincronización no está disponible. Inicia Redis y vuelve a intentarlo."
    sessions = StandSession.objects.filter(owner=request.user) if not request.user.is_superuser else StandSession.objects.all()
    sessions = list(sessions.select_related("tour")[:20])
    for session in sessions:
        service.expire(session)
    return render(request, "stand/index.html", panel.context(request, section="stand", sessions=sessions,
        tours=service.available_tours(), can_create=service.permitted(request.user, "add"), error=error), status=400 if error else 200)


@panel.panel_access
@require_GET
def operator(request, sid):
    session = service.expire(get_object_or_404(StandSession, pk=sid))
    if not service.permitted(request.user, "view", session):
        return panel.denied(request)
    try:
        code = service.store().get(service.key(sid, "code")) if not session.viewer_hash else None
    except RedisError:
        code = None
    cfg = {**config(session, "operator"), "command": reverse("stand:command", args=[sid]),
        "code": reverse("stand:code", args=[sid]), "can_control": service.permitted(request.user, "change", session)}
    return render(request, "stand/operator.html", panel.context(request, section="stand", session=session,
        stand_config=cfg, code=code, tours=service.available_tours(), can_control=cfg["can_control"]))


@panel.panel_access
@require_POST
def command(request, sid):
    try:
        if request.content_type != "application/json" or len(request.body) > 2048:
            raise ValidationError("Formato de orden no válido.")
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValidationError("Formato de orden no válido.")
        service.command(request.user, sid, payload)
        notify(sid)
        return JsonResponse({"accepted": True})
    except PermissionDenied:
        return panel.denied(request)
    except (ValueError, TypeError, ValidationError, StandSession.DoesNotExist):
        return JsonResponse({"error": "No se envió la orden. Revisa el recorrido, la escena y los datos."}, status=400)
    except service.Conflict as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except RedisError:
        return JsonResponse({"error": "No se pudo confirmar la orden. Comprueba la sincronización antes de reintentar."}, status=503)


@panel.panel_access
@require_POST
def code(request, sid):
    try:
        value = service.regenerate_code(request.user, sid)
        notify(sid)
        return JsonResponse({"code": value})
    except PermissionDenied:
        return panel.denied(request)
    except service.Conflict as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except (RedisError, StandSession.DoesNotExist):
        return JsonResponse({"error": "No se pudo generar el código. Comprueba la sincronización."}, status=503)


def set_credential(response, session, role, token):
    response.set_cookie(f"stand_{role}_{session.pk}", token, max_age=settings.STAND_SESSION_SECONDS,
        path=f"/stand/{session.pk}/", secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite="Strict")
    response["Referrer-Policy"] = "no-referrer"
    return response


@panel.panel_access
@require_POST
def open_spectator(request, sid):
    try:
        session, token = service.spectator_token(request.user, sid)
    except PermissionDenied:
        return panel.denied(request)
    except (service.Conflict, RedisError, StandSession.DoesNotExist):
        messages.error(request, "No se pudo abrir el espectador. Comprueba que la sesión siga activa y Redis esté disponible.")
        return redirect("stand:operator", sid=sid)
    return set_credential(redirect("stand:spectator", sid=sid), session, "spectator", token)


@never_cache
@sensitive_post_parameters("code")
@require_http_methods(["GET", "POST"])
def join(request):
    error = ""
    if request.method == "POST":
        try:
            session, token = service.pair(request.POST.get("code", "")[:30], request.META.get("REMOTE_ADDR", "unknown"))
            notify(session.pk)
            return set_credential(redirect("stand:viewer", sid=session.pk), session, "viewer", token)
        except (ValidationError, service.Conflict) as exc:
            error = " ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        except RedisError:
            error = "No se pudo conectar al stand. Solicita ayuda al operador y vuelve a intentarlo."
    return render(request, "stand/join.html", {"error": error}, status=400 if error else 200)


def guest(role):
    def decorate(view):
        @wraps(view)
        @never_cache
        def wrapped(request, sid, **kwargs):
            session = service.expire(get_object_or_404(StandSession, pk=sid))
            if not service.credential_ok(session, role, request.COOKIES.get(f"stand_{role}_{sid}", "")):
                return unavailable(request)
            return view(request, session=session, **kwargs)
        return wrapped
    return decorate


@require_GET
@guest("viewer")
def viewer(request, session):
    tour = session.tour
    if not service.public_tour(tour):
        return unavailable(request)
    payload = service.tour_payload(tour, session.pk)
    return render(request, "tours/viewer.html", {"tour": {**present(tour), "scenes": payload["scenes"]}, "tour_data": payload, "stand_config": config(session, "viewer")})


@require_GET
@guest("spectator")
def spectator(request, session):
    return render(request, "stand/spectator.html", {"stand_config": config(session, "spectator")})


@never_cache
@require_GET
def state(request, sid, role):
    session = service.expire(get_object_or_404(StandSession, pk=sid))
    allowed = service.permitted(request.user, "view", session) if role == "operator" else service.credential_ok(session, role, request.COOKIES.get(f"stand_{role}_{sid}", ""))
    if not allowed:
        return JsonResponse({"error": "La sesión terminó o no tienes acceso."}, status=403)
    try:
        return JsonResponse(service.snapshot(session))
    except RedisError:
        return JsonResponse({"error": "La sincronización no está disponible."}, status=503)


@never_cache
@require_GET
def panorama(request, sid, scene_id):
    session = service.expire(get_object_or_404(StandSession.objects.select_related("confirmed_scene"), pk=sid))
    if not any(service.credential_ok(session, role, request.COOKIES.get(f"stand_{role}_{sid}", "")) for role in ("viewer", "spectator")):
        raise PermissionDenied
    tours = {session.tour_id}
    if session.confirmed_scene:
        tours.add(session.confirmed_scene.tour_id)
    scene = get_object_or_404(Scene.objects.select_related("tour"), pk=scene_id, tour_id__in=tours)
    if not service.public_tour(scene.tour) or not file_exists(scene.panorama):
        raise Http404
    try:
        return FileResponse(scene.panorama.open("rb"), content_type="image/png" if scene.panorama.name.endswith(".png") else "image/jpeg")
    except OSError as exc:
        raise Http404 from exc
