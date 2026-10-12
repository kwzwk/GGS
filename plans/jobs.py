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


def request_plan(week, language):
    """Create (or recreate) the week's plan and queue it for writing."""
    with transaction.atomic():
        Plan.objects.filter(week=week).delete()
        plan = Plan.objects.create(week=week, language=language[:5], daily_minutes=week.child.daily_minutes)
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
    prompt, schema = writer.build_prompt(outline, plan.week.child.class_level, plan.language)
    data = llm.get_client(settings).chat(
        settings.plan_model, [{"role": "user", "content": prompt}], schema=schema, temperature=0.6
    )
    blocks = writer.parse(outline, data)
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
        day.written = True
        day.save(update_fields=["written"])


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
