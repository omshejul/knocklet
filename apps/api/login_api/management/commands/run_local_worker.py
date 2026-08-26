import fcntl
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from login_api.automation import (
    enqueue_acceptance_check,
    recover_interrupted_work,
    run_due_work_once,
)


class Command(BaseCommand):
    help = "Run the sequential local outreach worker."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--poll-seconds", type=float, default=2.0)

    def handle(self, *args, **options):
        lock_path = Path(settings.DATABASE_PATH).with_suffix(".worker.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("w") as lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise CommandError("The local worker is already running.") from error

            recovered = recover_interrupted_work()
            if recovered:
                self.stdout.write(f"Marked {recovered} interrupted item(s) for review.")

            while True:
                close_old_connections()
                enqueue_acceptance_check()
                work_item = run_due_work_once()
                if options["once"]:
                    return
                if work_item is None:
                    time.sleep(max(options["poll_seconds"], 0.25))
