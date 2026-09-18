from django.contrib import admin
from django.utils.html import format_html
from .forms import TourForm, NavigationPointForm
from .images import file_exists
from .models import Category, Tour, Scene, NavigationPoint

admin.site.site_header = "Esquipulas 360° · Administración"
admin.site.site_title = "Esquipulas 360°"
admin.site.index_title = "Administración de recorridos"

@admin.display(description="Miniatura")
def preview(obj):
    if file_exists(obj.thumbnail):
        return format_html('<img src="{}" alt="Vista previa de {}" width="160" height="90" style="object-fit:contain" loading="lazy">', obj.thumbnail.url, obj.name)
    return "Sin miniatura"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}

class SceneSummaryInline(admin.TabularInline):
    model = Scene
    fk_name = "tour"
    fields = ["name", "order", preview]
    readonly_fields = ["name", "order", preview]
    extra = 0
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    form = TourForm
    list_display = ["name", "category", "status", "featured", "order", preview]
    list_filter = ["status", "category", "featured"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ["category"]
    readonly_fields = [preview]
    inlines = [SceneSummaryInline]
    fieldsets = [
        ("Lugar y descripción", {"fields": ["name", "slug", "description", "category"]}),
        ("Portada", {"fields": ["cover", preview], "description": "JPEG, PNG o WebP. El original se conserva; los límites se configuran en el servidor."}),
        ("Publicación", {"fields": ["status", "initial_scene", "featured", "order"], "description": "Primero guarda como borrador, crea las escenas y conecta sus puntos. Después selecciona la escena inicial y publica. Para eliminar escenas, vuelve a borrador."}),
    ]

class NavigationInline(admin.TabularInline):
    model = NavigationPoint
    fk_name = "origin"
    fields = ["destination", "label", "yaw", "pitch"]
    extra = 0

    def get_formset(self, request, obj=None, **kwargs):
        request._navigation_origin = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "destination":
            origin = getattr(request, "_navigation_origin", None)
            kwargs["queryset"] = Scene.objects.filter(tour_id=origin.tour_id).exclude(pk=origin.pk).select_related("tour") if origin else Scene.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request, obj=None):
        return obj is not None and super().has_add_permission(request, obj)

@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ["name", "tour", "order", preview]
    list_filter = ["tour", "tour__status"]
    search_fields = ["name", "tour__name", "text"]
    list_select_related = ["tour"]
    readonly_fields = [preview]
    inlines = [NavigationInline]
    fieldsets = [
        ("Escena", {"fields": ["tour", "name", "order"]}),
        ("Panorámica", {"fields": ["panorama", preview]}),
        ("Orientación inicial", {"fields": ["yaw", "pitch"], "description": "Grados de escena: 0 al frente, +90 a la izquierda, −90 a la derecha. Vertical positivo hacia arriba. No es una brújula geográfica."}),
        ("Información", {"fields": ["text"]}),
    ]

    def get_readonly_fields(self, request, obj=None):
        return [preview, "tour"] if obj else [preview]

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or not obj.tour.published)

    def get_deleted_objects(self, objs, request):
        deleted, counts, needed, protected = super().get_deleted_objects(objs, request)
        protected.extend(f"{obj}: cambia el recorrido a borrador antes de eliminar escenas." for obj in objs if obj.tour.published)
        if super().has_delete_permission(request):
            needed.discard(Scene._meta.verbose_name)
        return deleted, counts, needed, protected

@admin.register(NavigationPoint)
class NavigationPointAdmin(admin.ModelAdmin):
    form = NavigationPointForm
    list_display = ["label", "origin", "destination", "yaw", "pitch"]
    list_filter = ["origin__tour"]
    search_fields = ["label", "origin__name", "destination__name", "origin__tour__name"]
    list_select_related = ["origin__tour", "destination__tour"]
    fieldsets = [
        ("Conexión", {"fields": ["origin", "destination", "label"], "description": "El destino debe ser otra escena del mismo recorrido. Para crear ida y vuelta, añade un punto en cada escena."}),
        ("Posición angular", {"fields": ["yaw", "pitch"]}),
    ]
