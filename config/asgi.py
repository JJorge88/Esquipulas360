import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application
http_application = get_asgi_application()
from django.conf import settings
from django.urls import re_path
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from stand.consumers import StandConsumer

application = ProtocolTypeRouter({
    "http": http_application,
    "websocket": OriginValidator(AuthMiddlewareStack(URLRouter([
        re_path(r"^stand/(?P<sid>[0-9a-f-]{36})/socket/(?P<role>operator|viewer|spectator)/$", StandConsumer.as_asgi()),
    ])), settings.STAND_ALLOWED_ORIGINS),
})
