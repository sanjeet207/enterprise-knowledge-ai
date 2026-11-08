"""Shared pieces for the agents: a step trace and the document block sent to models."""
import re
import time
from dataclasses import dataclass, field

from app import tracing

MAX_PASSAGE_CHARS = 2000


@dataclass
class Trace:
    """What each agent did, in order. Stored in the audit log."""
    steps: list = field(default_factory=list)

    def add(self, agent: str, started: float, detail: str = "") -> None:
        self.steps.append({"agent": agent, "ms": int((time.perf_counter() - started) * 1000),
                           "detail": (detail or "")[:400]})
        tracing.record_step(agent, started)


_OUR_TAGS = re.compile(r"<(/?\s*)(source|documents)", re.IGNORECASE)


def neutralise(passage: str) -> str:
    """Stop a document from closing our wrapper tags and writing text that looks like it is outside the data."""
    return _OUR_TAGS.sub(lambda m: "\u2039" + m.group(1) + m.group(2), passage)


def documents_block(passages: list[str]) -> str:
    """Numbered sources. Passages are data: the prompts tell the model to ignore instructions in them,
    and the wrapper tags cannot be forged from inside a passage."""
    docs = "\n".join(
        f'<source id="{i}">\n{neutralise(p[:MAX_PASSAGE_CHARS])}\n</source>' for i, p in enumerate(passages, start=1)
    )
    return f"<documents>\n{docs}\n</documents>"
