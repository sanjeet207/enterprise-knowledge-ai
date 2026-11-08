"""Tracing: privacy filter, OTLP shape, parent/child links, and that it is harmless when off."""
import asyncio

from app import tracing


class Capture(tracing.Exporter):
    def __init__(self):  # no thread, no network
        self.spans = []

    def add(self, span):
        self.spans.append(span)


def _on():
    cap = Capture()
    tracing._exporter = cap
    return cap


def _off():
    tracing._exporter = None


def test_content_keys_are_dropped():
    out = tracing.safe_attributes({"question": "what is my salary", "answer": "x", "user.email": "a@b.c", "detail": "d",
                                   "passages": 5, "http.route": "/chat", "ok": True})
    assert out == {"passages": 5, "http.route": "/chat", "ok": True}


def test_long_strings_are_cut_and_objects_dropped():
    out = tracing.safe_attributes({"model": "x" * 500, "obj": {"a": 1}, "lst": [1]})
    assert len(out["model"]) == tracing.MAX_VALUE_CHARS and "obj" not in out and "lst" not in out


def test_parse_headers():
    assert tracing.parse_headers("a=1, b=2=3,bad,=x") == {"a": "1", "b": "2=3"}
    assert tracing.parse_headers("") == {}


def test_attribute_value_types():
    assert tracing.attribute_value(True) == {"boolValue": True}
    assert tracing.attribute_value(7) == {"intValue": "7"}
    assert tracing.attribute_value(1.5) == {"doubleValue": 1.5}
    assert tracing.attribute_value("s") == {"stringValue": "s"}


def test_off_is_a_noop():
    _off()
    with tracing.span("x", a=1) as s:
        s.set(b=2)
    tracing.record_step("planner", 0.0)
    assert tracing.current_trace_id() == "" and not tracing.enabled()


def test_nested_spans_share_trace_and_link_parent():
    cap = _on()
    try:
        with tracing.span("outer") as o:
            with tracing.span("inner", n=1):
                assert tracing.current_trace_id() == o.trace_id
        inner, outer = cap.spans
        assert inner["trace_id"] == outer["trace_id"] and inner["parent_id"] == outer["span_id"]
        assert outer["parent_id"] is None
    finally:
        _off()


def test_error_marks_span_and_reraises():
    cap = _on()
    try:
        try:
            with tracing.span("boom"):
                raise ValueError("x")
        except ValueError:
            pass
        assert cap.spans[0]["error"] is True
        assert tracing.span_to_otlp(cap.spans[0])["status"] == {"code": 2}
    finally:
        _off()


def test_parent_survives_await_points():
    cap = _on()

    async def child():
        await asyncio.sleep(0)
        with tracing.span("child"):
            pass

    async def main():
        with tracing.span("root"):
            await child()

    try:
        asyncio.run(main())
        child_span, root = cap.spans
        assert child_span["parent_id"] == root["span_id"]
    finally:
        _off()


def test_record_step_is_retroactive_and_content_free():
    import time
    cap = _on()
    try:
        with tracing.span("req"):
            tracing.record_step("validator", time.perf_counter() - 0.05)
        step = cap.spans[0]
        assert step["name"] == "agent.validator" and step["attributes"] == {"agent": "validator"}
        assert step["end_ns"] - step["start_ns"] >= 40_000_000
        assert step["parent_id"] == cap.spans[1]["span_id"]
    finally:
        _off()


def test_otlp_payload_shape():
    span = {"trace_id": "a" * 32, "span_id": "b" * 16, "parent_id": "c" * 16, "name": "n", "start_ns": 1, "end_ns": 2,
            "attributes": {"k": 1}, "error": False}
    payload = tracing.build_payload([span], "svc")
    rs = payload["resourceSpans"][0]
    assert rs["resource"]["attributes"][0]["value"] == {"stringValue": "svc"}
    s = rs["scopeSpans"][0]["spans"][0]
    assert s["parentSpanId"] == "c" * 16 and s["startTimeUnixNano"] == "1" and s["status"] == {"code": 1}
    assert s["attributes"] == [{"key": "k", "value": {"intValue": "1"}}]


def test_ids_have_the_right_length():
    assert len(tracing.new_trace_id()) == 32 and len(tracing.new_span_id()) == 16


def test_queue_full_drops_instead_of_blocking():
    ex = tracing.Exporter.__new__(tracing.Exporter)
    import queue
    ex.queue, ex.dropped = queue.Queue(maxsize=1), 0
    ex.add({"a": 1})
    ex.add({"a": 2})
    assert ex.dropped == 1


def test_agent_trace_steps_become_spans_without_their_text():
    import time
    from app.agents.base import Trace
    cap = _on()
    try:
        trace = Trace()
        with tracing.span("req"):
            trace.add("answerer", time.perf_counter(), detail="salary of Priya is 90000")
        step = cap.spans[0]
        assert step["name"] == "agent.answerer"
        assert "90000" not in str(step) and "Priya" not in str(step)
        assert trace.steps[0]["detail"].startswith("salary")  # the audit log keeps it; the trace never does
    finally:
        _off()
