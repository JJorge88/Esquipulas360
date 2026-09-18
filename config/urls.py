from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from tours import views

urlpatterns = [
    path("", views.home, name="home"),
    path("explorar/", views.explore, name="explore"),
    path("recorridos/<slug:slug>/", views.viewer, name="viewer"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
handler404 = "tours.views.not_found"
