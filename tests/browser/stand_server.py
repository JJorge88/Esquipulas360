"""Isolated ASGI/Redis stand fixture; never uses local content or credentials."""
import io
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import tempfile
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings


def stop(*args):
    raise SystemExit(0)


signal.signal(signal.SIGTERM, stop)
manifest = BASE_DIR / 'artifacts' / 'stand-session.json'
with tempfile.TemporaryDirectory(prefix='esquipulas-stand-tests-') as directory:
    settings.DATABASES['default']['NAME'] = str(Path(directory) / 'browser.sqlite3')
    settings.MEDIA_ROOT = str(Path(directory) / 'media')
    settings.DEBUG = True
    settings.SESSION_COOKIE_SECURE = settings.CSRF_COOKIE_SECURE = False
    settings.STAND_REDIS_PREFIX = 'test-browser-stand-' + secrets.token_hex(8)
    settings.CHANNEL_LAYERS['default']['CONFIG']['prefix'] = settings.STAND_REDIS_PREFIX + '-channels'
    settings.STAND_ALLOWED_ORIGINS = ['http://127.0.0.1:8016']
    settings.STAND_PAIR_ATTEMPTS = 100
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import Client
    from django.utils import timezone
    from tours.models import Tour, Scene
    from stand import services
    from stand.models import StandSession

    call_command('migrate', verbosity=0)
    call_command('import_phase1', stdout=io.StringIO())
    user = get_user_model().objects.create_superuser('Operador de prueba', email='')
    user.set_unusable_password(); user.save()
    client = Client(); client.force_login(user)
    demo = Tour.objects.get(slug='demostracion')
    other = Tour.objects.create(name='Recorrido alternativo', slug='alternativo', category=demo.category, description='Prueba de cambio de recorrido.')
    other.initial_scene = Scene.objects.create(tour=other, name='Otra perspectiva', key='otra', panorama=demo.initial_scene.panorama.name)
    other.status = 'available'; other.save()
    draft = Tour.objects.create(name='Borrador privado', slug='privado', category=demo.category, description='No debe aparecer en stand.')
    expired = services.create(user, demo.pk)
    old_code = services.store().get(services.key(expired.pk, 'code'))
    StandSession.objects.filter(pk=expired.pk).update(code_expires_at=timezone.now() - timedelta(seconds=1), phase='ended')
    # An expired unused code on an otherwise active session, owned by a second test user.
    expiry_user = get_user_model().objects.create_superuser('Caducidad de prueba', email='')
    expiry_user.set_unusable_password(); expiry_user.save()
    expired = services.create(expiry_user, demo.pk)
    expired_code = services.store().get(services.key(expired.pk, 'code'))
    StandSession.objects.filter(pk=expired.pk).update(code_expires_at=timezone.now() - timedelta(seconds=1))
    data = {'cookie': client.cookies[settings.SESSION_COOKIE_NAME].value, 'demo': demo.pk, 'other': other.pk,
        'draft': draft.pk, 'expiredCode': expired_code}
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text(json.dumps(data)); manifest.chmod(0o600)
    try:
        call_command('runserver', '127.0.0.1:8016', use_reloader=False)
    finally:
        manifest.unlink(missing_ok=True)
        store = services.store()
        keys = list(store.scan_iter(settings.STAND_REDIS_PREFIX + '*'))
        if keys: store.delete(*keys)
        store.close()
