from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from children.models import Child
from llm.client import is_known_unreachable
from worksheets.views import _parse_week
from worksheets.models import Week

from . import planner
from .jobs import PRIMARY_LANGUAGE, TRANSLATIONS, request_plan
from .models import Exercise, Plan


def _own_week(request, child_pk, week):
    child = get_object_or_404(Child, pk=child_pk, parent=request.user)
    return get_object_or_404(Week.objects.select_related("child"), child=child, week_start=_parse_week(week))


LANGUAGES = (PRIMARY_LANGUAGE,) + TRANSLATIONS


def _language(request):
    """The plan language to show: ?lang=, else the page language, else German."""
    for language in (request.GET.get("lang"), (translation.get_language() or "")[:2]):
        if language in LANGUAGES:
            return language
    return PRIMARY_LANGUAGE


def _plan_with_days(week, language):
    plan = get_object_or_404(Plan, week=week)
    days = list(
        plan.days.prefetch_related(
            Prefetch("exercises", queryset=Exercise.objects.prefetch_related("source_pages__upload"))
        )
    )
    # Plans written before translations existed are shown in their own language.
    if language != plan.language and not any(d.title_translations for d in days):
        language = plan.language
    for day in days:
        day.shown_title = day.title_in(language) if language != plan.language else (day.title or day.topic)
        for exercise in day.exercises.all():
            exercise.shown = exercise.content_in(language) if language != plan.language else exercise.content
    return plan, days, language


def _switch(plan, days, language):
    """The language links to show, or none for plans with one language."""
    if not any(d.title_translations for d in days):
        return []
    return [{"code": code, "name": name, "current": code == language} for code, name in (("de", "Deutsch"), ("en", "English"))]


@login_required
@require_POST
def create(request, child_pk, week):
    week = _own_week(request, child_pk, week)
    if any(p.is_pending for p in week.pages()):
        messages.error(request, _("Please wait until all worksheets are analysed."))
    elif not planner.topics_of_week(week) and not planner.due_topics(week):
        messages.error(request, _("No worksheet topics found for this week, so there is nothing to plan yet."))
    else:
        request_plan(week)
        messages.success(request, _("The study plan is being written. This can take a few minutes."))
    return redirect("plans:detail", child_pk=child_pk, week=week.week_start.isoformat())


@login_required
def detail(request, child_pk, week):
    week = _own_week(request, child_pk, week)
    plan = Plan.objects.filter(week=week).first()
    if plan is None:
        return redirect("worksheets:week", child_pk=child_pk, week=week.week_start.isoformat())
    plan, days, language = _plan_with_days(week, _language(request))
    with translation.override(language):
        return render(
            request,
            "plans/detail.html",
            {
                "child": week.child,
                "week": week,
                "plan": plan,
                "days": days,
                "language": language,
                "switch": _switch(plan, days, language),
                "klasse1": week.child.class_level == 1,
                "server_offline": plan.is_pending and is_known_unreachable(),
            },
        )


@login_required
def print_view(request, child_pk, week):
    week = _own_week(request, child_pk, week)
    plan, days, language = _plan_with_days(week, _language(request))
    if plan.status != Plan.Status.DONE:
        return redirect("plans:detail", child_pk=child_pk, week=week.week_start.isoformat())
    with translation.override(language):
        return render(
            request,
            "plans/print.html",
            {
                "child": week.child,
                "week": week,
                "plan": plan,
                "days": days,
                "language": language,
                "switch": _switch(plan, days, language),
                "klasse1": week.child.class_level == 1,
            },
        )
