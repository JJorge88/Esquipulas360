"""Session protocol and authorization, shared by HTTP and WebSocket transports."""
import hashlib
import json
import secrets
import uuid
from datetime import timedelta

import redis
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from tours.content import viewer_data
from tours.models import Scene, Tour
from .models import StandSession


class Conflict(Exception):
    pass


def store():
    return redis.Redis.from_url(settings.STAND_REDIS_URL, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)


def key(sid, suffix):
    return f"{settings.STAND_REDIS_PREFIX}:{sid}:{suffix}"


def digest(secret):
    return salted_hmac("stand-credential", secret, algorithm="sha256").hexdigest()


def permitted(user, operation="view", session=None):
    return user.is_authenticated and user.is_active and user.is_staff and (
        user.has_perm(f"stand.{operation}_standsession") or
        (operation == "view" and user.has_perm("stand.change_standsession"))
    ) and (session is None or session.owner_id == user.pk or user.is_superuser)


def available_tours():
    return [t for t in Tour.objects.filter(status__in=["demo", "available"]).select_related("initial_scene", "category") if not t.publication_errors()]


def public_tour(tour):
    return tour is not None and tour.published and not tour.publication_errors()


def get_session(sid):
    return StandSession.objects.select_related("tour__initial_scene", "confirmed_scene__tour__initial_scene", "scene").get(pk=sid)


def expire(session):
    if session.phase != "ended" and session.expires_at <= timezone.now():
        StandSession.objects.filter(pk=session.pk).update(phase="ended", viewer_hash="", spectator_hash="", code_hash=None, error="")
        session.phase = "ended"
        session.viewer_hash = session.spectator_hash = ""
        session.code_hash = None
    return session


def credential_ok(session, role, token):
    return role in ("viewer", "spectator") and session.phase != "ended" and session.expires_at > timezone.now() and bool(token) and secrets.compare_digest(getattr(session, f"{role}_hash"), digest(token))


def issue_code(session):
    code = "".join(secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(8))
    session.code_hash = digest(code)
    session.code_expires_at = timezone.now() + timedelta(seconds=settings.STAND_CODE_SECONDS)
    session.save()
    store().set(key(session.pk, "code"), code, ex=settings.STAND_CODE_SECONDS)
    return code


def create(user, tour_id):
    if not permitted(user, "add"):
        raise PermissionDenied
    if type(tour_id) is not int or not 0 < tour_id < 2**63:
        raise ValidationError("El recorrido no es válido.")
    with store().lock(key(user.pk, "create-lock"), timeout=10, blocking_timeout=2):
        with transaction.atomic():
            for old in StandSession.objects.filter(owner=user).exclude(phase="ended"):
                expire(old)
            existing = StandSession.objects.filter(owner=user).exclude(phase="ended").first()
            if existing:
                return existing
            tour = Tour.objects.get(pk=tour_id)
            if not public_tour(tour):
                raise ValidationError("Elige un recorrido disponible o de demostración que esté completo.")
            session = StandSession(owner=user, tour=tour, scene=tour.initial_scene,
                expires_at=timezone.now() + timedelta(seconds=settings.STAND_SESSION_SECONDS), code_expires_at=timezone.now())
            issue_code(session)
            return session


def regenerate_code(user, sid):
    with store().lock(key(sid, "lock"), timeout=10, blocking_timeout=2), transaction.atomic():
        session = expire(get_session(sid))
        if not permitted(user, "change", session):
            raise PermissionDenied
        if session.viewer_hash or session.phase == "ended":
            raise Conflict("Esta sesión ya se vinculó o terminó. Finalízala y crea otra para usar un nuevo visor.")
        return issue_code(session)


def rate_limit(address):
    client = store()
    # Never trust X-Forwarded-For here. A reverse proxy must enforce a per-client limit as well.
    for bucket, limit in ((digest(address), settings.STAND_PAIR_ATTEMPTS), ("global", 60)):
        count = client.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n", 1, key("pair", bucket))
        if count > limit:
            raise Conflict("Demasiados intentos. Espera un minuto antes de volver a probar.")


def pair(code, address):
    rate_limit(address)
    normalized = code.replace("-", "").replace(" ", "").upper()
    invalid = "El código es incorrecto, caducó o ya fue utilizado. Solicita uno al operador."
    if len(normalized) != 8:
        raise ValidationError(invalid)
    hashed = digest(normalized)
    sid = StandSession.objects.filter(code_hash=hashed).values_list("pk", flat=True).first()
    if not sid:
        raise ValidationError(invalid)
    # Share the session lock with renewal/end, then recheck the code under the lock.
    with store().lock(key(sid, "lock"), timeout=10, blocking_timeout=2), transaction.atomic():
        session = StandSession.objects.select_for_update().filter(pk=sid, code_hash=hashed, code_expires_at__gt=timezone.now(), expires_at__gt=timezone.now()).exclude(phase="ended").first()
        if not session or session.viewer_hash or not public_tour(session.tour):
            raise ValidationError(invalid)
        token = secrets.token_urlsafe(32)
        session.viewer_hash = digest(token)
        session.code_hash = None
        session.save(update_fields=["viewer_hash", "code_hash"])
        store().delete(key(session.pk, "code"))
        return session, token


def spectator_token(user, sid):
    with store().lock(key(sid, "lock"), timeout=10, blocking_timeout=2):
        session = expire(get_session(sid))
        if not permitted(user, "change", session):
            raise PermissionDenied
        if session.phase == "ended":
            raise Conflict("La sesión ya finalizó.")
        token = secrets.token_urlsafe(32)
        session.spectator_hash = digest(token)
        session.save(update_fields=["spectator_hash"])
        # A newly opened TV window replaces the previous one immediately. The old
        # socket's compare-and-delete cleanup cannot remove the replacement's lease.
        store().delete(key(sid, "spectator-lease"))
        return session, token


