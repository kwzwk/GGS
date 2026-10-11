"""A small database-backed job queue, processed by `manage.py run_worker`.

Handlers are plain functions registered with @handler("kind"). A handler raises
ServiceUnavailable when an outside service (Ollama) can't be reached: the job
then goes back to the queue without counting as a failed attempt, and the
worker pauses before trying again.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Job

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
_handlers = {}


class ServiceUnavailable(Exception):
    """An outside service is down; retry the job later without penalty."""


def handler(kind):
    def register(func):
        _handlers[kind] = func
        return func

    return register


def enqueue(kind, **payload):
    """Queue a job. It becomes visible to the worker with the surrounding transaction."""
    job = Job.objects.create(kind=kind, payload=payload)
    return job


def recover_stale():
    """Jobs left 'running' by a crash or restart go back to the queue."""
    return Job.objects.filter(status=Job.Status.RUNNING).update(status=Job.Status.QUEUED)


def pending_count():
    return Job.objects.filter(status__in=[Job.Status.QUEUED, Job.Status.RUNNING]).count()


def claim_next():
    now = timezone.now()
    with transaction.atomic():
        job = Job.objects.filter(status=Job.Status.QUEUED, run_after__lte=now).first()
        if job is None:
            return None
        claimed = Job.objects.filter(pk=job.pk, status=Job.Status.QUEUED).update(
            status=Job.Status.RUNNING, started_at=now
        )
    if not claimed:
        return None
    job.refresh_from_db()
    return job


def run(job):
    """Run a claimed job. Returns False if it was put back because a service is down."""
    func = _handlers.get(job.kind)
    try:
        if func is None:
            raise LookupError(f"No handler for job kind {job.kind!r}")
        func(**job.payload)
    except ServiceUnavailable as exc:
        Job.objects.filter(pk=job.pk).update(status=Job.Status.QUEUED, last_error=str(exc))
        return False
    except Exception as exc:
        logger.exception("Job %s failed", job)
        attempts = job.attempts + 1
        if attempts >= MAX_ATTEMPTS:
            Job.objects.filter(pk=job.pk).update(
                status=Job.Status.FAILED,
                attempts=attempts,
                last_error=repr(exc),
                finished_at=timezone.now(),
            )
            failed = getattr(func, "on_failure", None)
            if failed:
                failed(error=exc, **job.payload)
        else:
            Job.objects.filter(pk=job.pk).update(
                status=Job.Status.QUEUED,
                attempts=attempts,
                last_error=repr(exc),
                run_after=timezone.now() + timedelta(minutes=2**attempts),
            )
        return True
    Job.objects.filter(pk=job.pk).update(
        status=Job.Status.DONE, last_error="", finished_at=timezone.now()
    )
    return True


def retry(queryset):
    return queryset.filter(status=Job.Status.FAILED).update(
        status=Job.Status.QUEUED, attempts=0, run_after=timezone.now()
    )
