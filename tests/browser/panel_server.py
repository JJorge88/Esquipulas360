"""Ephemeral panel tests, including a real login. No credentials or edits in the local DB."""
import io
import json
import os
from pathlib import Path
import secrets
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
manifest = BASE_DIR / "artifacts" / "panel-session.json"
with tempfile.TemporaryDirectory(prefix="esquipulas-panel-tests-") as directory:
    settings.DATABASES["default"]["NAME"] = str(Path(directory) / "browser.sqlite3")
    settings.MEDIA_ROOT = str(Path(directory) / "media")
    settings.DEBUG = True
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import Client
    from tours.models import Tour

    call_command("migrate", verbosity=0)
    call_command("import_phase1", stdout=io.StringIO())
    password = secrets.token_urlsafe(32)
    user = get_user_model().objects.create_superuser("Equipo Esquipulas", email="", password=password)
    client = Client()
    client.force_login(user)
    demo = Tour.objects.get(slug="demostracion")
    data = {"username": user.username, "password": password, "cookie": client.cookies[settings.SESSION_COOKIE_NAME].value,
            "demo": {"id": demo.pk, "a": demo.scenes.get(key="azul").pk, "b": demo.scenes.get(key="ambar").pk}}
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text(json.dumps(data))
    manifest.chmod(0o600)
    try:
        call_command("runserver", "127.0.0.1:8014", use_reloader=False)
    finally:
        manifest.unlink(missing_ok=True)
