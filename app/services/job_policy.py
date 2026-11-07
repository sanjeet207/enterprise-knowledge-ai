"""Pure rules for background jobs: whether to retry, how long to wait, when a job counts as stuck.

No database and no clock in here, so every rule can be unit-tested.
"""
MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 2
MAX_DELAY_SECONDS = 60
STUCK_AFTER_SECONDS = 600  # a job "processing" for longer than this lost its worker (crash, restart)
MAX_PENDING_PER_USER = 20


def backoff_seconds(attempts: int) -> int:
    """Wait before the next try: 2 s, 4 s, 8 s ... capped. Gives a struggling dependency time to recover."""
    attempts = max(1, attempts)
    return min(MAX_DELAY_SECONDS, BASE_DELAY_SECONDS * 2 ** (attempts - 1))


def after_failure(attempts: int, permanent: bool, max_attempts: int = MAX_ATTEMPTS):
    """What happens to a job that just failed: ("failed", 0) or ("queued", seconds_to_wait).

    A permanent failure (duplicate content, no longer allowed, empty file) is never retried: retrying cannot fix it.
    """
    if permanent or attempts >= max_attempts:
        return "failed", 0
    return "queued", backoff_seconds(attempts)


def publish_status(queued_as: str, uploader_is_admin_now: bool) -> str:
    """The safer of 'what we promised at upload' and 'what the uploader may do right now'."""
    return "published" if queued_as == "published" and uploader_is_admin_now else "pending"
