"""Custom staff UI. Django permissions and shared model validation remain authoritative."""
from functools import wraps

from django.contrib import admin, messages
from django.contrib.auth.views import LoginView, LogoutView, redirect_to_login
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError, RestrictedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from . import editor
from .content import filter_tours
from .images import file_exists
from .models import Category, Scene, Tour
from .panel_forms import PanelAuthenticationForm, PanelCategoryForm, PanelSceneForm, PanelTourForm, authorized


def allowed(user, model, operation="view"):
    return user.is_active and user.is_staff and (
        user.has_perm(f"tours.{operation}_{model}") or
        (operation == "view" and user.has_perm(f"tours.change_{model}"))
    )


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "") or request.content_type == "application/json"


def denied(request):
    if wants_json(request):
        return JsonResponse({"error": "No tienes permiso para realizar esta operación."}, status=403)
    return render(request, "panel/forbidden.html", context(request), status=403)


def panel_access(view):
    @wraps(view)
    @never_cache
    @csrf_protect
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if wants_json(request):
                return JsonResponse({"error": "Tu sesión terminó. Abre el panel en otra pestaña, inicia sesión y vuelve a intentar el guardado."}, status=403)
            return redirect_to_login(request.get_full_path(), reverse("panel:login"))
        if not authorized(request.user):
            return denied(request)
        return view(request, *args, **kwargs)
    return wrapped


def context(request, **extra):
    capabilities = {f"{operation}_{model}": allowed(request.user, model, operation)
                    for model in ("tour", "scene", "category") for operation in ("view", "add", "change", "delete")}
    return {"panel_permissions": capabilities, "can_preview": editor.can_preview(request.user),
            "can_edit_points": editor.can_edit(request.user), **extra}


class PanelLoginView(LoginView):
    template_name = "panel/login.html"
    authentication_form = PanelAuthenticationForm
    next_page = reverse_lazy("panel:home")


class PanelLogoutView(LogoutView):
    next_page = reverse_lazy("panel:login")


def thumbnail(obj):
    return obj.thumbnail.url if file_exists(obj.thumbnail) else ""


def tour_cards(tours, request):
    cards = []
    for tour in tours:
        cards.append({"object": tour, "image": thumbnail(tour), "scene_count": tour.scene_count,
                      "preview": editor.can_preview(request.user) and tour.scene_count > 0})
    return cards


def tour_query():
    return Tour.objects.select_related("category", "initial_scene").annotate(scene_count=Count("scenes"))


@panel_access
@require_GET
def home(request):
    stats, recent = [], []
    if allowed(request.user, "tour"):
        counts = dict(Tour.objects.values_list("status").annotate(total=Count("pk")))
        stats = [{"label": label, "value": counts.get(status, 0), "url": reverse("panel:tours") + "?status=" + status}
                 for status, label in (("available", "Disponibles"), ("draft", "Borradores"), ("upcoming", "Próximos"))]
        recent = tour_cards(tour_query().order_by("-pk")[:4], request)
    if allowed(request.user, "scene"):
        stats.append({"label": "Escenas", "value": Scene.objects.count()})
    return render(request, "panel/home.html", context(request, section="home", stats=stats, cards=recent))


@panel_access
@require_GET
def tours(request):
    if not allowed(request.user, "tour"):
        return denied(request)
    query = request.GET.get("q", "").strip()[:200]
    category = request.GET.get("category", "")
    status = request.GET.get("status", "")
    objects = tour_query()
    if status:
        objects = objects.filter(status=status)
    page = Paginator(filter_tours(objects, query, category), 12).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "panel/tours.html", context(request, section="tours", cards=tour_cards(page, request),
        page=page, query=query, selected_category=category, selected_status=status, categories=Category.objects.all(),
        statuses=Tour.Status.choices, filter_query=params.urlencode()))


def add_save_error(form, exc):
    if hasattr(exc, "message_dict"):
        for field, errors in exc.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, exc)


def save_form(request, form, destination):
    """A JSON failure leaves the original DOM (including selected uploads) intact."""
    if form.is_valid():
        try:
            with transaction.atomic():
                obj = form.save()
        except ValidationError as exc:
            add_save_error(form, exc)
        else:
            url = destination(obj)
            messages.success(request, "Cambios guardados correctamente.")
            return JsonResponse({"redirect": url}) if wants_json(request) else redirect(url)
    if wants_json(request):
        return JsonResponse({"error": "No se guardaron los cambios. Revisa los campos indicados.", "errors": form.errors}, status=400)
    return None


@panel_access
@require_http_methods(["GET", "POST"])
def tour_edit(request, pk=None):
    operation = "change" if pk else "add"
    editable = allowed(request.user, "tour", operation)
    if not editable and (not pk or request.method == "POST" or not allowed(request.user, "tour")):
        return denied(request)
    obj = get_object_or_404(Tour, pk=pk) if pk else Tour()
    form = PanelTourForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST":
        response = save_form(request, form, lambda saved: reverse("panel:tour_edit", args=[saved.pk]) if allowed(request.user, "tour") else reverse("panel:home"))
        if response is not None:
            return response
    scenes = [{"object": scene, "image": thumbnail(scene), "point_count": scene.point_count}
              for scene in obj.scenes.annotate(point_count=Count("hotspots"))] if pk and allowed(request.user, "scene") else []
    return render(request, "panel/tour_form.html", context(request, section="tours", obj=obj, form=form,
        editable=editable, scenes=scenes, image=thumbnail(obj), publication_errors=obj.publication_errors(inspect_images=True)), status=400 if form.errors else 200)