def command(user, sid, payload):
    if set(payload) != {"id", "seq", "action", "tour", "scene"} or type(payload["seq"]) is not int:
        raise ValidationError("La orden no es válida.")
    try:
        identifier = uuid.UUID(payload["id"])
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("La orden necesita un identificador válido.")
    action = payload["action"]
    if action not in ("start", "tour", "scene", "restart", "end"):
        raise ValidationError("Acción no permitida.")
    if action == "tour" and (type(payload["tour"]) is not int or not 0 < payload["tour"] < 2**63):
        raise ValidationError("El recorrido no es válido.")
    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with store().lock(key(sid, "lock"), timeout=10, blocking_timeout=2), transaction.atomic():
        session = expire(get_session(sid))
        if not permitted(user, "change", session):
            raise PermissionDenied
        if session.command_id == identifier:
            if request_hash != session.request_hash:
                raise Conflict("Ese identificador ya corresponde a otra orden.")
            return session
        if session.phase == "ended":
            raise Conflict("La sesión ya finalizó.")
        if session.seq != payload["seq"]:
            raise Conflict("El estado cambió. Revisa la escena actual y vuelve a enviar la orden.")
        if action != "end":
            tour = Tour.objects.filter(pk=payload["tour"]).first() if action == "tour" else session.tour
            if not public_tour(tour):
                raise ValidationError("El recorrido dejó de estar disponible o está incompleto. Elige otro.")
            if action == "scene":
                target = tour.scenes.filter(key=payload["scene"]).first() if isinstance(payload["scene"], str) else None
                if not target:
                    raise ValidationError("La escena no pertenece al recorrido seleccionado.")
            else:
                target = tour.initial_scene
            session.tour, session.scene = tour, target
            if action in ("start", "scene", "restart"):
                session.phase = "running"
        else:
            session.phase = "ended"
            session.viewer_hash = session.spectator_hash = ""
            session.code_hash = None
            store().delete(key(sid, "code"), key(sid, "pose"))
        session.seq += 1
        session.command_id = identifier
        session.request_hash = request_hash
        session.action, session.error = action, ""
        session.save()
        return session


def viewer_event(sid, token, payload):
    kind = payload.get("type")
    fields = {"navigate": {"type", "seq", "scene"}, "applied": {"type", "seq", "scene"}, "error": {"type", "seq", "code"}}
    if kind not in fields or set(payload) != fields[kind] or type(payload.get("seq")) is not int:
        raise ValidationError("Evento de visor no válido.")
    with store().lock(key(sid, "lock"), timeout=10, blocking_timeout=2), transaction.atomic():
        session = expire(get_session(sid))
        if not credential_ok(session, "viewer", token):
            raise PermissionDenied
        if session.phase != "running" or not public_tour(session.tour):
            raise Conflict("El recorrido todavía no está iniciado o dejó de estar disponible.")
        if session.seq != payload["seq"]:
            return session  # Stale confirmations/navigation never overwrite the current desired state.
        if kind == "error":
            if payload["code"] not in ("load_failed", "webgl_lost"):
                raise ValidationError("Error de visor no reconocido.")
            session.error = "El visor no pudo cargar la escena. Revisa la conexión o selecciona otra escena."
        elif kind == "applied":
            if payload["scene"] != session.scene.key:
                raise ValidationError("La confirmación no corresponde a la escena enviada.")
            session.confirmed_scene, session.applied_seq, session.error = session.scene, session.seq, ""
        else:
            if session.applied_seq != session.seq or not isinstance(payload["scene"], str):
                raise Conflict("Espera a que se aplique la orden pendiente.")
            target = session.tour.scenes.filter(key=payload["scene"]).first()
            if not target:
                raise ValidationError("Destino ajeno al recorrido.")
            session.scene, session.action = target, "visitor"
            session.seq += 1
            session.command_id = uuid.uuid4()
            session.request_hash, session.error = "", ""
        session.save()
        return session


def tour_payload(tour, sid):
    if not public_tour(tour):
        return None
    data = viewer_data(tour, private=True, panorama_url=lambda s: reverse("stand:panorama", args=[sid, s.pk]))
    return {**data, "id": tour.pk, "slug": tour.slug,
        "thumbnails": {s.key: s.thumbnail.url if s.thumbnail else "" for s in tour.scenes.all()}}


def snapshot(session):
    session = expire(session)
    if session.phase == "ended":
        return {"type": "ended", "id": str(session.pk), "seq": session.seq}
    client = store()
    viewer = bool(client.exists(key(session.pk, "viewer-lease")))
    spectator = bool(client.exists(key(session.pk, "spectator-lease")))
    tour = tour_payload(session.tour, session.pk)
    confirmed = session.confirmed_scene
    actual_tour = tour if confirmed and confirmed.tour_id == session.tour_id else tour_payload(confirmed.tour, session.pk) if confirmed else None
    return {"type": "state", "id": str(session.pk), "seq": session.seq, "command_id": str(session.command_id),
        "phase": session.phase, "action": session.action, "tour": tour,
        "scene": session.scene.key if session.scene else None, "confirmed_scene": confirmed.key if confirmed and actual_tour else None,
        "confirmed_tour": actual_tour, "applied_seq": session.applied_seq, "error": session.error,
        "content_error": "El recorrido ya no está disponible. El operador debe seleccionar otro." if not tour else "",
        "paired": bool(session.viewer_hash), "code_expires_at": session.code_expires_at.isoformat(),
        "expires_at": session.expires_at.isoformat(), "viewer_connected": viewer, "spectator_connected": spectator,
        "order_status": "error" if session.error else "applied" if confirmed and session.applied_seq == session.seq else "sent"}
