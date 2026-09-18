import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from .models import NavigationPoint, Scene, Tour
from .tests import MediaTestCase, picture
from .editor import point_data, orientation_data


class EditorTests(MediaTestCase):
    def setUp(self):
        self.tour = self.make_tour()
        self.a = Scene.objects.create(tour=self.tour, name="A", panorama=picture())
        self.b = Scene.objects.create(tour=self.tour, name="B", panorama=picture())
        self.point = NavigationPoint.objects.create(origin=self.a, destination=self.b, label="Ir a B")
        self.user = get_user_model().objects.create_user("editor", password=None, is_staff=True)
        self.grant("view_tour", "view_scene", "view_navigationpoint", "add_navigationpoint", "change_navigationpoint", "delete_navigationpoint", "change_scene")

    def grant(self, *permissions):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label="tours", codename__in=permissions))
        self.client.force_login(self.user)

    def url(self, suffix="editor", scene=None, point=None):
        args = [(scene or self.a).pk]
        if point is not None: args.append(point.pk)
        return reverse(f"admin:tours_scene_{suffix}", args=args)

    def create_payload(self):
        return {"label": "Nuevo", "destination": self.b.pk, "yaw": -32.5, "pitch": 12, "key": "a" * 32}

    def update_payload(self):
        return {key: value for key, value in point_data(self.point).items() if key in ("label", "destination", "yaw", "pitch", "revision")}

    def send(self, suffix, payload, method="post", scene=None, point=None, client=None):
        return getattr(client or self.client, method)(self.url(suffix, scene, point), json.dumps(payload), content_type="application/json")

    def test_anonymous_and_nonstaff_are_rejected_on_every_private_route(self):
        endpoints = [("editor", "get", None), ("editor_data", "get", None), ("preview", "get", None), ("panorama", "get", None), ("points", "post", None), ("point_detail", "patch", self.point), ("point_detail", "delete", self.point), ("orientation", "patch", None)]
        for is_staff in (None, False):
            self.client.logout()
            if is_staff is False:
                self.user.is_staff = False; self.user.save(); self.client.force_login(self.user)
            for suffix, method, point in endpoints:
                response = getattr(self.client, method)(self.url(suffix, point=point))
                self.assertEqual(response.status_code, 302, (suffix, method))
        self.assertEqual(NavigationPoint.objects.count(), 1)

    def test_staff_without_permissions_is_rejected_on_every_private_route(self):
        self.grant()
        for suffix in ("editor", "editor_data", "preview", "panorama"):
            self.assertEqual(self.client.get(self.url(suffix)).status_code, 403)
        for suffix, method, point in (("points", "post", None), ("point_detail", "patch", self.point), ("point_detail", "delete", self.point), ("orientation", "patch", None)):
            self.assertEqual(self.send(suffix, {}, method, point=point).status_code, 403)

    def test_read_only_can_preview_but_cannot_enter_editor_or_mutate(self):
        self.grant("view_tour", "view_scene", "view_navigationpoint")
        self.assertEqual(self.client.get(self.url("preview")).status_code, 200)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        self.assertEqual(self.client.get(self.url("editor_data")).status_code, 403)
        for suffix, method, point in (("points", "post", None), ("point_detail", "patch", self.point), ("point_detail", "delete", self.point), ("orientation", "patch", None)):
            self.assertEqual(self.send(suffix, {}, method, point=point).status_code, 403)

    def test_specific_permissions_are_enforced_independently(self):
        self.grant("view_tour", "view_scene", "view_navigationpoint", "add_navigationpoint")
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertEqual(self.send("points", self.create_payload()).status_code, 201)
        for suffix, method, point in (("point_detail", "patch", self.point), ("point_detail", "delete", self.point), ("orientation", "patch", None)):
            self.assertEqual(self.send(suffix, {}, method, point=point).status_code, 403)
        self.grant("view_tour", "view_scene", "view_navigationpoint", "change_scene")
        self.assertEqual(self.send("points", self.create_payload()).status_code, 403)
        self.assertEqual(self.send("orientation", {**orientation_data(self.a), "yaw": 15}, "patch").status_code, 200)

    def test_admin_link_requires_editor_permission_and_saved_scene(self):
        url = reverse("admin:tours_scene_change", args=[self.a.pk])
        self.assertContains(self.client.get(url), "Editar puntos visualmente")
        self.grant("view_tour", "view_scene", "view_navigationpoint")
        self.assertNotContains(self.client.get(url), "Editar puntos visualmente")

    def test_draft_editor_only_offers_destinations_from_same_tour(self):
        other = self.make_tour("otro", True)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        data = response.context["editor_data"]
        self.assertEqual(data["destinations"], [{"id": self.b.pk, "name": "B"}])
        self.assertNotContains(response, other.name)
        self.assertEqual(data["scene"]["panorama"], self.url("panorama"))
        self.assertNotContains(response, self.a.panorama.url)

    def test_create_then_read_preserves_angles(self):
        response = self.send("points", self.create_payload())
        self.assertEqual(response.status_code, 201)
        point = NavigationPoint.objects.get(pk=response.json()["point"]["id"])
        self.assertEqual((point.yaw, point.pitch, point.destination_id), (-32.5, 12, self.b.pk))
        saved = self.client.get(self.url("editor_data")).json()["points"][-1]
        self.assertEqual(saved["yaw"], -32.5)
        self.assertEqual(saved["pitch"], 12)

    def test_create_retry_is_idempotent_without_overwriting_changes(self):
        first = self.send("points", self.create_payload()).json()
        self.assertEqual(self.send("points", self.create_payload()).json(), first)
        self.assertEqual(NavigationPoint.objects.count(), 2)
        changed = {**self.create_payload(), "label": "Otro"}
        self.assertEqual(self.send("points", changed).status_code, 409)
        self.assertEqual(NavigationPoint.objects.get(pk=first["point"]["id"]).label, "Nuevo")

    def test_update_label_destination_and_position(self):
        c = Scene.objects.create(tour=self.tour, name="C")
        payload = {**self.update_payload(), "label": "Ir a C", "destination": c.pk, "yaw": 80, "pitch": -15}
        response = self.send("point_detail", payload, "patch", point=self.point)
        self.assertEqual(response.status_code, 200)
        self.point.refresh_from_db()
        self.assertEqual((self.point.label, self.point.destination_id, self.point.yaw, self.point.pitch), ("Ir a C", c.pk, 80, -15))
        self.assertEqual(self.send("point_detail", payload, "patch", point=self.point).status_code, 200)

    def test_foreign_self_missing_destinations_rejected_on_create_and_update(self):
        other = self.make_tour("otro", True)
        for destination in (other.initial_scene_id, self.a.pk, 999999):
            self.assertEqual(self.send("points", {**self.create_payload(), "destination": destination}).status_code, 400)
            self.assertEqual(self.send("point_detail", {**self.update_payload(), "destination": destination}, "patch", point=self.point).status_code, 400)
        self.assertEqual(NavigationPoint.objects.count(), 1)

    def test_point_must_belong_to_scene_in_url(self):
        self.assertEqual(self.send("point_detail", self.update_payload(), "patch", scene=self.b, point=self.point).status_code, 404)
        self.assertEqual(self.send("point_detail", {"revision": point_data(self.point)["revision"]}, "delete", scene=self.b, point=self.point).status_code, 404)
        self.assertTrue(NavigationPoint.objects.filter(pk=self.point.pk).exists())

    def test_invalid_angles_rejected_for_points_and_orientation(self):
        for yaw, pitch in ((181, 0), (0, 91), (float("inf"), 0), (float("nan"), 0), (True, 0), ("0", 0), (10**400, 0)):
            with self.subTest(yaw=yaw, pitch=pitch):
                self.assertEqual(self.send("points", {**self.create_payload(), "yaw": yaw, "pitch": pitch}).status_code, 400)
                self.assertEqual(self.send("orientation", {**orientation_data(self.a), "yaw": yaw, "pitch": pitch}, "patch").status_code, 400)
        self.assertEqual(NavigationPoint.objects.count(), 1)

    def test_rejects_blank_labels_malformed_json_extra_fields_and_wrong_types(self):
        for payload in ({**self.create_payload(), "label": " "}, {**self.create_payload(), "label": 12}, {**self.create_payload(), "origin": self.b.pk}, {**self.create_payload(), "destination": True}, {"yaw": 0}, [], None):
            self.assertEqual(self.send("points", payload).status_code, 400)
        self.assertEqual(self.client.post(self.url("points"), "{bad", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(self.url("points"), self.create_payload()).status_code, 400)

    def test_delete_and_stale_version_protection(self):
        old_revision = point_data(self.point)["revision"]
        self.point.label = "Cambio externo"; self.point.save()
        self.assertEqual(self.send("point_detail", {"revision": old_revision}, "delete", point=self.point).status_code, 409)
        self.assertEqual(self.send("point_detail", {**self.update_payload(), "revision": old_revision, "label": "Perder cambio"}, "patch", point=self.point).status_code, 409)
        self.assertEqual(self.send("point_detail", {"revision": point_data(self.point)["revision"]}, "delete", point=self.point).status_code, 200)
        self.assertFalse(NavigationPoint.objects.exists())

    def test_orientation_is_persisted_without_changing_other_scene_fields(self):
        original = (self.a.name, self.a.panorama.name, self.a.tour_id)
        payload = {**orientation_data(self.a), "yaw": -125.5, "pitch": 33.2}
        self.assertEqual(self.send("orientation", payload, "patch").status_code, 200)
        self.a.refresh_from_db()
        self.assertEqual((self.a.yaw, self.a.pitch), (-125.5, 33.2))
        self.assertEqual((self.a.name, self.a.panorama.name, self.a.tour_id), original)
        self.assertEqual(self.send("orientation", payload, "patch").status_code, 200)
        self.assertEqual(self.send("orientation", {**payload, "yaw": 0}, "patch").status_code, 409)

    def test_orientation_reuses_phase2_image_validation(self):
        with open(self.a.panorama.path, "wb") as file: file.write(b"broken")
        response = self.send("orientation", {**orientation_data(self.a), "yaw": 30}, "patch")
        self.assertEqual(response.status_code, 400)
        self.a.refresh_from_db(); self.assertEqual(self.a.yaw, 0)

    def test_get_cannot_modify_data(self):
        for suffix, point in (("points", None), ("point_detail", self.point), ("orientation", None)):
            self.assertEqual(self.client.get(self.url(suffix, point=point), self.create_payload()).status_code, 405)
        self.assertEqual(NavigationPoint.objects.count(), 1)
        self.a.refresh_from_db(); self.assertEqual(self.a.yaw, 0)

    def test_all_write_methods_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for suffix, method, point in (("points", "post", None), ("point_detail", "patch", self.point), ("point_detail", "delete", self.point), ("orientation", "patch", None)):
            self.assertEqual(self.send(suffix, {}, method, point=point, client=client).status_code, 403)
        client.get(self.url())
        token = client.cookies["csrftoken"].value
        response = client.post(self.url("points"), json.dumps(self.create_payload()), content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201)

    def test_private_preview_uses_saved_values_without_publishing_or_needing_initial_scene(self):
        response = self.client.get(self.url("preview"))
        self.assertContains(response, "PRUEBA PRIVADA")
        data = response.context["tour_data"]
        self.assertEqual(data["initial_scene"], self.a.key)
        self.assertEqual(data["scenes"][0]["hotspots"][0]["position"], self.point.position())
        self.assertEqual(data["scenes"][0]["panorama"], self.url("panorama"))
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.status, Tour.Status.DRAFT)
        self.assertIsNone(self.tour.initial_scene)
        self.assertEqual(self.client.get(f"/recorridos/{self.tour.slug}/").status_code, 404)
        self.assertEqual(self.client.get("/explorar/").context["result_count"], 0)

    def test_editor_and_preview_are_not_cached_and_panorama_is_protected(self):
        for suffix in ("editor", "editor_data", "preview", "panorama"):
            response = self.client.get(self.url(suffix))
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            response.close()
        self.a.panorama = ""; self.a.save()
        self.assertEqual(self.client.get(self.url("panorama")).status_code, 404)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertEqual(self.client.get(self.url("preview")).status_code, 200)

    def test_editorial_text_is_escaped_in_editor_and_private_preview(self):
        self.point.label = '</script><script>alert("unsafe")</script>'; self.point.save()
        self.a.name = '<img src=x onerror=alert(1)>'; self.a.save()
        for suffix in ("editor", "preview"):
            response = self.client.get(self.url(suffix))
            self.assertNotContains(response, self.point.label)
            self.assertNotContains(response, self.a.name)

    def test_saved_marker_coordinates_match_public_viewer(self):
        self.tour.initial_scene = self.a; self.tour.status = Tour.Status.DEMO; self.tour.save()
        self.send("point_detail", {**self.update_payload(), "yaw": -30, "pitch": 25}, "patch", point=self.point)
        self.point.refresh_from_db()
        response = self.client.get(f"/recorridos/{self.tour.slug}/")
        point = response.context["tour_data"]["scenes"][0]["hotspots"][0]
        self.assertEqual(point["position"], self.point.position())
        self.assertEqual(point["destination"], self.b.key)
