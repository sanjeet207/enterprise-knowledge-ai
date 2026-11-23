import json
import time

from app.agents.base import Trace
from app.routers.chat import sse


def test_trace_tells_the_listener_the_step_name_and_time_only():
    seen = []
    trace = Trace(listener=lambda agent, ms: seen.append((agent, ms)))
    trace.add("retriever", time.perf_counter(), "score 0.9: Salary bands for managers")
    assert len(seen) == 1 and seen[0][0] == "retriever" and isinstance(seen[0][1], int)
    assert "Salary" not in json.dumps(seen)  # the detail text can name documents and stays in the audit log


def test_a_broken_listener_never_breaks_an_answer():
    def boom(agent, ms):
        raise RuntimeError("client went away")
    trace = Trace(listener=boom)
    trace.add("router", time.perf_counter())
    assert [s["agent"] for s in trace.steps] == ["router"]


def test_events_are_valid_server_sent_events():
    text = sse("step", {"agent": "refiner", "ms": 12})
    assert text == 'event: step\ndata: {"agent": "refiner", "ms": 12}\n\n'


def test_the_stream_route_is_mounted_and_needs_a_signed_in_user():
    from app.main import app
    route = next(r for r in app.routes if getattr(r, "path", "") == "/chat/stream")
    assert "POST" in route.methods
    assert "get_current_user" in [d.call.__name__ for d in route.dependant.dependencies]
