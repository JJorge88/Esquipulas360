"""Presentation-only forms; content and publication rules live in the models."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .forms import TourForm
from .models import Category, Scene, Tour


def authorized(user):
    return user.is_active and user.is_staff and any(
        user.has_perm(f"tours.{action}_{model}")
        for model in ("tour", "category", "scene", "navigationpoint")
        for action in ("view", "add", "change", "delete")
    )


class PanelAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not authorized(user):
            raise ValidationError("Esta cuenta no tiene acceso al panel. Solicita acceso al responsable del proyecto.", code="no_panel_access")


class OriginalFileInput(forms.ClearableFileInput):
    template_name = "panel/file_input.html"


class PanelFields:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["aria-describedby"] = f"id_{name}_help id_{name}_errors"
        if "slug" in self.fields:
            self.fields["slug"].required = False
            self.fields["slug"].label = "Dirección del recorrido" if self._meta.model is Tour else "Identificador"
            self.fields["slug"].help_text = "Solo letras sin acentos, números y guiones. Si lo dejas vacío, se genera a partir del nombre. Conserva el actual para mantener sus enlaces."
        if "order" in self.fields:
            self.fields["order"].help_text = "Los números menores aparecen primero."
        if "initial_scene" in self.fields:
            self.fields["initial_scene"].label_from_instance = lambda scene: scene.name
        if "cover" in self.fields:
            self.fields["cover"].help_text = f"Máximo {settings.COVER_MAX_BYTES / 1048576:g} MiB; mínimo {settings.COVER_MIN_WIDTH} × {settings.COVER_MIN_HEIGHT} píxeles."
        if "panorama" in self.fields:
            self.fields["panorama"].help_text = f"Máximo {settings.PANORAMA_MAX_BYTES / 1048576:g} MiB; mínimo {settings.PANORAMA_MIN_WIDTH} × {settings.PANORAMA_MIN_HEIGHT} píxeles. Proporción 2:1, con tolerancia de ±{settings.PANORAMA_RATIO_TOLERANCE * 100:g} %. Puede quedar vacía mientras el recorrido no esté publicado."

    def clean(self):
        data = super().clean()
        if "slug" in self.fields and not data.get("slug"):
            data["slug"] = slugify(data.get("name", ""))[:self.fields["slug"].max_length]
            if not data["slug"]:
                self.add_error("slug", "Escribe un identificador con letras o números.")
        return data


class PanelTourForm(PanelFields, TourForm):
    class Meta(TourForm.Meta):
        fields = ["name", "slug", "description", "category", "cover", "status", "featured", "order", "initial_scene"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5}), "cover": OriginalFileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp", "data-image-input": "cover"})}


class PanelSceneForm(PanelFields, forms.ModelForm):
    class Meta:
        model = Scene
        fields = ["name", "order", "panorama", "text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 5}), "panorama": OriginalFileInput(attrs={"accept": ".jpg,.jpeg,.png", "data-image-input": "panorama"})}


class PanelCategoryForm(PanelFields, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug"]
