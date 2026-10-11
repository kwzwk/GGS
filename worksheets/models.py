import datetime
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


SUBJECT_LABELS = {
    "math": _("Maths"),
    "german": _("German"),
    "science": _("General studies"),
    "english": _("English"),
    "other": _("Other"),
}

DIFFICULTY_LABELS = {"easy": _("easy"), "medium": _("medium"), "hard": _("hard")}


def monday_of(day):
    return day - datetime.timedelta(days=day.weekday())


def _upload_path(instance, filename):
    week = instance.week
    return f"children/{week.child_id}/{week.week_start:%Y-%m-%d}/originals/{uuid.uuid4().hex}_{filename[-80:]}"


def _page_path(instance, filename):
    week = instance.upload.week
    return f"children/{week.child_id}/{week.week_start:%Y-%m-%d}/pages/{uuid.uuid4().hex}.jpg"


class Week(models.Model):
    child = models.ForeignKey("children.Child", on_delete=models.CASCADE, related_name="weeks")
    week_start = models.DateField(_("week starting"))

    class Meta:
        ordering = ["-week_start"]
        constraints = [
            models.UniqueConstraint(fields=["child", "week_start"], name="unique_week_per_child")
        ]
        verbose_name = _("week")
        verbose_name_plural = _("weeks")

    def __str__(self):
        return f"{self.child} · {self.week_start:%Y-%m-%d}"

    @property
    def week_end(self):
        return self.week_start + datetime.timedelta(days=4)

    def pages(self):
        return Page.objects.filter(upload__week=self).order_by("upload__uploaded_at", "upload_id", "page_number")


class Upload(models.Model):
    """One file as the parent sent it (photo, HEIC or PDF). Kept until the admin deletes it."""

    week = models.ForeignKey(Week, on_delete=models.CASCADE, related_name="uploads")
    file = models.FileField(upload_to=_upload_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = _("upload")
        verbose_name_plural = _("uploads")

    def __str__(self):
        return self.original_name


class Page(models.Model):
    """One image to analyse: a photo, or one page of a PDF."""

    class Status(models.TextChoices):
        QUEUED = "queued", _("Waiting for analysis")
        ANALYSING = "analysing", _("Being analysed")
        DONE = "done", _("Analysed")
        FAILED = "failed", _("Analysis failed")

    upload = models.ForeignKey(Upload, on_delete=models.CASCADE, related_name="pages")
    page_number = models.PositiveSmallIntegerField(default=1)
    image = models.ImageField(upload_to=_page_path)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    # Language the analysis summary should be written in (the parent's language).
    language = models.CharField(max_length=5, default="de")
    analysis = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    analysed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["upload_id", "page_number"]
        verbose_name = _("page")
        verbose_name_plural = _("pages")

    def __str__(self):
        return f"{self.upload} p.{self.page_number}"

    @property
    def subject_label(self):
        subject = (self.analysis or {}).get("subject")
        return SUBJECT_LABELS.get(subject, SUBJECT_LABELS["other"])

    @property
    def difficulty_label(self):
        return DIFFICULTY_LABELS.get((self.analysis or {}).get("difficulty"), "")

    @property
    def is_pending(self):
        return self.status in (self.Status.QUEUED, self.Status.ANALYSING)
