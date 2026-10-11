import json
import os
from unittest import mock

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase

from . import client
from .models import OllamaSettings


def transport(handler):
    return httpx.MockTransport(handler)


class ClientTests(TestCase):
    def test_list_models(self):
        def handle(request):
            self.assertEqual(request.url.path, "/api/tags")
            return httpx.Response(200, json={"models": [{"name": "qwen2.5vl:7b"}, {"name": "gemma3:12b"}]})

        c = client.OllamaClient("http://ollama:11434/", transport=transport(handle))
        self.assertEqual(c.list_models(), ["gemma3:12b", "qwen2.5vl:7b"])

    def test_chat_with_schema(self):
        def handle(request):
            body = json.loads(request.content)
            self.assertEqual(body["model"], "m")
            self.assertFalse(body["stream"])
            self.assertEqual(body["format"], {"type": "object"})
            return httpx.Response(200, json={"message": {"content": '{"a": 1}'}})

        c = client.OllamaClient("http://ollama:11434", transport=transport(handle))
        self.assertEqual(c.chat("m", [], schema={"type": "object"}), {"a": 1})

    def test_connection_error_means_unavailable(self):
        def handle(request):
            raise httpx.ConnectError("refused")

        c = client.OllamaClient("http://ollama:11434", transport=transport(handle))
        with self.assertRaises(client.OllamaUnavailable):
            c.list_models()

    def test_http_error_is_not_unavailable(self):
        c = client.OllamaClient(
            "http://ollama:11434", transport=transport(lambda r: httpx.Response(404, text="model not found"))
        )
        with self.assertRaises(client.OllamaError):
            c.chat("m", [])

    def test_no_url_means_unavailable(self):
        with self.assertRaises(client.OllamaUnavailable):
            client.OllamaClient("")


class SettingsTests(TestCase):
    @mock.patch.dict(os.environ, {"GGS_OLLAMA_URL": "http://gpu:11434"})
    def test_seeded_from_env(self):
        obj = OllamaSettings.load()
        self.assertEqual(obj.base_url, "http://gpu:11434")
        self.assertEqual(obj.plan_model, "qwen2.5vl:7b")
        self.assertFalse(client.is_known_unreachable())
        client.record_status(False)
        self.assertTrue(client.is_known_unreachable())

    def test_admin_page_shows_status(self):
        admin = get_user_model().objects.create_superuser("kai", password="x")
        self.client.force_login(admin)
        OllamaSettings.load()
        response = self.client.get("/admin/llm/ollamasettings/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ollama")
        self.assertContains(response, "Wartende Aufgaben")
