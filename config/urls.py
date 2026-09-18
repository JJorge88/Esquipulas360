from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.contrib import admin
from tours import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("stand.urls")),
    path("panel/", include("tours.panel_urls")),
    path("", views.home, name="home"),
    path("explorar/", views.explore, name="explore"),
    path("recorridos/<slug:slug>/", views.viewer, name="viewer"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
handler404 = "tours.views.not_found"
