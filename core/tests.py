from django.test import TestCase

from ggs.env import normalize_base_path
from ggs.wsgi import strip_base_path


class HealthzTests(TestCase):
    def test_healthz_reports_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class LanguageTests(TestCase):
    def test_german_is_the_default(self):
        response = self.client.get("/")
        self.assertContains(response, "Willkommen")
        self.assertContains(response, '<html lang="de">')

    def test_english_from_browser_language(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(response, "Welcome")

    def test_language_switch_is_remembered(self):
        self.client.post("/i18n/setlang/", {"language": "en", "next": "/"})
        response = self.client.get("/")
        self.assertContains(response, "Welcome")


class BasePathTests(TestCase):
    def test_normalize_base_path(self):
        self.assertEqual(normalize_base_path(""), "")
        self.assertEqual(normalize_base_path("/"), "")
        self.assertEqual(normalize_base_path("lernplan"), "/lernplan")
        self.assertEqual(normalize_base_path("/lernplan/"), "/lernplan")

    def _path_seen_by_app(self, base_path, path):
        seen = {}

        def app(environ, start_response):
            seen["path"] = environ["PATH_INFO"]

        strip_base_path(app, base_path)({"PATH_INFO": path}, None)
        return seen["path"]

    def test_prefix_is_stripped_when_proxy_forwards_it(self):
        self.assertEqual(self._path_seen_by_app("/lernplan", "/lernplan/healthz"), "/healthz")
        self.assertEqual(self._path_seen_by_app("/lernplan", "/lernplan"), "/")

    def test_paths_without_prefix_are_untouched(self):
        self.assertEqual(self._path_seen_by_app("/lernplan", "/healthz"), "/healthz")
        self.assertEqual(self._path_seen_by_app("/lernplan", "/lernplanx"), "/lernplanx")
