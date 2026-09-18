import math
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from tours.legacy import CATEGORIES, load_tours, ContentError
from tours.images import validate_cover, validate_panorama
from tours.models import Category, Tour, Scene, NavigationPoint

class Command(BaseCommand):
    help = "Importa la fase 1 sin duplicar ni sobrescribir recorridos existentes. Genera antes las panorámicas."

    def handle(self, *args, **options):
        try:
            source = load_tours()
            pending = []
            for item in source:
                if Tour.objects.filter(Q(legacy_key=item["id"]) | Q(slug=item["slug"])).exists():
                    self.stdout.write(f"Conservado sin cambios: {item['slug']}")
                    continue
                pending.append(item)
                files = [(item.get("cover"), validate_cover)] + [(s["panorama"], validate_panorama) for s in item["scenes"]]
                for name, validator in files:
                    if not name:
                        continue
                    path = self.source_path(name)
                    if not path.is_file():
                        raise CommandError(f"Falta {name}. Ejecuta primero: .venv/bin/python scripts/generate_panoramas.py")
                    with path.open("rb") as stream:
                        validator(File(stream, name=path.name))
            # Database writes occur only after all required source files validate.
            with transaction.atomic():
                for item in pending:
                    self.import_tour(item)
                    self.stdout.write(self.style.SUCCESS(f"Importado: {item['slug']}"))
            self.stdout.write(self.style.SUCCESS(f"Finalizado: {len(pending)} recorridos nuevos; {len(source) - len(pending)} conservados."))
        except (ValidationError, ContentError, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

    @staticmethod
    def source_path(name):
        root = settings.MEDIA_ROOT if name.startswith("media/") else settings.BASE_DIR / "static"
        return Path(root) / (name[6:] if name.startswith("media/") else name)

    def assign_file(self, instance, attribute, name):
        path = self.source_path(name)
        with path.open("rb") as stream:
            setattr(instance, attribute, File(stream, name=path.name))
            instance.save()

    def import_tour(self, item):
        category, _ = Category.objects.get_or_create(slug=item["category"], defaults={"name": CATEGORIES[item["category"]]})
        tour = Tour.objects.create(name=item["name"], slug=item["slug"], description=item["description"], category=category,
                                   legacy_key=item["id"], featured=item["status"] == "upcoming", order=0 if item["status"] == "demo" else {"mirador": 10, "basilica": 20, "parque-central": 30}.get(item["id"], 40))
        if item.get("cover"):
            self.assign_file(tour, "cover", item["cover"])
        scenes = {}
        for order, data in enumerate(item["scenes"]):
            scene = Scene(tour=tour, key=data["id"], name=data["name"], order=order, yaw=data["orientation"]["yaw"], pitch=data["orientation"]["pitch"], text=data.get("text", ""))
            self.assign_file(scene, "panorama", data["panorama"])
            scenes[data["id"]] = scene
        for data in item["scenes"]:
            for point in data["hotspots"]:
                x, y, z = point["position"]
                radius = math.sqrt(x*x + y*y + z*z)
                NavigationPoint.objects.create(origin=scenes[data["id"]], destination=scenes[point["destination"]], key=point["id"], label=point["label"], yaw=math.degrees(math.atan2(-x, -z)), pitch=math.degrees(math.asin(y / radius)))
        tour.initial_scene = scenes.get(item["initial_scene"])
        tour.status = item["status"]
        tour.save()
