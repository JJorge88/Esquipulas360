from django.urls import path
from . import editor, panel
from .models import Category, Scene, Tour

app_name = "panel"
urlpatterns = [
    path("", panel.home, name="home"),
    path("ingresar/", panel.PanelLoginView.as_view(), name="login"),
    path("salir/", panel.PanelLogoutView.as_view(), name="logout"),
    path("recorridos/", panel.tours, name="tours"),
    path("recorridos/nuevo/", panel.tour_edit, name="tour_add"),
    path("recorridos/<int:pk>/", panel.tour_edit, name="tour_edit"),
    path("recorridos/<int:pk>/eliminar/", panel.delete, {"model": Tour}, name="tour_delete"),
    path("recorridos/<int:pk>/vista-previa/", panel.tour_preview, name="tour_preview"),
    path("recorridos/<int:tour_id>/escenas/nueva/", panel.scene_edit, name="scene_add"),
    path("recorridos/<int:tour_id>/escenas/<int:scene_id>/", panel.scene_edit, name="scene_edit"),
    path("recorridos/<int:tour_id>/escenas/<int:pk>/eliminar/", panel.delete, {"model": Scene}, name="scene_delete"),
    path("categorias/", panel.categories, name="categories"),
    path("categorias/nueva/", panel.category_edit, name="category_add"),
    path("categorias/<int:pk>/", panel.category_edit, name="category_edit"),
    path("categorias/<int:pk>/eliminar/", panel.delete, {"model": Category}, name="category_delete"),
]
for route, view, name in [
    ("editor/", editor.page, "editor"), ("editor/data/", editor.data, "editor_data"),
    ("editor/points/", editor.create_point, "points"), ("editor/points/<int:point_id>/", editor.point_detail, "point_detail"),
    ("editor/orientation/", editor.orientation, "orientation"), ("vista-previa/", editor.preview, "preview"),
    ("panorama/", editor.panorama, "panorama"),
]:
    urlpatterns.append(path(f"recorridos/<int:tour_id>/escenas/<int:scene_id>/{route}", panel.scene_route(view), name=name))
