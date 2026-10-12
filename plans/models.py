from django.db import models
from django.utils.translation import gettext_lazy as _

WEEKDAYS = [
    (0, _("Monday")),
    (1, _("Tuesday")),
    (2, _("Wednesday")),
    (3, _("Thursday")),
    (4, _("Friday")),
]


class Plan(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", _("Waiting to be written")
        WRITING = "writing", _("Being written")
        DONE = "done", _("Ready")
        FAILED = "failed", _("Failed")

    week = models.OneToOneField("worksheets.Week", on_delete=models.CASCADE, related_name="plan")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    # Language the plan is written in (the parent's language when they asked for it).
    language = models.CharField(max_length=5, default="de")
    # Snapshot of the child's cap when the plan was made.
    daily_minutes = models.PositiveSmallIntegerField(default=20)
    error = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("study plan")
        verbose_name_plural = _("study plans")

    def __str__(self):
        return str(self.week)

    @property
    def is_pending(self):
        return self.status in (self.Status.QUEUED, self.Status.WRITING)


class PlanDay(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="days")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    subject = models.CharField(max_length=20, blank=True)
    topic = models.CharField(max_length=200, blank=True)
    # The outline the exercises are written from (topics, minutes per block).
    outline = models.JSONField(default=dict)
    written = models.BooleanField(default=False)

    class Meta:
        ordering = ["weekday"]
        constraints = [models.UniqueConstraint(fields=["plan", "weekday"], name="unique_plan_weekday")]

    def __str__(self):
        return f"{self.plan} · {self.get_weekday_display()}"

    @property
    def is_friday(self):
        return self.weekday == 4

    @property
    def total_minutes(self):
        return sum(e.minutes for e in self.exercises.all())


class Exercise(models.Model):
    """One block of a day's session (see docs/learning-principles.md, session template)."""

    class Kind(models.TextChoices):
        RECALL = "recall", _("Do you remember?")
        PUZZLE = "puzzle", _("Puzzle of the day")
        MAIN = "main", _("Main task")
        EXPLAIN = "explain", _("Explain it to me")
        REFLECT = "reflect", _("How did it go?")
        QUIZ = "quiz", _("Friday quiz")
        RESEARCH = "research", _("Research question")
        REVIEW = "review", _("Looking back on the week")

    day = models.ForeignKey(PlanDay, on_delete=models.CASCADE, related_name="exercises")
    order = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=10, choices=Kind.choices)
    minutes = models.PositiveSmallIntegerField()
    subject = models.CharField(max_length=20, blank=True)
    topic = models.CharField(max_length=200, blank=True)
    # {"text": str, "items": [str], "choices": [{"label", "title", "text"}]}
    content = models.JSONField(default=dict)
    # Worksheets the exercise was derived from (private to the family).
    source_pages = models.ManyToManyField("worksheets.Page", blank=True, related_name="exercises")

    class Meta:
        ordering = ["day", "order"]
        verbose_name = _("exercise")
        verbose_name_plural = _("exercises")

    def __str__(self):
        return f"{self.day} · {self.get_kind_display()}"

    @property
    def is_generated(self):
        return self.kind in (self.Kind.RECALL, self.Kind.PUZZLE, self.Kind.MAIN, self.Kind.EXPLAIN, self.Kind.QUIZ)
