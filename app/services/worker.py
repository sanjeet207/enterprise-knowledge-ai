"""The background loop that turns queued uploads into searchable documents."""
import logging
import threading
import time

from app.services import jobs

log = logging.getLogger("worker")
_stop = threading.Event()


def loop(stop: threading.Event, idle_seconds: float = 1.0) -> None:
    last_sweep = 0.0
    while not stop.is_set():
        busy = False
        try:
            if time.monotonic() - last_sweep > 60:
                recovered = jobs.requeue_stuck()
                if recovered:
                    log.warning("recovered %s stuck upload job(s)", recovered)
                last_sweep = time.monotonic()
            busy = jobs.run_one()
        except Exception:  # noqa: BLE001 - e.g. the database is restarting; wait and try again
            log.exception("worker loop error")
            stop.wait(5)
        if not busy:
            stop.wait(idle_seconds)


def start() -> threading.Thread:
    _stop.clear()
    thread = threading.Thread(target=loop, args=(_stop,), name="ingest-worker", daemon=True)
    thread.start()
    return thread


def stop() -> None:
    _stop.set()
