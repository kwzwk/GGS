"""Minimal Ollama HTTP client (https://github.com/ollama/ollama/blob/main/docs/api.md)."""

import json

import httpx
from django.utils import timezone

from jobs.queue import ServiceUnavailable

from .models import OllamaSettings

CHECK_TIMEOUT = 3


class OllamaUnavailable(ServiceUnavailable):
    pass


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, base_url, timeout=600, transport=None):
        if not base_url:
            raise OllamaUnavailable("No Ollama URL configured")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _client(self, timeout):
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=CHECK_TIMEOUT),
            transport=self.transport,
        )

    def _request(self, method, path, timeout, **kwargs):
        try:
            with self._client(timeout) as client:
                response = client.request(method, path, **kwargs)
        except httpx.ReadTimeout as exc:
            raise OllamaError(f"Ollama did not answer within {timeout}s") from exc
        except httpx.TransportError as exc:
            # Connection refused, host down, connection dropped: the PC is off.
            raise OllamaUnavailable(f"Ollama not reachable at {self.base_url}: {exc}") from exc
        if response.status_code >= 400:
            raise OllamaError(f"Ollama returned {response.status_code}: {response.text[:500]}")
        return response.json()

    def list_models(self):
        data = self._request("GET", "/api/tags", CHECK_TIMEOUT)
        return sorted(m["name"] for m in data.get("models", []))

    def chat(self, model, messages, schema=None, temperature=0.2):
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if schema is not None:
            body["format"] = schema
        data = self._request("POST", "/api/chat", self.timeout, json=body)
        content = data.get("message", {}).get("content", "")
        if schema is None:
            return content
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Model returned invalid JSON: {content[:300]}") from exc


def get_client(settings=None):
    settings = settings or OllamaSettings.load()
    return OllamaClient(settings.base_url, timeout=settings.request_timeout)


def check(settings=None):
    """Check reachability, remember the result, return (ok, models, error)."""
    settings = settings or OllamaSettings.load()
    try:
        models = get_client(settings).list_models()
        ok, error = True, ""
    except (OllamaUnavailable, OllamaError) as exc:
        models, ok, error = [], False, str(exc)
    OllamaSettings.objects.filter(pk=settings.pk).update(
        last_check_at=timezone.now(), last_check_ok=ok
    )
    return ok, models, error


def record_status(ok):
    """Remember whether the last real request reached Ollama (shown to parents and the admin)."""
    OllamaSettings.objects.filter(pk=1).update(last_check_at=timezone.now(), last_check_ok=ok)


def is_known_unreachable():
    settings = OllamaSettings.load()
    return not settings.base_url or (settings.last_check_at is not None and not settings.last_check_ok)
