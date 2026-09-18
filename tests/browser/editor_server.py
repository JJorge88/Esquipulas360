"""Disposable browser-test server. Never touches the workspace database or users."""
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from django.conf import settings


def stop(*args):
    raise SystemExit(0)


signal.signal(signal.SIGTERM, stop)
manifest = BASE_DIR / "artifacts" / "editor-session.json"
with tempfile.TemporaryDirectory(prefix="esquipulas-editor-tests-") as directory:
    settings.DATABASES["default"]["NAME"] = str(Path(directory) / "browser.sqlite3")
    settings.MEDIA_ROOT = str(Path(directory) / "media")
    settings.DEBUG = True
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.files import File
    from django.core.management import call_command
    from django.test import Client
    from tours.models import Tour, Scene, NavigationPoint

    call_command("migrate", verbosity=0)
    call_command("import_phase1", stdout=io.StringIO())
    user = get_user_model().objects.create_superuser("browser-editor", email="", password=None)
    client = Client()
    client.force_login(user)
    data = {"cookie": client.cookies[settings.SESSION_COOKIE_NAME].value, "scenes": {}}
    demo = Tour.objects.get(slug="demostracion")
    for name in ("flow", "drag", "failure", "orientation", "mobile", "pending"):
        tour = Tour.objects.create(name=f"Borrador {name}", slug=f"borrador-{name}", description="Datos temporales de prueba.", category=demo.category)
        scenes = []
        for original in demo.scenes.all():
            with original.panorama.open("rb") as stream:
                scene = Scene(tour=tour, key=original.key, name=original.name, panorama=File(stream, name=Path(original.panorama.name).name), yaw=original.yaw, pitch=original.pitch)
                scene.save()
                scenes.append(scene)
        NavigationPoint.objects.create(origin=scenes[0], destination=scenes[1], label="Punto guardado", yaw=0, pitch=0)
        NavigationPoint.objects.create(origin=scenes[1], destination=scenes[0], label="Volver a azul", yaw=90, pitch=5)
        data["scenes"][name] = {"a": scenes[0].pk, "b": scenes[1].pk, "slug": tour.slug}
    data["demo"] = {"a": demo.scenes.get(key="azul").pk, "b": demo.scenes.get(key="ambar").pk}
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text(json.dumps(data))
    try:
        call_command("runserver", "127.0.0.1:8013", use_reloader=False)
    finally:
        manifest.unlink(missing_ok=True)
