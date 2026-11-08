"""Run the upload worker as its own process (for deployments where the web process should stay light).

Usage: INGEST_WORKER_ENABLED=false uvicorn app.main:app   # web only
       python -m scripts.worker                           # one or more of these
"""
import signal
import threading

from app import tracing
from app.services import worker


def main() -> None:
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    tracing.setup()
    print("Upload worker running. Press Ctrl+C to stop.")
    worker.loop(stop)
    tracing.shutdown()


if __name__ == "__main__":
    main()
