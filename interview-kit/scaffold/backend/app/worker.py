# Background processor: `python -m app.worker`. Same image as the API, separate
# process/container -- scale it independently (`docker compose up --scale
# worker=3`); SKIP LOCKED in process_next makes N workers safe. Stateless: kill
# it any time, an in-flight batch rolls back to pending.

import logging
import signal
import time

from app.config import get_settings
from app.deps import close_resources, get_ingest_repository
from app.observability import configure_logging

log = logging.getLogger("app.worker")


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.git_sha)
    repo = get_ingest_repository()
    stopping = False

    def stop(*_) -> None:
        nonlocal stopping
        stopping = True  # finish the current batch, then exit (graceful SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("worker started", extra={"git_sha": settings.git_sha})
    while not stopping:
        try:
            batch_id = repo.process_next(settings.worker_max_attempts)
        except Exception:
            log.exception("batch processing failed")  # DB down or poison batch: back off, keep going
            time.sleep(settings.worker_poll_seconds * 4)
            continue
        if batch_id:
            log.info("batch processed", extra={"batch_id": batch_id})
        else:
            time.sleep(settings.worker_poll_seconds)  # idle poll; LISTEN/NOTIFY would remove it
    close_resources()
    log.info("worker stopped")


if __name__ == "__main__":
    run()
