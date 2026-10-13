import logging

from django.db import transaction
from django.utils import timezone

from jobs.queue import enqueue, handler
from llm import client as llm
from llm.models import OllamaSettings
from worksheets.models import Page

from . import planner, writer
from .models import Exercise, Plan, PlanDay

logger = logging.getLogger(__name__)

GENERATE = "plans.generate"

# Plans are written in German; these languages get a translated version.
PRIMARY_LANGUAGE = "de"
TRANSLATIONS = ("en",)


def request_plan(week):
    """Create (or recreate) the week's plan and queue it for writing."""
    with transaction.atomic():
        Plan.objects.filter(week=week).delete()
        plan = Plan.objects.create(week=week, language=PRIMARY_LANGUAGE, daily_minutes=week.child.daily_minutes)
        for day in planner.build_outline(week, plan.daily_minutes):
            main = day["main"] or {}
            PlanDay.objects.create(
                plan=plan,
                weekday=day["weekday"],
                subject=main.get("subject", ""),
                topic=main.get("topic", ""),
                outline=day,
            )
        enqueue(GENERATE, plan_id=plan.pk)
    return plan


def _write_day(plan, day, settings):
    outline = day.outline
    prompt, schema = writer.build_prompt(outline, plan.week.child.class_level)
    data = llm.get_client(settings).chat(
        settings.plan_model, [{"role": "user", "content": prompt}], schema=schema, temperature=0.6
    )
    title, blocks = writer.parse(outline, data)
    main = outline.get("main") or {}
    main_pages = Page.objects.filter(pk__in=main.get("page_ids", []))
    recall_pages = Page.objects.filter(pk__in=[pid for t in outline.get("recall", []) for pid in t.get("page_ids", [])])
    with transaction.atomic():
        day.exercises.all().delete()
        for order, (kind, minutes, content) in enumerate(blocks):
            exercise = Exercise.objects.create(
                day=day,
                order=order,
                kind=kind,
                minutes=minutes,
                subject=main.get("subject", "") if kind == "main" else "",
                topic=main.get("topic", "") if kind == "main" else "",
                content=content,
            )
            if kind == "main":
                exercise.source_pages.set(main_pages)
            elif kind in ("recall", "quiz"):
                exercise.source_pages.set(recall_pages)
        day.title = title
        day.title_translations = {}
        day.written = True
        day.translated = False
        day.save(update_fields=["title", "title_translations", "written", "translated"])


def _translate_day(plan, day, settings):
    exercises = list(day.exercises.all())
    texts = [day.title] if day.title else []
    for exercise in exercises:
        texts += writer.flatten(exercise.content)
    for language in TRANSLATIONS:
        if texts:
            prompt, schema = writer.build_translation_prompt(texts, plan.week.child.class_level)
            data = llm.get_client(settings).chat(
                settings.plan_model, [{"role": "user", "content": prompt}], schema=schema, temperature=0.2
            )
            remaining = writer.parse_translation(texts, data)
        else:
            remaining = []
        with transaction.atomic():
            if day.title:
                day.title_translations[language] = remaining.pop(0)
            for exercise in exercises:
                exercise.translations[language] = writer.unflatten(exercise.content, remaining)
                exercise.save(update_fields=["translations"])
            day.save(update_fields=["title_translations"])
    day.translated = True
    day.save(update_fields=["translated"])


@handler(GENERATE)
def generate(plan_id):
    plan = Plan.objects.select_related("week__child").filter(pk=plan_id).first()
    if plan is None:
        return  # replaced or deleted in the meantime
    settings = OllamaSettings.load()
    Plan.objects.filter(pk=plan.pk).update(status=Plan.Status.WRITING)
    try:
        # Days already written survive a restart or the AI PC going off midway.
        for day in plan.days.filter(written=False):
            _write_day(plan, day, settings)
            llm.record_status(True)
        for day in plan.days.filter(translated=False):
            _translate_day(plan, day, settings)
    except llm.OllamaUnavailable:
        llm.record_status(False)
        Plan.objects.filter(pk=plan.pk).update(status=Plan.Status.QUEUED)
        raise
    except Exception:
        Plan.objects.filter(pk=plan.pk).update(status=Plan.Status.QUEUED)
        raise
    Plan.objects.filter(pk=plan.pk).update(status=Plan.Status.DONE, error="", finished_at=timezone.now())


def _generation_failed(plan_id, error):
    Plan.objects.filter(pk=plan_id).update(status=Plan.Status.FAILED, error=str(error)[:2000])


generate.on_failure = _generation_failed
