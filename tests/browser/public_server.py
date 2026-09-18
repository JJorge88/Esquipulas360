"""Stable demonstration fixtures for public regressions, separate from editorial data."""
import io
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
with tempfile.TemporaryDirectory(prefix="esquipulas-public-tests-") as directory:
    settings.DATABASES["default"]["NAME"] = str(Path(directory) / "browser.sqlite3")
    settings.MEDIA_ROOT = str(Path(directory) / "media")
    settings.DEBUG = True
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", verbosity=0)
    call_command("import_phase1", stdout=io.StringIO())
    call_command("runserver", "127.0.0.1:8015", use_reloader=False)
