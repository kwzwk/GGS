from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from . import queue
from .models import Job

calls = []


@queue.handler("test.ok")
def ok(value):
    calls.append(value)


@queue.handler("test.boom")
def boom():
    raise RuntimeError("boom")


boom.on_failure = lambda error: calls.append(f"failed: {error}")


@queue.handler("test.offline")
def offline():
    raise queue.ServiceUnavailable("server off")


class QueueTests(TestCase):
    def setUp(self):
        calls.clear()

    def run_next(self):
        job = queue.claim_next()
        self.assertIsNotNone(job)
        return queue.run(job), Job.objects.get(pk=job.pk)

    def test_success(self):
        queue.enqueue("test.ok", value=42)
        ran, job = self.run_next()
        self.assertTrue(ran)
        self.assertEqual(job.status, Job.Status.DONE)
        self.assertEqual(calls, [42])
        self.assertIsNone(queue.claim_next())

    def test_failure_backs_off_then_fails(self):
        queue.enqueue("test.boom")
        for attempt in (1, 2):
            _, job = self.run_next()
            self.assertEqual(job.status, Job.Status.QUEUED)
            self.assertEqual(job.attempts, attempt)
            self.assertGreater(job.run_after, timezone.now())
            self.assertIsNone(queue.claim_next())  # not due yet
            Job.objects.filter(pk=job.pk).update(run_after=timezone.now() - timedelta(seconds=1))
        _, job = self.run_next()
        self.assertEqual(job.status, Job.Status.FAILED)
        self.assertEqual(calls, ["failed: boom"])

        self.assertEqual(queue.retry(Job.objects.all()), 1)
        job.refresh_from_db()
        self.assertEqual((job.status, job.attempts), (Job.Status.QUEUED, 0))

    def test_service_unavailable_requeues_without_attempt(self):
        queue.enqueue("test.offline")
        ran, job = self.run_next()
        self.assertFalse(ran)
        self.assertEqual((job.status, job.attempts), (Job.Status.QUEUED, 0))
        self.assertEqual(job.last_error, "server off")

    def test_unknown_kind_fails(self):
        queue.enqueue("test.nope")
        _, job = self.run_next()
        self.assertEqual(job.attempts, 1)
        self.assertIn("No handler", job.last_error)

    def test_recover_stale_and_worker_once(self):
        Job.objects.create(kind="test.ok", payload={"value": 1}, status=Job.Status.RUNNING)
        queue.enqueue("test.ok", value=2)
        call_command("run_worker", "--once", stdout=StringIO())
        self.assertEqual(sorted(calls), [1, 2])
        self.assertEqual(queue.pending_count(), 0)
