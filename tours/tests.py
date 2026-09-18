import copy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .checks import check_tours
from .content import ContentError, filter_tours, load_tours, validate_content, viewer_data

class CatalogTests(SimpleTestCase):
    def setUp(self):
        self.tours = load_tours()

    def test_routes_and_explicit_demo(self):
        for path in ("/", "/explorar/", "/recorridos/demostracion/"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertContains(self.client.get("/recorridos/demostracion/"), "Demostración técnica — no representa un lugar real")

    @override_settings(DEBUG=False)
    def test_missing_and_upcoming_tours_are_real_404s(self):
        for slug in ("inexistente", "mirador", "basilica", "parque-central"):
            response = self.client.get(f"/recorridos/{slug}/")
            self.assertEqual(response.status_code, 404)
            self.assertContains(response, "todavía no está aquí", status_code=404)

    def test_search_ignores_case_and_accents(self):
        for query in ("Basílica", "basilica", "BASÍLICA", "  BASILICA  "):
            self.assertEqual([t["id"] for t in filter_tours(self.tours, query)], ["basilica"])
        response = self.client.get("/explorar/", {"q": "BASILICA"})
        self.assertContains(response, "Basílica")
        self.assertNotContains(response, '<h3>Mirador</h3>')

    def test_search_combines_with_category(self):
        matching = self.client.get("/explorar/", {"q": "basilica", "categoria": "patrimonio"})
        self.assertEqual(matching.context["result_count"], 1)
        empty = self.client.get("/explorar/", {"q": "basilica", "categoria": "vistas"})
        self.assertEqual(empty.context["result_count"], 0)
        self.assertContains(empty, "Restablecer búsqueda")

    def test_invalid_category_falls_back_to_all(self):
        self.assertEqual(self.client.get("/explorar/", {"categoria": "inventado"}).context["result_count"], 4)

    def test_upcoming_has_no_fake_link(self):
        response = self.client.get("/explorar/")
        for slug in ("mirador", "basilica", "parque-central"):
            self.assertNotContains(response, f'href="/recorridos/{slug}/"')
        self.assertContains(response, 'href="/recorridos/demostracion/"')

    def test_query_is_escaped(self):
        self.assertNotContains(self.client.get("/explorar/", {"q": '<script>alert(1)</script>'}), '<script>alert(1)</script>')

    def test_viewer_data_has_resolved_urls_and_no_missing_audio_controls(self):
        data = viewer_data(self.tours[0])
        self.assertEqual(data["scenes"][0]["panorama"], "/static/panoramas/demo-azul.png")
        self.assertIsNone(data["scenes"][0]["audio"])
        self.assertNotContains(self.client.get("/recorridos/demostracion/"), '<audio')

    def test_media_urls_are_supported(self):
        tour = copy.deepcopy(self.tours[0])
        tour["scenes"][0]["panorama"] = "media/panoramas/mirador.jpg"
        self.assertEqual(viewer_data(tour)["scenes"][0]["panorama"], "/media/panoramas/mirador.jpg")

    def test_missing_panorama_is_left_to_recoverable_viewer_error(self):
        tours = copy.deepcopy(self.tours)
        tours[0]["scenes"][0]["panorama"] = "panoramas/ausente.png"
        with patch("tours.views.load_tours", return_value=tours):
            response = self.client.get("/recorridos/demostracion/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "panoramas/ausente.png")
        self.assertContains(response, 'id="retry"')

class ValidationTests(SimpleTestCase):
    def setUp(self):
        self.tours = load_tours()

    def test_valid_catalog(self):
        self.assertEqual(len(validate_content(self.tours)), 4)
        self.assertEqual(check_tours(None), [])

    def test_duplicate_and_malformed_ids_and_slugs(self):
        for key, bad in (("id", "demo"), ("slug", "demostracion"), ("slug", "../mal")):
            data = copy.deepcopy(self.tours)
            data[1][key] = bad
            with self.assertRaises(ContentError): validate_content(data)

    def test_missing_initial_scene(self):
        self.tours[0]["initial_scene"] = "missing"
        with self.assertRaisesMessage(ContentError, "Escena inicial"): validate_content(self.tours)

    def test_duplicate_scene_and_hotspot_ids(self):
        for kind in ("scenes", "hotspots"):
            data = copy.deepcopy(self.tours)
            items = data[0]["scenes"] if kind == "scenes" else data[0]["scenes"][0]["hotspots"]
            items.append(copy.deepcopy(items[0]))
            with self.assertRaises(ContentError): validate_content(data)

    def test_invalid_destinations(self):
        self.tours[0]["scenes"][0]["hotspots"][0]["destination"] = "unknown"
        with self.assertRaisesMessage(ContentError, "Destino inexistente"): validate_content(self.tours)

    def test_invalid_positions_and_orientation(self):
        for position in ([0, 0], [0, 0, 0], [0, float("nan"), 3], [0, "2", 3]):
            data = copy.deepcopy(self.tours)
            data[0]["scenes"][0]["hotspots"][0]["position"] = position
            with self.assertRaises(ContentError): validate_content(data)
        self.tours[0]["scenes"][0]["orientation"]["pitch"] = 91
        with self.assertRaises(ContentError): validate_content(self.tours)

    def test_invalid_panorama_path(self):
        for path in ("../secret", "/etc/passwd", "https://other.example/a.png", "media/../../env"):
            data = copy.deepcopy(self.tours)
            data[0]["scenes"][0]["panorama"] = path
            with self.assertRaises(ContentError): validate_content(data)

    def test_upcoming_cannot_expose_scenes(self):
        self.tours[0]["status"] = "upcoming"
        with self.assertRaises(ContentError): validate_content(self.tours)

    def test_invalid_catalog_is_reported_by_django_check(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"broken": true}')
            with patch("tours.content.CONTENT_FILE", path):
                self.assertEqual(check_tours(None)[0].id, "tours.E001")
