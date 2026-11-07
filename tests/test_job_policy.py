from app.services import job_policy as jp


def test_backoff_doubles_and_is_capped():
    assert [jp.backoff_seconds(n) for n in (1, 2, 3, 4)] == [2, 4, 8, 16]
    assert jp.backoff_seconds(50) == jp.MAX_DELAY_SECONDS
    assert jp.backoff_seconds(0) == 2


def test_transient_failure_is_retried_with_a_wait():
    assert jp.after_failure(1, permanent=False) == ("queued", 2)
    assert jp.after_failure(2, permanent=False) == ("queued", 4)


def test_failure_after_the_last_attempt_is_final():
    assert jp.after_failure(jp.MAX_ATTEMPTS, permanent=False) == ("failed", 0)


def test_permanent_failure_is_never_retried():
    assert jp.after_failure(1, permanent=True) == ("failed", 0)


def test_publish_status_takes_the_safer_option():
    assert jp.publish_status("published", True) == "published"
    assert jp.publish_status("published", False) == "pending"  # lost admin rights while queued
    assert jp.publish_status("pending", True) == "pending"      # never upgraded behind the uploader's back
    assert jp.publish_status("pending", False) == "pending"
