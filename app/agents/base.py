"""Shared pieces for the agents: a step trace and the document block sent to models."""
import time
from dataclasses import dataclass, field

MAX_PASSAGE_CHARS = 2000


@dataclass
class Trace:
    """What each agent did, in order. Stored in the audit log."""
    steps: list = field(default_factory=list)

    def add(self, agent: str, started: float, detail: str = "") -> None:
        self.steps.append({"agent": agent, "ms": int((time.perf_counter() - started) * 1000),
                           "detail": (detail or "")[:160]})


def documents_block(passages: list[str]) -> str:
    """Numbered sources. Passages are data: the prompts tell the model to ignore instructions in them."""
    docs = "\n".join(
        f'<source id="{i}">\n{p[:MAX_PASSAGE_CHARS]}\n</source>' for i, p in enumerate(passages, start=1)
    )
    return f"<documents>\n{docs}\n</documents>"
