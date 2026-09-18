import io
import json
import math
import tempfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.test import TestCase, SimpleTestCase, override_settings

from .content import viewer_data
from .images import validate_cover, validate_panorama
from .models import Category, Tour, Scene, NavigationPoint

def picture(name="panorama.png", size=(1024, 512), format="PNG", **kwargs):
    output = io.BytesIO()
    Image.new("RGB", size, (25, 60, 85)).save(output, format=format, **kwargs)
    return SimpleUploadedFile(name, output.getvalue(), content_type="application/octet-stream")

class MediaTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_dir = tempfile.TemporaryDirectory()
        cls.media_settings = override_settings(MEDIA_ROOT=cls.media_dir.name)
        cls.media_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_settings.disable()
        cls.media_dir.cleanup()
        super().tearDownClass()

    def make_tour(self, slug="prueba", published=False):
        category, _ = Category.objects.get_or_create(slug="vistas", defaults={"name": "Vistas"})
        tour = Tour.objects.create(name=slug.title(), slug=slug, description="Una descripción de prueba.", category=category)
        if published:
            scene = Scene.objects.create(tour=tour, name="Primera", panorama=picture())
            tour.initial_scene = scene
            tour.status = Tour.Status.AVAILABLE
            tour.save()
        return tour

class ImageTests(SimpleTestCase):
    def test_supported_cover_formats_check_real_content_not_mime(self):
        for suffix, format in (("jpg", "JPEG"), ("jpeg", "JPEG"), ("png", "PNG"), ("webp", "WEBP")):
            validate_cover(picture(f"photo.{suffix}", format=format))

    def test_only_jpeg_and_png_panoramas(self):
        validate_panorama(picture())
        validate_panorama(picture("photo.jpg", format="JPEG"))
        with self.assertRaises(ValidationError):
            validate_panorama(picture("photo.webp", format="WEBP"))

    def test_fake_image_and_disguised_extension(self):
        for file in (SimpleUploadedFile("fake.png", b"<script>not an image</script>"), picture("disguised.png", format="JPEG"), picture("photo.svg")):
            with self.assertRaises(ValidationError): validate_cover(file)

    def test_truncated_file_is_rejected(self):
        file = picture("photo.jpg", format="JPEG")
        with self.assertRaises(ValidationError):
            validate_panorama(SimpleUploadedFile("broken.jpg", file.read()[:200]))

    @override_settings(PANORAMA_MAX_BYTES=200, COVER_MAX_BYTES=200)
    def test_byte_limits(self):
        for validator in (validate_cover, validate_panorama):
            with self.assertRaisesMessage(ValidationError, "supera el máximo"): validator(picture())

    def test_minimum_dimensions(self):
        with self.assertRaisesMessage(ValidationError, "al menos"): validate_panorama(picture(size=(400, 200)))
        with self.assertRaisesMessage(ValidationError, "al menos"): validate_cover(picture(size=(20, 20)))

    @override_settings(IMAGE_MAX_DIMENSION=1500)
    def test_maximum_side(self):
        with self.assertRaisesMessage(ValidationError, "supera el límite"): validate_panorama(picture(size=(2048, 1024)))

    @override_settings(IMAGE_MAX_PIXELS=500000)
    def test_maximum_pixels(self):
        with self.assertRaisesMessage(ValidationError, "supera el límite"): validate_panorama(picture())

    def test_ratio_tolerance_inside_and_outside(self):
        validate_panorama(picture(size=(2020, 1000)))
        validate_panorama(picture(size=(1980, 1000)))
        for size in ((2021, 1000), (1979, 1000), (1024, 1024)):
            with self.assertRaisesMessage(ValidationError, "proporción 2:1"): validate_panorama(picture(size=size))

    def test_panorama_exif_rotation_is_rejected(self):
        exif = Image.Exif()
        exif[274] = 6
        with self.assertRaisesMessage(ValidationError, "EXIF"):
            validate_panorama(picture("rotated.jpg", format="JPEG", exif=exif))

    def test_animated_png_is_rejected(self):
        out = io.BytesIO()
        image = Image.new("RGB", (1024, 512), "red")
        image.save(out, format="PNG", save_all=True, append_images=[Image.new("RGB", (1024, 512), "blue")])
        with self.assertRaisesMessage(ValidationError, "estática"):
            validate_panorama(SimpleUploadedFile("animated.png", out.getvalue()))

