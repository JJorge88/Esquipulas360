from django.urls import path
from . import views

app_name = "stand"
urlpatterns = [
    path("panel/stand/", views.index, name="index"),
    path("panel/stand/<uuid:sid>/", views.operator, name="operator"),
    path("panel/stand/<uuid:sid>/command/", views.command, name="command"),
    path("panel/stand/<uuid:sid>/code/", views.code, name="code"),
    path("panel/stand/<uuid:sid>/spectator/", views.open_spectator, name="open_spectator"),
    path("stand/", views.join, name="join"),
    path("stand/<uuid:sid>/viewer/", views.viewer, name="viewer"),
    path("stand/<uuid:sid>/spectator/", views.spectator, name="spectator"),
    path("stand/<uuid:sid>/state/<str:role>/", views.state, name="state"),
    path("stand/<uuid:sid>/panorama/<int:scene_id>/", views.panorama, name="panorama"),
]