@panel_access
@require_http_methods(["GET", "POST"])
def scene_edit(request, tour_id, scene_id=None):
    editable = allowed(request.user, "scene", "change" if scene_id else "add")
    if not allowed(request.user, "tour") or (not editable and (not scene_id or request.method == "POST" or not allowed(request.user, "scene"))):
        return denied(request)
    tour = get_object_or_404(Tour, pk=tour_id)
    obj = get_object_or_404(Scene, pk=scene_id, tour=tour) if scene_id else Scene(tour=tour)
    form = PanelSceneForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST":
        response = save_form(request, form, lambda saved: reverse("panel:scene_edit", args=[tour.pk, saved.pk]) if allowed(request.user, "scene") else reverse("panel:tour_edit", args=[tour.pk]))
        if response is not None:
            return response
    return render(request, "panel/scene_form.html", context(request, section="tours", tour=tour, obj=obj, form=form, editable=editable, image=thumbnail(obj)), status=400 if form.errors else 200)


@panel_access
@require_GET
def categories(request):
    if not allowed(request.user, "category"):
        return denied(request)
    return render(request, "panel/categories.html", context(request, section="categories", categories=Category.objects.annotate(tour_count=Count("tours"))))


@panel_access
@require_http_methods(["GET", "POST"])
def category_edit(request, pk=None):
    editable = allowed(request.user, "category", "change" if pk else "add")
    if not editable and (not pk or request.method == "POST" or not allowed(request.user, "category")):
        return denied(request)
    obj = get_object_or_404(Category, pk=pk) if pk else Category()
    form = PanelCategoryForm(request.POST or None, instance=obj)
    if request.method == "POST":
        response = save_form(request, form, lambda saved: reverse("panel:categories") if allowed(request.user, "category") else reverse("panel:home"))
        if response is not None:
            return response
    return render(request, "panel/category_form.html", context(request, section="categories", obj=obj, form=form, editable=editable), status=400 if form.errors else 200)


def deletion_plan(obj, request):
    # Use precisely the same dependency collector and related permissions as /admin/.
    _, counts, needed, protected = admin.site.get_model_admin(type(obj)).get_deleted_objects([obj], request)
    reasons = []
    if isinstance(obj, Tour) and obj.published and allowed(request.user, "scene", "delete"):
        # SceneAdmin intentionally blocks published scenes, even for a permitted editor.
        # Explain the publication restriction rather than incorrectly asking for permissions.
        needed.discard(Scene._meta.verbose_name)
    if needed:
        reasons.append("La eliminación también afecta registros para los que no tienes permiso de eliminación: " + ", ".join(sorted(needed)) + ".")
    if isinstance(obj, Tour) and obj.published:
        reasons.append("Cambia el recorrido a borrador antes de eliminar sus escenas y puntos.")
    if protected:
        if isinstance(obj, Category):
            reasons.append("Esta categoría está en uso. Asigna otra categoría a sus recorridos antes de eliminarla.")
        elif isinstance(obj, Scene):
            reasons.append("Para eliminar esta escena, el recorrido debe estar en borrador. Quita su selección como escena inicial y elimina o cambia los puntos que llegan a ella desde otras escenas.")
        else:
            reasons.append("Otros registros dependen de este contenido. Revisa sus relaciones antes de eliminarlo.")
    return counts, reasons


@panel_access
@require_http_methods(["GET", "POST"])
def delete(request, model, pk, tour_id=None):
    if not allowed(request.user, model._meta.model_name, "delete") or (model is Scene and not allowed(request.user, "tour")):
        return denied(request)
    lookup = {"pk": pk, **({"tour_id": tour_id} if model is Scene else {})}
    with transaction.atomic():
        obj = get_object_or_404(model.objects.select_for_update(), **lookup)
        counts, reasons = deletion_plan(obj, request)
        back_url = reverse("panel:tour_edit", args=[tour_id]) if model is Scene else reverse("panel:categories" if model is Category else "panel:tours")
        if request.method == "POST" and not reasons:
            try:
                with transaction.atomic():
                    obj.delete()
            except (ProtectedError, RestrictedError, ValidationError):
                reasons.append("No se pudo eliminar: el contenido está publicado o tiene relaciones protegidas. Revisa el recorrido y vuelve a intentarlo.")
            else:
                messages.success(request, "Registro eliminado. Los archivos originales se conservan.")
                return redirect(back_url if allowed(request.user, "category" if model is Category else "tour") else reverse("panel:home"))
    return render(request, "panel/delete.html", context(request, section="categories" if model is Category else "tours", obj=obj,
        counts=counts, reasons=reasons, back_url=back_url), status=409 if request.method == "POST" else 200)


def scene_route(view):
    @panel_access
    @wraps(view)
    def wrapped(request, tour_id, scene_id, **kwargs):
        # Check permissions before looking up any private record.
        if not editor.can_preview(request.user):
            return denied(request)
        get_object_or_404(Scene, pk=scene_id, tour_id=tour_id)
        return view(request, scene_id=scene_id, **kwargs)
    return wrapped


@panel_access
@require_GET
def tour_preview(request, pk):
    if not editor.can_preview(request.user):
        return denied(request)
    tour = get_object_or_404(Tour, pk=pk)
    scene = tour.initial_scene or tour.scenes.first()
    if scene is None:
        messages.info(request, "Añade una escena y su panorámica para previsualizar el recorrido.")
        return redirect("panel:tour_edit", pk=pk)
    return redirect("panel:preview", tour_id=pk, scene_id=scene.pk)