class ModelTests(MediaTestCase):
    def test_publish_requires_saved_scenes_and_initial_scene(self):
        tour = self.make_tour()
        tour.status = Tour.Status.AVAILABLE
        with self.assertRaisesMessage(ValidationError, "escena inicial"): tour.save()
        tour.refresh_from_db()
        self.assertEqual(tour.status, Tour.Status.DRAFT)

    def test_initial_scene_must_belong_to_tour_even_in_draft(self):
        first, second = self.make_tour(), self.make_tour("segundo", True)
        first.initial_scene = second.initial_scene
        with self.assertRaisesMessage(ValidationError, "mismo recorrido"): first.save()

    def test_all_scene_images_required_to_publish(self):
        tour = self.make_tour()
        a = Scene.objects.create(tour=tour, name="A", panorama=picture())
        Scene.objects.create(tour=tour, name="B")
        tour.initial_scene, tour.status = a, Tour.Status.DEMO
        with self.assertRaisesMessage(ValidationError, "Falta la panorámica"): tour.save()

    def test_missing_or_corrupt_file_blocks_publication(self):
        for kind in ("missing", "corrupt"):
            tour = self.make_tour(kind)
            scene = Scene.objects.create(tour=tour, name="A", panorama=picture())
            path = Path(scene.panorama.path)
            if kind == "missing": path.unlink()
            else: path.write_bytes(b"invalid file")
            tour.initial_scene, tour.status = scene, Tour.Status.AVAILABLE
            with self.assertRaises(ValidationError): tour.save()

    def test_removing_public_panorama_or_adding_incomplete_scene_is_blocked(self):
        tour = self.make_tour(published=True)
        scene = tour.initial_scene
        scene.panorama = ""
        with self.assertRaisesMessage(ValidationError, "recorrido publicado"): scene.save()
        with self.assertRaisesMessage(ValidationError, "recorrido publicado"):
            Scene.objects.create(tour=tour, name="Sin foto")

    def test_valid_edits_of_published_scene_are_allowed(self):
        tour = self.make_tour(published=True)
        scene = tour.initial_scene
        scene.text = "Texto actualizado"
        scene.panorama = picture("nuevo.jpg", format="JPEG")
        scene.save()
        self.assertEqual(Tour.objects.get(pk=tour.pk).publication_errors(), [])

    def test_scene_cannot_move_to_another_tour(self):
        first, second = self.make_tour(), self.make_tour("segundo")
        scene = Scene.objects.create(tour=first, name="A")
        scene.tour = second
        with self.assertRaisesMessage(ValidationError, "trasladarse"): scene.save()

    def test_destinations_must_be_same_tour_and_different_scene(self):
        tour, other = self.make_tour(published=True), self.make_tour("otro", True)
        for destination in (tour.initial_scene, other.initial_scene):
            with self.assertRaises(ValidationError):
                NavigationPoint.objects.create(origin=tour.initial_scene, destination=destination, label="Ir")

    def test_angles_are_finite_and_bounded(self):
        tour = self.make_tour()
        for yaw, pitch in ((181, 0), (0, -91), (math.inf, 0), (0, math.nan)):
            with self.assertRaises(ValidationError): Scene.objects.create(tour=tour, name="A", yaw=yaw, pitch=pitch)

    def test_angular_coordinates_match_viewer_axes(self):
        for yaw, pitch, expected in ((0, 0, [0, 0, -3.5]), (90, 0, [-3.5, 0, 0]), (-90, 0, [3.5, 0, 0]), (0, 90, [0, 3.5, 0])):
            actual = NavigationPoint(yaw=yaw, pitch=pitch).position()
            for a, e in zip(actual, expected): self.assertAlmostEqual(a, e)

    def test_public_scene_deletion_is_protected_including_bulk(self):
        tour = self.make_tour(published=True)
        extra = Scene.objects.create(tour=tour, name="Extra", panorama=picture())
        with self.assertRaises(ProtectedError), transaction.atomic(): extra.delete()
        with self.assertRaises(ProtectedError), transaction.atomic(): Scene.objects.filter(pk=extra.pk).delete()
        with self.assertRaises(RestrictedError): tour.initial_scene.delete()

    def test_draft_scene_destination_is_restricted_until_points_removed(self):
        tour = self.make_tour()
        a = Scene.objects.create(tour=tour, name="A")
        b = Scene.objects.create(tour=tour, name="B")
        point = NavigationPoint.objects.create(origin=a, destination=b, label="Ir")
        with self.assertRaises(RestrictedError): b.delete()
        point.delete()
        b.delete()

    def test_deleting_whole_tour_handles_cycles_and_retains_originals(self):
        tour = self.make_tour(published=True)
        a = tour.initial_scene
        b = Scene.objects.create(tour=tour, name="B", panorama=picture())
        NavigationPoint.objects.create(origin=a, destination=b, label="Ida")
        NavigationPoint.objects.create(origin=b, destination=a, label="Vuelta")
        paths = [Path(a.panorama.path), Path(b.panorama.path), Path(a.thumbnail.path)]
        tour.delete()
        self.assertFalse(Scene.objects.exists())
        self.assertFalse(NavigationPoint.objects.exists())
        self.assertTrue(all(path.exists() for path in paths))

    def test_file_names_are_unique_replacements_keep_originals_and_thumbnail_is_small(self):
        tour = self.make_tour()
        original = picture()
        raw = original.read(); original.seek(0)
        a = Scene.objects.create(tour=tour, name="A", panorama=original)
        b = Scene.objects.create(tour=tour, name="B", panorama=picture())
        self.assertNotEqual(a.panorama.name, b.panorama.name)
        path = Path(a.panorama.path)
        self.assertEqual(path.read_bytes(), raw)
        with Image.open(a.thumbnail.path) as image:
            self.assertLessEqual(image.width, 640)
            self.assertLessEqual(image.height, 360)
        a.panorama = picture(); a.save()
        self.assertTrue(path.exists())
        self.assertNotEqual(str(path), a.panorama.path)

    def test_unsafe_bulk_writes_cannot_bypass_publication_validation(self):
        tour = self.make_tour()
        with self.assertRaises(ValidationError): Tour.objects.filter(pk=tour.pk).update(status="available")
        with self.assertRaises(ValidationError): Tour.objects.bulk_update([tour], ["status"])
        with self.assertRaises(ValidationError): Scene.objects.bulk_create([Scene(tour=tour, name="A")])

