from app.services import metrics


def setup_function():
    metrics.reset()


def test_counter_renders_with_labels():
    metrics.inc("chat_outcomes_total", outcome="answered")
    metrics.inc("chat_outcomes_total", outcome="answered")
    metrics.inc("chat_outcomes_total", outcome="refused")
    text = metrics.render()
    assert 'chat_outcomes_total{outcome="answered"} 2' in text
    assert 'chat_outcomes_total{outcome="refused"} 1' in text


def test_histogram_buckets_are_cumulative():
    metrics.observe(0.07, route="/x")
    metrics.observe(3, route="/x")
    text = metrics.render()
    assert 'http_request_duration_seconds_bucket{route="/x",le="0.1"} 1' in text
    assert 'http_request_duration_seconds_bucket{route="/x",le="5"} 2' in text
    assert 'http_request_duration_seconds_bucket{route="/x",le="+Inf"} 2' in text
    assert 'http_request_duration_seconds_count{route="/x"} 2' in text
