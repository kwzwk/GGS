from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from jobs.models import Job

from . import client
from .models import OllamaSettings


@admin.register(OllamaSettings)
class OllamaSettingsAdmin(admin.ModelAdmin):
    fields = ("base_url", "vision_model", "text_model", "request_timeout")
    change_form_template = "admin/llm/ollamasettings/change_form.html"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = OllamaSettings.load()
        return redirect(reverse("admin:llm_ollamasettings_change", args=[obj.pk]))

    def change_view(self, request, object_id, form_url="", extra_context=None):
        settings = OllamaSettings.load()
        ok, models, error = client.check(settings)
        extra_context = {
            **(extra_context or {}),
            "ollama_ok": ok,
            "ollama_models": models,
            "ollama_error": error,
            "configured_models": [m for m in {settings.vision_model, settings.plan_model} if m],
            "jobs_waiting": Job.objects.filter(status=Job.Status.QUEUED).count(),
            "jobs_running": Job.objects.filter(status=Job.Status.RUNNING).count(),
            "jobs_failed": Job.objects.filter(status=Job.Status.FAILED).count(),
        }
        return super().change_view(request, object_id, form_url, extra_context)
