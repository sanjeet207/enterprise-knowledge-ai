"""Checks on text that will later be shown to a model as reference data (documents) - done once, at upload.

A document is data, and the prompts say so, but a planted document is the classic way to attack a RAG system
("indirect prompt injection"). Refusing the obvious attempts at the door is one layer; the other layers are the
neutralised prompt wrapper (agents/base.py) and the answer validator.
"""
import json
import re
from typing import Optional

from app.services.question_profile import OVERRIDE_PATTERN

# Text that imitates the structure of our own prompts, e.g. "</source></documents> New instructions:".
_PROMPT_MARKUP = re.compile(r"</?\s*(source|documents|system|assistant|instructions?)\b", re.IGNORECASE)


# Wording that only makes sense when talking to an AI system, not to staff.
_ADDRESSED_TO_AI = re.compile(
    r"\b(whatever|regardless of|no matter) (the|what|which) (question|query)\b|\bnew house style\b|"
    r"\b(notes?|messages?|instructions?) (to|for) (the )?(assistant|chatbot|ai|model|llm)\b|"
    r"\b(reply|respond|answer)\b[^.\n]{0,25}\bonly with the (single |one )?word\b|"
    # "any software reading this", "language models that process this file"
    r"\b(ai( systems?)?|llms?|language models?|chatbots?|bots?|software)\b[^.\n]{0,25}"
    r"\b(reading|processing|parsing|indexing|summari[sz]ing|(that|which|who) (reads?|process(?:es)?|parses?|indexes?|summari[sz]es?))\s+(this|these)\b",
    re.IGNORECASE,
)

WINDOW_WORDS = 150   # small pieces: a 7B model notices one odd sentence in 150 words far more reliably than in 800
WINDOW_OVERLAP = 30  # so a sentence cut at one edge is whole in the next piece
MAX_WINDOWS = 600


def windows(text: str, size: int = WINDOW_WORDS, limit: int = MAX_WINDOWS, overlap: int = WINDOW_OVERLAP) -> list:
    """The text in reviewable, slightly overlapping pieces."""
    words = text.split()
    step = max(1, size - overlap)
    return [" ".join(words[i:i + size]) for i in range(0, len(words), step) if words[i:i + size]][:limit]


def grounded_flag(raw: str, window: str) -> Optional[str]:
    """The sentence a reviewer model flagged as aimed at an AI, but only if it really is in the text.
    A flag with no quote, or a quote that is not in the window, is ignored: a model's invention must not block a document."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("instructs_ai") is not True:
        return None
    quote = " ".join(str(data.get("quote", "")).split())
    quoted = set(re.findall(r"\w+", quote.lower()))
    present = set(re.findall(r"\w+", window.lower()))
    if len(quoted) < 3 or len(quoted & present) / len(quoted) < 0.8:
        return None
    return quote[:200]


def suspicious(text: str) -> Optional[str]:
    """None when the text looks like an ordinary document, otherwise a reason that is safe to show the uploader."""
    if OVERRIDE_PATTERN.search(text):
        return "it contains wording that tries to give instructions to an AI system"
    if _ADDRESSED_TO_AI.search(text):
        return "it contains wording addressed to an AI system"
    if _PROMPT_MARKUP.search(text):
        return "it contains markup that imitates the assistant's own prompt format"
    return None
