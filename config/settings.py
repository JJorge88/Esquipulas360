import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"true", "1", "yes"}

DEBUG = env_bool("DJANGO_DEBUG")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "replace-with-a-random-local-secret":
    raise ImproperlyConfigured("Configura DJANGO_SECRET_KEY en .env (consulta README.md).")
ALLOWED_HOSTS = [s.strip() for s in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if s.strip()]
CSRF_TRUSTED_ORIGINS = [s.strip() for s in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if s.strip()]
INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.staticfiles", "tours.apps.ToursConfig"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "tours.context.site_settings"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
LANGUAGE_CODE = "es-gt"
TIME_ZONE = "America/Guatemala"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if env_bool("DJANGO_TRUST_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
