import datetime

from django.contrib import messages
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from children.models import Child
from jobs.queue import enqueue
from llm.client import is_known_unreachable

from .forms import UploadForm
from .images import InvalidUpload, pages_from_bytes
from .models import Page, Upload, Week

ANALYSE = "worksheets.analyse_page"


def _own_child(request, child_pk):
    return get_object_or_404(Child, pk=child_pk, parent=request.user)


def _own_page(request, child_pk, pk):
    return get_object_or_404(
        Page.objects.select_related("upload__week"),
        pk=pk,
        upload__week__child__pk=child_pk,
        upload__week__child__parent=request.user,
    )


@login_required
def week_list(request, child_pk):
    child = _own_child(request, child_pk)
    weeks = child.weeks.all()
    return render(request, "worksheets/week_list.html", {"child": child, "weeks": weeks})


@login_required
def upload(request, child_pk):
    child = _own_child(request, child_pk)
    initial = {}
    if request.GET.get("week"):
        try:
            initial["week"] = datetime.date.fromisoformat(request.GET["week"])
        except ValueError:
            pass
    form = UploadForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        converted, rejected = [], []
        for f in form.cleaned_data["files"]:
            data = f.read()
            try:
                converted.append((f, data, pages_from_bytes(data)))
            except InvalidUpload:
                rejected.append(f.name)
        for name in rejected:
            messages.error(
                request,
                _("%(name)s could not be read. Please upload a photo (JPEG, PNG, HEIC) or a PDF.")
                % {"name": name},
            )
        if converted:
            language = translation.get_language() or "de"
            with transaction.atomic():
                week, _created = Week.objects.get_or_create(
                    child=child, week_start=form.cleaned_data["week"]
                )
                count = 0
                for f, data, images in converted:
                    up = Upload(week=week, original_name=f.name[:255], content_type=f.content_type or "")
                    up.file.save(f.name, ContentFile(data), save=False)
                    up.save()
                    for number, image in enumerate(images, start=1):
                        page = Page(upload=up, page_number=number, language=language[:5])
                        page.image.save("page.jpg", image, save=False)
                        page.save()
                        enqueue(ANALYSE, page_id=page.pk)
                        count += 1
            messages.success(
                request,
                _("Uploaded. %(count)d page(s) will be analysed.") % {"count": count},
            )
            return redirect("worksheets:week", child_pk=child.pk, week=week.week_start.isoformat())
    return render(request, "worksheets/upload.html", {"child": child, "form": form})


def _parse_week(value):
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise Http404 from None


@login_required
def week_detail(request, child_pk, week):
    child = _own_child(request, child_pk)
    week = get_object_or_404(Week, child=child, week_start=_parse_week(week))
    pages = list(week.pages())
    pending = any(p.is_pending for p in pages)
    return render(
        request,
        "worksheets/week_detail.html",
        {
            "child": child,
            "week": week,
            "pages": pages,
            "pending": pending,
            "server_offline": pending and is_known_unreachable(),
            "plan": getattr(week, "plan", None),
            "can_plan": not pending and any(p.status == Page.Status.DONE for p in pages),
        },
    )


@login_required
def page_image(request, child_pk, pk):
    page = _own_page(request, child_pk, pk)
    response = FileResponse(page.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=86400"
    return response


@login_required
@require_POST
def page_delete(request, child_pk, pk):
    page = _own_page(request, child_pk, pk)
    week = page.upload.week
    with transaction.atomic():
        upload = page.upload
        page.delete()
        if not upload.pages.exists():
            upload.delete()
    messages.success(request, _("The page was removed."))
    return redirect("worksheets:week", child_pk=child_pk, week=week.week_start.isoformat())


@login_required
@require_POST
def page_retry(request, child_pk, pk):
    page = _own_page(request, child_pk, pk)
    if page.status == Page.Status.FAILED:
        with transaction.atomic():
            Page.objects.filter(pk=page.pk).update(status=Page.Status.QUEUED, error="")
            enqueue(ANALYSE, page_id=page.pk)
    return redirect("worksheets:week", child_pk=child_pk, week=page.upload.week.week_start.isoformat())
