import logging
import time

from django.core.management.base import BaseCommand

from jobs import queue

logger = logging.getLogger("jobs.worker")

IDLE_SLEEP = 5
MIN_PAUSE = 15
MAX_PAUSE = 60


class Command(BaseCommand):
    help = "Process background jobs until stopped."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process ready jobs, then exit.")

    def handle(self, *args, **options):
        recovered = queue.recover_stale()
        if recovered:
            logger.info("Re-queued %d interrupted job(s).", recovered)
        logger.info("Worker started.")
        pause = MIN_PAUSE
        while True:
            job = queue.claim_next()
            if job is None:
                if options["once"]:
                    return
                time.sleep(IDLE_SLEEP)
                continue
            if queue.run(job):
                pause = MIN_PAUSE
                continue
            # A service the job needs is down (e.g. the GPU PC is off). Wait and
            # try again, backing off so an offline server isn't hammered.
            if options["once"]:
                return
            logger.info("Service unavailable; retrying in %ds.", pause)
            time.sleep(pause)
            pause = min(pause * 2, MAX_PAUSE)
