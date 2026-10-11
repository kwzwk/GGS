from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Job(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", _("queued")
        RUNNING = "running", _("running")
        DONE = "done", _("done")
        FAILED = "failed", _("failed")

    kind = models.CharField(_("kind"), max_length=64)
    payload = models.JSONField(_("payload"), default=dict)
    status = models.CharField(
        _("status"), max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    attempts = models.PositiveIntegerField(_("attempts"), default=0)
    run_after = models.DateTimeField(_("run after"), default=timezone.now, db_index=True)
    last_error = models.TextField(_("last error"), blank=True)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    started_at = models.DateTimeField(_("started"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished"), null=True, blank=True)

    class Meta:
        ordering = ["run_after", "id"]
        verbose_name = _("job")
        verbose_name_plural = _("jobs")

    def __str__(self):
        return f"{self.kind} #{self.pk} ({self.status})"
