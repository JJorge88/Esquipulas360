import math
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .images import (cover_path, panorama_path, validate_cover, validate_panorama,
                     validate_angle, thumbnail_content, file_exists)

def stable_key():
    return uuid4().hex

class ValidatedQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Guarda cada registro individualmente para aplicar las validaciones de contenido.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("La creación masiva omite validaciones. Usa save() para cada registro.")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("La actualización masiva omite validaciones. Usa save() para cada registro.")

class ValidatedModel(models.Model):
    objects = ValidatedQuerySet.as_manager()
    image_attribute = None

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is not None:
            raise ValidationError("Guarda el registro completo para validar las relaciones; no uses update_fields.")
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            if self.pk:
                type(self).objects.using(using).select_for_update().filter(pk=self.pk).first()
            self.lock_parent(using)
            self.full_clean()
            original = getattr(self, self.image_attribute) if self.image_attribute else None
            previous = type(self).objects.using(using).filter(pk=self.pk).first() if self.pk else None
            changed = bool(self.image_attribute and (not previous or getattr(previous, self.image_attribute).name != original.name or (original and not original._committed)))
            super().save(*args, **kwargs)
            if self.image_attribute and (changed or (original and not self.thumbnail)):
                preview = thumbnail_content(original) if original else None
                self.thumbnail = ""
                if preview:
                    self.thumbnail.save(preview.name, preview, save=False)
                # Only a generated derivative; bypass our save override to avoid recursion.
                models.Model.save(self, using=using, update_fields=["thumbnail"])

    def lock_parent(self, using):
        pass

class Category(ValidatedModel):
    name = models.CharField("nombre", max_length=100)
    slug = models.SlugField("slug", unique=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["id"]

    def __str__(self):
        return self.name

class Tour(ValidatedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        UPCOMING = "upcoming", "Próximo"
        DEMO = "demo", "Demostración"
        AVAILABLE = "available", "Disponible"

    name = models.CharField("nombre", max_length=180)
    slug = models.SlugField("slug", unique=True, max_length=180)
    description = models.TextField("descripción")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name="categoría", related_name="tours")
    cover = models.ImageField("portada", upload_to=cover_path, validators=[validate_cover], blank=True, max_length=255)
    thumbnail = models.ImageField(upload_to="", blank=True, editable=False, max_length=255)
    status = models.CharField("estado", max_length=12, choices=Status, default=Status.DRAFT)
    featured = models.BooleanField("destacado en Inicio", default=False)
    order = models.PositiveIntegerField("orden", default=0)
    initial_scene = models.ForeignKey("Scene", on_delete=models.RESTRICT, null=True, blank=True, related_name="initial_for", verbose_name="escena inicial", help_text="Guarda primero el recorrido como borrador y crea sus escenas.")
    legacy_key = models.CharField(max_length=100, unique=True, null=True, blank=True, editable=False)
    image_attribute = "cover"

    class Meta:
        verbose_name = "recorrido"
        verbose_name_plural = "recorridos"
        ordering = ["order", "name", "pk"]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=["draft", "upcoming", "demo", "available"]), name="tour_valid_status")]

    def __str__(self):
        return self.name

    @property
    def published(self):
        return self.status in (self.Status.DEMO, self.Status.AVAILABLE)

    def publication_errors(self, *, inspect_images=False):
        errors = []
        scenes = list(self.scenes.all()) if self.pk else []
        by_id = {scene.pk: scene for scene in scenes}
        if not self.initial_scene_id or self.initial_scene_id not in by_id:
            errors.append("Selecciona una escena inicial perteneciente a este recorrido.")
        if not scenes:
            errors.append("Añade al menos una escena antes de publicar.")
        for scene in scenes:
            if not file_exists(scene.panorama):
                errors.append(f"Falta la panorámica de «{scene.name}». Carga el archivo antes de publicar.")
            elif inspect_images:
                try:
                    validate_panorama(scene.panorama)
                except ValidationError as exc:
                    errors.extend(f"{scene.name}: {message}" for message in exc.messages)
            for point in scene.hotspots.all():
                if point.destination_id not in by_id:
                    errors.append(f"El destino de «{point.label}» no pertenece a este recorrido.")
        return errors

    def clean(self):
        super().clean()
        if self.initial_scene_id and not Scene.objects.filter(pk=self.initial_scene_id, tour_id=self.pk).exists():
            raise ValidationError({"initial_scene": "La escena inicial debe pertenecer al mismo recorrido."})
        if self.published:
            errors = self.publication_errors(inspect_images=True)
            if errors:
                raise ValidationError({"status": errors})

