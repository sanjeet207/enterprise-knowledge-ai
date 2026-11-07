"""Tiny Prometheus-style metrics, in memory. Enough for a dashboard and alerts without another dependency."""
import threading
from collections import defaultdict
from typing import Dict, Tuple

BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)

_lock = threading.Lock()
_counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)
_hist: Dict[Tuple[Tuple[str, str], ...], list] = {}


def _key(labels: dict) -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted((k, str(v)) for k, v in labels.items()))


def inc(name: str, **labels) -> None:
    with _lock:
        _counters[(name, _key(labels))] += 1


def observe(seconds: float, **labels) -> None:
    key = _key(labels)
    with _lock:
        h = _hist.setdefault(key, [[0] * len(BUCKETS), 0.0, 0])
        for i, bound in enumerate(BUCKETS):
            if seconds <= bound:
                h[0][i] += 1
        h[1] += seconds
        h[2] += 1


def _fmt(labels: Tuple[Tuple[str, str], ...], extra: str = "") -> str:
    parts = [f'{k}="{v}"' for k, v in labels] + ([extra] if extra else [])
    return "{" + ",".join(parts) + "}" if parts else ""


def render() -> str:
    lines = []
    with _lock:
        for (name, labels), value in sorted(_counters.items()):
            lines.append(f"{name}{_fmt(labels)} {value:g}")
        for labels, (counts, total, n) in sorted(_hist.items()):
            for bound, c in zip(BUCKETS, counts):
                le = 'le="%s"' % bound
                lines.append("http_request_duration_seconds_bucket%s %s" % (_fmt(labels, le), c))
            lines.append("http_request_duration_seconds_bucket%s %s" % (_fmt(labels, 'le="+Inf"'), n))
            lines.append(f"http_request_duration_seconds_sum{_fmt(labels)} {total:g}")
            lines.append(f"http_request_duration_seconds_count{_fmt(labels)} {n}")
    return "\n".join(lines) + "\n"


def reset() -> None:
    with _lock:
        _counters.clear()
        _hist.clear()
