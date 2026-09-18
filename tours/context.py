import json
from django.conf import settings
from .content import asset_url, public_tours, present

def site_settings(request):
    with (settings.BASE_DIR / "content" / "site.json").open(encoding="utf-8") as source:
        site = json.load(source)
    demo = None if request.path.startswith(("/admin/", "/panel/", "/stand/")) else next((t for t in public_tours(request) if t.status == "demo"), None)
    return {"demo": present(demo) if demo else None, "site": {**site, "hero_desktop_url": asset_url(site["hero_desktop"]) if site.get("hero_desktop") else None, "hero_mobile_url": asset_url(site["hero_mobile"]) if site.get("hero_mobile") else None}}
