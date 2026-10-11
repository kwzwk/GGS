from django.db import models
from django.utils.translation import gettext_lazy as _

from ggs.env import env_str


class OllamaSettings(models.Model):
    """The single row holding the admin's Ollama configuration."""

    base_url = models.URLField(
        _("Ollama URL"),
        blank=True,
        help_text=_("Address of the Ollama server on your network, e.g. http://192.168.1.50:11434"),
    )
    vision_model = models.CharField(
        _("model for reading worksheets"),
        max_length=100,
        default="qwen2.5vl:7b",
        help_text=_("A vision model installed in Ollama, e.g. qwen2.5vl:7b or gemma3:12b."),
    )
    text_model = models.CharField(
        _("model for writing plans"),
        max_length=100,
        blank=True,
        help_text=_("Leave empty to use the same model as for reading worksheets."),
    )
    request_timeout = models.PositiveIntegerField(
        _("timeout (seconds)"),
        default=600,
        help_text=_("How long one AI request may take. Loading a model can take a while."),
    )
    # Written by the worker so pages can show whether the server is up without
    # waiting for a network timeout.
    last_check_at = models.DateTimeField(_("last checked"), null=True, blank=True)
    last_check_ok = models.BooleanField(_("reachable at last check"), default=False)

    class Meta:
        verbose_name = _("AI server settings")
        verbose_name_plural = _("AI server settings")

    def __str__(self):
        return str(_("AI server settings"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @property
    def plan_model(self):
        return self.text_model or self.vision_model

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(
            pk=1,
            defaults={
                "base_url": env_str("GGS_OLLAMA_URL"),
                "vision_model": env_str("GGS_OLLAMA_VISION_MODEL") or "qwen2.5vl:7b",
                "text_model": env_str("GGS_OLLAMA_TEXT_MODEL"),
            },
        )
        return obj
