import uuid
from django.conf import settings
from django.db import models


class StandSession(models.Model):
    """Current control state only. Head poses and presence never enter this database."""
    class Phase(models.TextChoices):
        WAITING = "waiting", "En espera"
        RUNNING = "running", "En curso"
        ENDED = "ended", "Finalizada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    tour = models.ForeignKey("tours.Tour", on_delete=models.SET_NULL, null=True, related_name="stand_sessions")
    scene = models.ForeignKey("tours.Scene", on_delete=models.SET_NULL, null=True, related_name="stand_targets")
    confirmed_scene = models.ForeignKey("tours.Scene", on_delete=models.SET_NULL, null=True, blank=True, related_name="stand_confirmed")
    phase = models.CharField(max_length=10, choices=Phase, default=Phase.WAITING)
    seq = models.PositiveIntegerField(default=0)
    applied_seq = models.PositiveIntegerField(default=0)
    command_id = models.UUIDField(default=uuid.uuid4)
    request_hash = models.CharField(max_length=64, blank=True)
    action = models.CharField(max_length=12, default="created")
    error = models.CharField(max_length=200, blank=True)
    code_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    code_expires_at = models.DateTimeField()
    viewer_hash = models.CharField(max_length=64, blank=True)
    spectator_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "sesión de stand"
        verbose_name_plural = "sesiones de stand"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["owner"], condition=models.Q(phase__in=["waiting", "running"]), name="one_active_stand_per_operator")]
