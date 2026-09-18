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
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "tours.apps.ToursConfig"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "tours.context.site_settings"]}}]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
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

# Validated before decoding images. Limits are independent of browser/GPU limits.
COVER_MAX_BYTES = int(os.getenv("COVER_MAX_BYTES", 12 * 1024 * 1024))
COVER_MIN_WIDTH = int(os.getenv("COVER_MIN_WIDTH", 320))
COVER_MIN_HEIGHT = int(os.getenv("COVER_MIN_HEIGHT", 180))
PANORAMA_MAX_BYTES = int(os.getenv("PANORAMA_MAX_BYTES", 20 * 1024 * 1024))
PANORAMA_MIN_WIDTH = int(os.getenv("PANORAMA_MIN_WIDTH", 1024))
PANORAMA_MIN_HEIGHT = int(os.getenv("PANORAMA_MIN_HEIGHT", 512))
IMAGE_MAX_DIMENSION = int(os.getenv("IMAGE_MAX_DIMENSION", 8192))
IMAGE_MAX_PIXELS = int(os.getenv("IMAGE_MAX_PIXELS", 33554432))
PANORAMA_RATIO_TOLERANCE = float(os.getenv("PANORAMA_RATIO_TOLERANCE", "0.01"))
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
