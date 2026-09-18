"""Panel contracts: real permissions, uploads, deletion and shared private editor."""
import json
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from .editor import orientation_data, point_data
from .models import Category, NavigationPoint, Scene, Tour
from .tests import MediaTestCase, picture


class PanelTests(MediaTestCase):
    def setUp(self):
        self.tour = self.make_tour()
        self.a = Scene.objects.create(tour=self.tour, name="Escena A", panorama=picture())
        self.b = Scene.objects.create(tour=self.tour, name="Escena B", panorama=picture())
        self.point = NavigationPoint.objects.create(origin=self.a, destination=self.b, label="Ir a B")
        self.user = get_user_model().objects.create_user("responsable", password=None, is_staff=True)
        self.grant(*Permission.objects.filter(content_type__app_label="tours").values_list("codename", flat=True))

    def grant(self, *permissions):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label="tours", codename__in=permissions))
        self.client.force_login(self.user)

    def url(self, name, *args):
        return reverse(f"panel:{name}", args=args)

    def tour_payload(self, **extra):
        return {"name": self.tour.name, "slug": self.tour.slug, "description": self.tour.description,
                "category": self.tour.category_id, "status": "draft", "order": 0, "initial_scene": "", **extra}

    def post_tour(self, **extra):
        return self.client.post(self.url("tour_edit", self.tour.pk), self.tour_payload(**extra), HTTP_ACCEPT="application/json")

    def test_anonymous_routes_redirect_to_custom_login_and_json_denies(self):
        self.client.logout()
        for url in [self.url("home"), self.url("tours"), self.url("categories"), self.url("tour_add"), self.url("tour_edit", self.tour.pk), self.url("scene_add", self.tour.pk), self.url("scene_edit", self.tour.pk, self.a.pk), self.url("editor", self.tour.pk, self.a.pk), self.url("preview", self.tour.pk, self.a.pk), self.url("panorama", self.tour.pk, self.a.pk)]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response.url.startswith(self.url("login")))
        self.assertEqual(self.post_tour().status_code, 403)

    def test_nonstaff_and_staff_without_permissions_cannot_enter(self):
        self.user.is_staff = False
        self.user.save()
        self.assertEqual(self.client.get(self.url("home")).status_code, 403)
        self.user.is_staff = True
        self.user.save()
        self.grant()
        self.assertEqual(self.client.get(self.url("home")).status_code, 403)

    def test_login_uses_django_session_and_logout_requires_post_and_csrf(self):
        password = secrets.token_urlsafe(24)
        self.user.set_password(password)
        self.user.save()
        client = Client(enforce_csrf_checks=True)
        login = self.url("login")
        self.assertContains(client.get(login), "images/logo.png")
        self.assertEqual(client.post(login, {"username": self.user.username, "password": password}).status_code, 403)
        token = client.cookies["csrftoken"].value
        response = client.post(login, {"username": self.user.username, "password": password, "csrfmiddlewaretoken": token, "next": "https://malicious.invalid/"})
        self.assertRedirects(response, self.url("home"))
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)
        self.assertEqual(client.get(self.url("logout")).status_code, 405)
        self.assertEqual(client.post(self.url("logout")).status_code, 403)
        response = client.post(self.url("logout"), {"csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertRedirects(response, self.url("login"))
        self.assertNotIn("_auth_user_id", client.session)

    def test_login_rejects_correct_password_without_panel_access(self):
        password = secrets.token_urlsafe(24)
        self.user.set_password(password)
        self.user.save()
        self.grant()
        self.client.logout()
        response = self.client.post(self.url("login"), {"username": self.user.username, "password": password})
        self.assertContains(response, "Esta cuenta no tiene acceso al panel")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_every_panel_page_renders_with_saved_images_and_no_cache(self):
        self.tour.cover = picture("cover.webp", format="WEBP")
        self.tour.save()
        for name, args in [("home", []), ("tours", []), ("tour_add", []), ("tour_edit", [self.tour.pk]), ("scene_add", [self.tour.pk]), ("scene_edit", [self.tour.pk, self.a.pk]), ("categories", []), ("category_add", []), ("category_edit", [self.tour.category_id])]:
            response = self.client.get(self.url(name, *args))
            self.assertEqual(response.status_code, 200, name)
            self.assertIn("no-store", response.headers["Cache-Control"])

    def test_dashboard_reports_database_counts_and_creation_order(self):
        available = self.make_tour("disponible", True)
        upcoming = self.make_tour("proximo")
        upcoming.status = "upcoming"
        upcoming.save()
        response = self.client.get(self.url("home"))
        stats = {s["label"]: s["value"] for s in response.context["stats"]}
        self.assertEqual(stats, {"Disponibles": 1, "Borradores": 1, "Próximos": 1, "Escenas": 3})
        self.assertEqual(response.context["cards"][0]["object"], upcoming)
        self.assertNotContains(response, "visitas")

    def test_summary_does_not_expose_tours_to_category_only_user(self):
        self.grant("view_category")
        response = self.client.get(self.url("home"))
        self.assertEqual(response.context["stats"], [])
        self.assertNotContains(response, self.tour.name)
        self.assertEqual(self.client.get(self.url("tours")).status_code, 403)

    def test_search_accents_filters_and_empty_state(self):
        self.tour.name = "Basílica de prueba"
        self.tour.save()
        response = self.client.get(self.url("tours"), {"q": "BASILICA", "status": "draft", "category": self.tour.category.slug})
        self.assertEqual(len(response.context["cards"]), 1)
        self.assertContains(self.client.get(self.url("tours"), {"q": "ausente"}), "No encontramos recorridos")
        self.assertEqual(len(self.client.get(self.url("tours"), {"status": "available"}).context["cards"]), 0)

    def test_read_only_pages_have_no_save_and_reject_mutations(self):
        self.grant("view_tour", "view_scene", "view_category", "view_navigationpoint")
        for name, args in [("tour_edit", [self.tour.pk]), ("scene_edit", [self.tour.pk, self.a.pk]), ("category_edit", [self.tour.category_id])]:
            response = self.client.get(self.url(name, *args))
            self.assertContains(response, "acceso de consulta")
            self.assertNotContains(response, "Guardar cambios")
            self.assertEqual(self.client.post(self.url(name, *args), {}).status_code, 403)
        for name, args in [("tour_add", []), ("scene_add", [self.tour.pk]), ("category_add", []), ("tour_delete", [self.tour.pk]), ("scene_delete", [self.tour.pk, self.a.pk]), ("category_delete", [self.tour.category_id])]:
            self.assertEqual(self.client.get(self.url(name, *args)).status_code, 403)
        self.assertEqual(self.client.get(self.url("preview", self.tour.pk, self.a.pk)).status_code, 200)
        self.assertEqual(self.client.get(self.url("editor", self.tour.pk, self.a.pk)).status_code, 403)

    def test_add_and_change_permissions_are_separate(self):
        self.grant("add_tour")
        response = self.client.post(self.url("tour_add"), self.tour_payload(name="Otro lugar", slug=""), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Tour.objects.filter(slug="otro-lugar").exists())
        self.assertEqual(self.post_tour(name="No permitido").status_code, 403)
        self.grant("change_tour")
        self.assertEqual(self.post_tour(name="Permitido").status_code, 200)
        self.assertEqual(self.client.post(self.url("tour_add"), self.tour_payload(slug="sin-permiso")).status_code, 403)

    def test_cover_upload_preserves_original_and_unique_name(self):
        original = picture("portada.png")
        raw = original.read()
        original.seek(0)
        self.assertEqual(self.post_tour(cover=original).status_code, 200)
        self.tour.refresh_from_db()
        first = self.tour.cover.name
        with self.tour.cover.open("rb") as stream:
            self.assertEqual(stream.read(), raw)
        self.assertTrue(self.tour.thumbnail.name)
        self.assertEqual(self.post_tour(cover=picture("portada.png")).status_code, 200)
        self.tour.refresh_from_db()
        self.assertNotEqual(first, self.tour.cover.name)
        self.assertTrue(self.tour.cover.storage.exists(first))

    def test_invalid_upload_returns_field_errors_without_saving_other_values(self):
        response = self.post_tour(name="No guardar", cover=SimpleUploadedFile("fake.png", b"not a PNG"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("cover", response.json()["errors"])
        self.tour.refresh_from_db()
        self.assertNotEqual(self.tour.name, "No guardar")
        response = self.client.post(self.url("tour_edit", self.tour.pk), self.tour_payload(name="Conservar texto", description=""))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Conservar texto", status_code=400)

    @override_settings(COVER_MAX_BYTES=100)
    def test_configured_upload_limits_reach_panel(self):
        self.assertEqual(self.post_tour(cover=picture()).status_code, 400)

    def test_publish_incomplete_is_rejected_then_complete_can_be_published(self):
        response = self.post_tour(status="available")
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.json()["errors"])
        self.assertEqual(self.client.get(reverse("viewer", args=[self.tour.slug])).status_code, 404)
        self.assertEqual(self.post_tour(status="available", initial_scene=self.a.pk).status_code, 200)
        self.assertEqual(self.client.get(reverse("viewer", args=[self.tour.slug])).status_code, 200)
        self.assertEqual(self.post_tour(status="draft", initial_scene=self.a.pk).status_code, 200)
        self.assertEqual(self.client.get(reverse("viewer", args=[self.tour.slug])).status_code, 404)

    def test_foreign_initial_scene_is_rejected(self):
        other = self.make_tour("otro", True)
        self.assertEqual(self.post_tour(initial_scene=other.initial_scene_id).status_code, 400)

    def test_create_edit_order_scene_with_existing_validators(self):
        url = self.url("scene_add", self.tour.pk)
        response = self.client.post(url, {"name": "Nueva", "order": 4, "text": "<b>Texto plano</b>", "panorama": picture()}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        scene = Scene.objects.get(name="Nueva")
        response = self.client.post(self.url("scene_edit", self.tour.pk, scene.pk), {"name": "Nueva", "order": 1, "text": "Editada", "tour": 9999}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        scene.refresh_from_db()
        self.assertEqual(scene.tour_id, self.tour.pk)
        self.assertEqual(scene.order, 1)
        self.assertTrue(scene.panorama)
        for upload in [picture("wrong.png", size=(1024, 700)), picture("wrong.webp", format="WEBP"), SimpleUploadedFile("fake.jpg", b"fake")]:
            response = self.client.post(url, {"name": "Inválida", "order": 0, "panorama": upload}, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("panorama", response.json()["errors"])
        self.assertFalse(Scene.objects.filter(name="Inválida").exists())

    def test_scene_cannot_be_read_or_mutated_through_foreign_tour(self):
        other = self.make_tour("otro")
        for route in ("scene_edit", "scene_delete", "editor", "editor_data", "preview", "panorama", "points", "orientation"):
            url = self.url(route, other.pk, self.a.pk)
            self.assertEqual(self.client.get(url).status_code, 404, route)
            self.assertEqual(self.client.post(url).status_code, 404, route)

    def test_published_scene_cannot_lose_panorama(self):
        self.post_tour(status="available", initial_scene=self.a.pk)
        response = self.client.post(self.url("scene_edit", self.tour.pk, self.a.pk), {"name": "A", "order": 0, "panorama-clear": "on"}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)
        self.a.refresh_from_db()
        self.assertTrue(self.a.panorama)

    def test_delete_requires_post_confirmation_keeps_files_and_related_permissions(self):
        url = self.url("tour_delete", self.tour.pk)
        self.assertContains(self.client.get(url), "Confirmar eliminación")
        self.assertTrue(Tour.objects.filter(pk=self.tour.pk).exists())
        self.grant("view_tour", "delete_tour")
        self.assertEqual(self.client.post(url).status_code, 409)
        self.assertTrue(Tour.objects.filter(pk=self.tour.pk).exists())
        self.grant("view_tour", "delete_tour", "delete_scene", "delete_navigationpoint")
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Tour.objects.filter(pk=self.tour.pk).exists())
        self.assertFalse(Scene.objects.exists())
        self.assertTrue(self.a.panorama.storage.exists(self.a.panorama.name))

    def test_delete_scene_explains_initial_incoming_and_published_restrictions(self):
        url = self.url("scene_delete", self.tour.pk, self.b.pk)
        self.assertContains(self.client.get(url), "puntos que llegan a ella")
        self.assertEqual(self.client.post(url).status_code, 409)
        self.point.delete()
        self.tour.initial_scene = self.b
        self.tour.save()
        self.assertEqual(self.client.post(url).status_code, 409)
        self.tour.initial_scene = None
        self.tour.save()
        self.assertEqual(self.client.post(url).status_code, 302)
        self.post_tour(status="available", initial_scene=self.a.pk)
        self.assertEqual(self.client.post(self.url("scene_delete", self.tour.pk, self.a.pk)).status_code, 409)
        self.assertContains(self.client.get(self.url("tour_delete", self.tour.pk)), "Cambia el recorrido a borrador")

    def test_category_creation_edit_and_in_use_delete(self):
        response = self.client.post(self.url("category_add"), {"name": "Naturaleza", "slug": ""}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        category = Category.objects.get(slug="naturaleza")
        self.client.post(self.url("category_edit", category.pk), {"name": "Naturaleza local", "slug": category.slug})
        category.refresh_from_db()
        self.assertEqual(category.name, "Naturaleza local")
        self.assertEqual(self.client.post(self.url("category_delete", category.pk)).status_code, 302)
        used_url = self.url("category_delete", self.tour.category_id)
        self.assertContains(self.client.get(used_url), "categoría está en uso")
        self.assertEqual(self.client.post(used_url).status_code, 409)

    def test_private_editor_and_preview_return_panel_routes_and_keep_draft_private(self):
        response = self.client.get(self.url("editor", self.tour.pk, self.a.pk))
        self.assertContains(response, "Volver al recorrido")
        data = response.context["editor_data"]
        self.assertEqual(data["urls"]["points"], self.url("points", self.tour.pk, self.a.pk))
        self.assertEqual(data["scene"]["panorama"], self.url("panorama", self.tour.pk, self.a.pk))
        response = self.client.get(self.url("preview", self.tour.pk, self.a.pk))
        self.assertTrue(response.context["private_preview"])
        self.assertTrue(all(s["panorama"].startswith("/panel/") for s in response.context["tour_data"]["scenes"]))
        self.assertEqual(self.client.get(reverse("viewer", args=[self.tour.slug])).status_code, 404)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.status, "draft")
        self.assertIsNone(self.tour.initial_scene_id)

    def test_shared_editor_create_patch_orientation_delete_and_cross_tour_validation(self):
        other = self.make_tour("otro", True)
        payload = {"label": "Conexión", "destination": self.b.pk, "yaw": 15, "pitch": -10, "key": "f" * 32}
        points = self.url("points", self.tour.pk, self.a.pk)
        response = self.client.post(points, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        data = response.json()["point"]
        point_url = self.url("point_detail", self.tour.pk, self.a.pk, data["id"])
        edit = {k: data[k] for k in ("label", "destination", "yaw", "pitch", "revision")}
        self.assertEqual(self.client.patch(point_url, json.dumps({**edit, "destination": other.initial_scene_id}), content_type="application/json").status_code, 400)
        for angle in ["NaN", float("nan"), float("inf")]:
            self.assertEqual(self.client.patch(point_url, json.dumps({**edit, "yaw": angle}), content_type="application/json").status_code, 400)
        response = self.client.patch(point_url, json.dumps({**edit, "yaw": 25, "label": "Movido"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        point = NavigationPoint.objects.get(pk=data["id"])
        self.assertEqual(point.yaw, 25)
        orientation_url = self.url("orientation", self.tour.pk, self.a.pk)
        self.assertEqual(self.client.patch(orientation_url, json.dumps({**orientation_data(self.a), "yaw": 70}), content_type="application/json").status_code, 200)
        self.a.refresh_from_db()
        self.assertEqual(self.a.yaw, 70)
        self.assertEqual(self.client.delete(point_url, json.dumps({"revision": point_data(point)["revision"]}), content_type="application/json").status_code, 200)

    def test_endpoints_enforce_specific_permissions_independently(self):
        self.grant("view_tour", "view_scene", "view_navigationpoint", "add_navigationpoint")
        self.assertEqual(self.client.get(self.url("editor", self.tour.pk, self.a.pk)).status_code, 200)
        for route, method, args in [("orientation", "patch", [self.tour.pk, self.a.pk]), ("point_detail", "patch", [self.tour.pk, self.a.pk, self.point.pk]), ("point_detail", "delete", [self.tour.pk, self.a.pk, self.point.pk])]:
            self.assertEqual(getattr(self.client, method)(self.url(route, *args), "{}", content_type="application/json").status_code, 403)
        self.grant("view_tour", "view_scene", "view_navigationpoint", "change_scene")
        self.assertEqual(self.client.post(self.url("points", self.tour.pk, self.a.pk), "{}", content_type="application/json").status_code, 403)

    def test_csrf_applies_to_every_write_and_get_never_mutates(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        routes = [("tour_add", [], "post"), ("tour_edit", [self.tour.pk], "post"), ("tour_delete", [self.tour.pk], "post"), ("scene_add", [self.tour.pk], "post"), ("scene_edit", [self.tour.pk, self.a.pk], "post"), ("scene_delete", [self.tour.pk, self.a.pk], "post"), ("category_add", [], "post"), ("category_edit", [self.tour.category_id], "post"), ("category_delete", [self.tour.category_id], "post"), ("points", [self.tour.pk, self.a.pk], "post"), ("point_detail", [self.tour.pk, self.a.pk, self.point.pk], "delete"), ("orientation", [self.tour.pk, self.a.pk], "patch")]
        before = [Tour.objects.count(), Scene.objects.count(), NavigationPoint.objects.count(), Category.objects.count()]
        for name, args, method in routes:
            self.assertEqual(getattr(client, method)(self.url(name, *args)).status_code, 403, name)
            self.assertIn(self.client.get(self.url(name, *args)).status_code, (200, 405))
        self.assertEqual(before, [Tour.objects.count(), Scene.objects.count(), NavigationPoint.objects.count(), Category.objects.count()])

    def test_editorial_text_is_escaped_and_empty_states_are_useful(self):
        self.tour.name = '<script>alert("test")</script>'
        self.tour.save()
        self.assertNotContains(self.client.get(self.url("tours")), self.tour.name)
        self.assertContains(self.client.get(self.url("tours")), "&lt;script&gt;")
        self.tour.delete()
        self.assertContains(self.client.get(self.url("home")), "Tu primer recorrido")
        self.assertContains(self.client.get(self.url("tours")), "Todavía no hay recorridos")