class ImportAndPublicTests(MediaTestCase):
    def setUp(self):
        call_command("import_phase1", stdout=io.StringIO())

    def test_import_is_idempotent_and_preserves_editorial_changes(self):
        tour = Tour.objects.get(slug="demostracion")
        tour.name = "Nombre editado"; tour.slug = "nuevo-slug"; tour.status = "draft"; tour.save()
        scene = tour.scenes.get(key="azul"); scene.text = "Texto editado"; scene.save()
        NavigationPoint.objects.filter(origin=scene).delete()
        files_before = sorted(str(p) for p in Path(self.media_dir.name).rglob("*"))
        call_command("import_phase1", stdout=io.StringIO())
        self.assertEqual((Category.objects.count(), Tour.objects.count(), Scene.objects.count(), NavigationPoint.objects.count()), (4, 4, 2, 1))
        tour.refresh_from_db(); scene.refresh_from_db()
        self.assertEqual(tour.name, "Nombre editado")
        self.assertEqual(tour.status, "draft")
        self.assertEqual(scene.text, "Texto editado")
        self.assertEqual(files_before, sorted(str(p) for p in Path(self.media_dir.name).rglob("*")))

    def test_existing_slug_is_not_overwritten(self):
        tour = Tour.objects.get(slug="mirador")
        tour.legacy_key = None; tour.name = "Mirador editado"; tour.save()
        call_command("import_phase1", stdout=io.StringIO())
        self.assertEqual(Tour.objects.get(slug="mirador").name, "Mirador editado")

    def test_missing_source_file_reports_command_error_without_partial_rows(self):
        Tour.objects.all().delete(); Category.objects.all().delete()
        with patch("tours.management.commands.import_phase1.Command.source_path", return_value=Path(self.media_dir.name) / "missing.png"):
            with self.assertRaisesMessage(CommandError, "generate_panoramas"):
                call_command("import_phase1", stdout=io.StringIO())
        self.assertEqual(Tour.objects.count(), 0)

    def test_public_routes_and_existing_slugs(self):
        for path in ("/", "/explorar/", "/recorridos/demostracion/"):
            self.assertEqual(self.client.get(path).status_code, 200)
        for slug in ("mirador", "basilica", "parque-central", "inexistente"):
            self.assertEqual(self.client.get(f"/recorridos/{slug}/").status_code, 404)

    @override_settings(DEBUG=False)
    def test_custom_404(self):
        self.assertContains(self.client.get("/recorridos/inexistente/"), "todavía no está aquí", status_code=404)

    def test_search_accents_case_combination_and_reset(self):
        for query in ("basilica", "BASÍLICA", " Basílica "):
            response = self.client.get("/explorar/", {"q": query, "categoria": "patrimonio"})
            self.assertEqual(response.context["result_count"], 1)
            self.assertContains(response, "Basílica")
        self.assertContains(self.client.get("/explorar/", {"q": "basilica", "categoria": "vistas"}), "Restablecer búsqueda")
        self.assertEqual(self.client.get("/explorar/", {"categoria": "inventado"}).context["result_count"], 4)

    def test_drafts_are_hidden_everywhere_even_demo_links(self):
        tour = Tour.objects.get(slug="demostracion")
        tour.status = "draft"; tour.save()
        for path in ("/", "/explorar/"):
            response = self.client.get(path)
            self.assertNotContains(response, '/recorridos/demostracion/')
            self.assertNotContains(response, tour.name)
        self.assertEqual(self.client.get("/recorridos/demostracion/").status_code, 404)
        self.assertNotIn(("demostracion", "Demostración"), list(self.client.get("/explorar/").context["categories"]))

    def test_upcoming_cards_have_no_links_to_viewer(self):
        response = self.client.get("/explorar/")
        for slug in ("mirador", "basilica", "parque-central"):
            self.assertNotContains(response, f'href="/recorridos/{slug}/"')

    def test_edits_featured_and_order_are_read_from_database(self):
        tour = Tour.objects.get(slug="basilica")
        tour.name = "Basílica editada"; tour.order = 1; tour.save()
        home = self.client.get("/")
        self.assertEqual(home.context["places"][0]["name"], "Basílica editada")
        tour.featured = False; tour.save()
        self.assertNotContains(self.client.get("/"), "Basílica editada")
        self.assertContains(self.client.get("/explorar/"), "Basílica editada")

    def test_public_pages_do_not_read_legacy_json(self):
        with patch("tours.legacy.load_tours", side_effect=AssertionError("Must not read JSON")):
            self.assertEqual(self.client.get("/explorar/").context["result_count"], 4)

    def test_external_file_loss_hides_broken_publication(self):
        scene = Scene.objects.get(key="azul")
        Path(scene.panorama.path).unlink()
        self.assertEqual(self.client.get("/recorridos/demostracion/").status_code, 404)
        self.assertNotContains(self.client.get("/explorar/"), '/recorridos/demostracion/')

    def test_public_json_only_contains_viewer_fields_and_escapes_editorial_html(self):
        tour = Tour.objects.get(slug="demostracion")
        scene = tour.scenes.get(key="azul")
        scene.text = '</script><script>window.editorialExecuted=true</script>'; scene.save()
        response = self.client.get("/recorridos/demostracion/")
        self.assertNotContains(response, '</script><script>window.editorialExecuted=true')
        data = response.context["tour_data"]
        self.assertEqual(set(data), {"name", "description", "status", "initial_scene", "panorama_ratio_tolerance", "scenes"})
        self.assertNotIn("audio", data["scenes"][0])
        self.assertNotIn("legacy_key", json.dumps(data))
        self.assertTrue(data["scenes"][0]["panorama"].startswith("/media/panoramas/originals/"))
        self.assertEqual(data["scenes"][0]["hotspots"][0]["destination"], "ambar")

    def test_empty_database_has_working_empty_states(self):
        Tour.objects.all().delete()
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertContains(self.client.get("/explorar/"), "Aún no encontramos")