class Scene(ValidatedModel):
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name="scenes", verbose_name="recorrido")
    key = models.SlugField(max_length=100, default=stable_key, editable=False)
    name = models.CharField("nombre", max_length=180)
    order = models.PositiveIntegerField("orden", default=0)
    panorama = models.ImageField("imagen panorámica", upload_to=panorama_path, validators=[validate_panorama], blank=True, max_length=255, help_text="JPEG o PNG equirectangular. 2:1 ±1% por defecto. Puede quedar vacía mientras el recorrido no esté publicado.")
    thumbnail = models.ImageField(upload_to="", blank=True, editable=False, max_length=255)
    yaw = models.FloatField("orientación horizontal (°)", default=0, validators=[validate_angle, MinValueValidator(-180), MaxValueValidator(180)])
    pitch = models.FloatField("orientación vertical (°)", default=0, validators=[validate_angle, MinValueValidator(-90), MaxValueValidator(90)])
    text = models.TextField("texto informativo", blank=True, help_text="Texto plano. No se interpreta HTML.")
    image_attribute = "panorama"

    class Meta:
        verbose_name = "escena"
        verbose_name_plural = "escenas"
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["tour", "key"], name="scene_key_per_tour"),
            models.CheckConstraint(condition=models.Q(yaw__gte=-180, yaw__lte=180, pitch__gte=-90, pitch__lte=90), name="scene_angles_in_range"),
        ]

    def __str__(self):
        return f"{self.tour.name} · {self.name}"

    def lock_parent(self, using):
        if self.tour_id:
            self.tour = Tour.objects.using(using).select_for_update().get(pk=self.tour_id)

    def clean(self):
        super().clean()
        if self.pk and Scene.objects.filter(pk=self.pk).exclude(tour_id=self.tour_id).exists():
            raise ValidationError({"tour": "Una escena guardada no puede trasladarse a otro recorrido. Crea una nueva escena allí."})
        if self.tour_id and Tour.objects.filter(pk=self.tour_id, status__in=[Tour.Status.DEMO, Tour.Status.AVAILABLE]).exists() and not self.panorama:
            raise ValidationError({"panorama": "Un recorrido publicado necesita panorámicas en todas sus escenas. Cambia primero su estado a borrador."})

class NavigationPoint(ValidatedModel):
    origin = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name="hotspots", verbose_name="escena de origen")
    destination = models.ForeignKey(Scene, on_delete=models.RESTRICT, related_name="incoming_points", verbose_name="escena de destino")
    key = models.SlugField(max_length=100, default=stable_key, editable=False)
    label = models.CharField("etiqueta", max_length=120)
    yaw = models.FloatField("posición horizontal (°)", default=0, validators=[validate_angle, MinValueValidator(-180), MaxValueValidator(180)], help_text="0: frente; +90: izquierda; −90: derecha; ±180: atrás.")
    pitch = models.FloatField("posición vertical (°)", default=0, validators=[validate_angle, MinValueValidator(-90), MaxValueValidator(90)], help_text="Positivo: arriba. Negativo: abajo.")

    class Meta:
        verbose_name = "punto de navegación"
        verbose_name_plural = "puntos de navegación"
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["origin", "key"], name="point_key_per_scene"),
            models.CheckConstraint(condition=~models.Q(origin=models.F("destination")), name="point_different_scenes"),
            models.CheckConstraint(condition=models.Q(yaw__gte=-180, yaw__lte=180, pitch__gte=-90, pitch__lte=90), name="point_angles_in_range"),
        ]

    def __str__(self):
        return self.label

    def lock_parent(self, using):
        if self.origin_id:
            Tour.objects.using(using).select_for_update().get(pk=self.origin.tour_id)

    def clean(self):
        super().clean()
        if self.origin_id and self.destination_id:
            if self.origin_id == self.destination_id:
                raise ValidationError({"destination": "Elige otra escena como destino; no la misma escena de origen."})
            if self.origin.tour_id != self.destination.tour_id:
                raise ValidationError({"destination": "Origen y destino deben pertenecer al mismo recorrido."})

    def position(self):
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        radius = 3.5
        return [-radius * math.sin(yaw) * math.cos(pitch), radius * math.sin(pitch), -radius * math.cos(yaw) * math.cos(pitch)]

@receiver(pre_delete, sender=Scene)
def protect_published_scene(sender, instance, using, origin, **kwargs):
    # Removing an entire tour is consistent: its scenes and points disappear together.
    origin_model = origin.model if isinstance(origin, models.QuerySet) else type(origin)
    if origin_model is Tour:
        return
    tour = Tour.objects.using(using).select_for_update().get(pk=instance.tour_id)
    if tour.published:
        raise ProtectedError("Cambia el recorrido a borrador antes de eliminar sus escenas.", [instance])