class AdminTests(MediaTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("editor-test", password=None, is_staff=True)
        self.tour = self.make_tour()

    def grant(self, *codenames):
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label="tours", codename__in=codenames))
        self.client.force_login(self.user)

    def test_anonymous_and_nonstaff_cannot_enter_admin(self):
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.user.is_staff = False; self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/admin/tours/tour/").status_code, 302)

    def test_staff_without_permissions_cannot_read_or_write_tours(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/admin/tours/tour/").status_code, 403)
        self.assertEqual(self.client.post("/admin/tours/tour/add/", {}).status_code, 403)

    def test_view_permission_does_not_allow_editing_or_uploading(self):
        self.grant("view_tour", "view_scene")
        self.assertEqual(self.client.get("/admin/tours/tour/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/tours/tour/{self.tour.pk}/change/").status_code, 200)
        self.assertEqual(self.client.post(f"/admin/tours/tour/{self.tour.pk}/change/", {"name": "No"}).status_code, 403)
        self.assertEqual(self.client.post("/admin/tours/scene/add/", {"panorama": picture()}).status_code, 403)

    def test_admin_in_spanish_and_invalid_publication_has_form_error(self):
        self.grant("add_tour", "view_tour", "change_tour")
        response = self.client.post("/admin/tours/tour/add/", {"name": "Nuevo", "slug": "nuevo", "description": "Descripción", "category": self.tour.category_id, "status": "available", "order": 0, "_save": "Guardar"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "escena inicial")
        self.assertContains(response, "Esquipulas 360° · Administración")
        self.assertFalse(Tour.objects.filter(slug="nuevo").exists())

    def test_add_scene_upload_and_cross_tour_destination_validation(self):
        self.grant("add_scene", "view_scene", "change_scene", "view_tour", "add_navigationpoint", "view_navigationpoint")
        response = self.client.post("/admin/tours/scene/add/", {"tour": self.tour.pk, "name": "A", "order": 0, "yaw": 0, "pitch": 0, "text": "", "panorama": picture(), "_save": "Guardar", "hotspots-TOTAL_FORMS": 0, "hotspots-INITIAL_FORMS": 0, "hotspots-MIN_NUM_FORMS": 0, "hotspots-MAX_NUM_FORMS": 0})
        self.assertEqual(response.status_code, 302)
        origin = Scene.objects.get(tour=self.tour)
        other = self.make_tour("otro", True).initial_scene
        response = self.client.post("/admin/tours/navigationpoint/add/", {"origin": origin.pk, "destination": other.pk, "label": "Inválido", "yaw": 0, "pitch": 0})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NavigationPoint.objects.exists())

    def test_scene_inline_saves_connected_point(self):
        self.grant("view_scene", "change_scene", "add_navigationpoint", "view_navigationpoint", "change_navigationpoint")
        a = Scene.objects.create(tour=self.tour, name="A")
        b = Scene.objects.create(tour=self.tour, name="B")
        response = self.client.post(f"/admin/tours/scene/{a.pk}/change/", {
            "name": "A", "order": 0, "yaw": 0, "pitch": 0, "text": "",
            "hotspots-TOTAL_FORMS": "1", "hotspots-INITIAL_FORMS": "0", "hotspots-MIN_NUM_FORMS": "0", "hotspots-MAX_NUM_FORMS": "1000",
            "hotspots-0-destination": b.pk, "hotspots-0-label": "Ir a B", "hotspots-0-yaw": 90, "hotspots-0-pitch": 5,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(a.hotspots.get().destination, b)

    def test_scene_admin_rejects_corrupt_upload_with_clear_error(self):
        self.grant("add_scene", "view_scene")
        response = self.client.post("/admin/tours/scene/add/", {"tour": self.tour.pk, "name": "A", "order": 0, "yaw": 0, "pitch": 0, "panorama": SimpleUploadedFile("fake.png", b"fake")})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Scene.objects.exists())
        self.assertIn("panorama", response.context["adminform"].form.errors)

    def test_published_scene_admin_single_and_bulk_deletes_are_blocked(self):
        self.grant("view_scene", "delete_scene")
        tour = self.make_tour("publicado", True)
        scene = Scene.objects.create(tour=tour, name="Extra", panorama=picture())
        self.assertEqual(self.client.post(f"/admin/tours/scene/{scene.pk}/delete/", {"post": "yes"}).status_code, 403)
        response = self.client.post("/admin/tours/scene/", {"action": "delete_selected", "_selected_action": [scene.pk], "post": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "borrador")
        self.assertTrue(Scene.objects.filter(pk=scene.pk).exists())

    def test_permissions_allow_complete_editorial_flow(self):
        self.grant("add_tour", "change_tour", "view_tour", "view_scene")
        scene = Scene.objects.create(tour=self.tour, name="Inicio", panorama=picture())
        data = {"name": "Publicado", "slug": self.tour.slug, "description": "Listo", "category": self.tour.category_id, "status": "available", "initial_scene": scene.pk, "order": 0,
                "scenes-TOTAL_FORMS": 1, "scenes-INITIAL_FORMS": 1, "scenes-MIN_NUM_FORMS": 0, "scenes-MAX_NUM_FORMS": 1000, "scenes-0-id": scene.pk, "scenes-0-tour": self.tour.pk}
        response = self.client.post(f"/admin/tours/tour/{self.tour.pk}/change/", data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(f"/recorridos/{self.tour.slug}/").status_code, 200)
