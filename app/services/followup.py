"""Follow-up questions ("and for managers?") need the earlier question to make sense.

Only the person's own earlier QUESTIONS are used as context, never earlier answers. Answers are not trusted input,
and a question can never smuggle restricted text into a later search. The rewritten question goes through every
normal check again (access control, citations, validation), so a bad rewrite can only cause a poor answer, not a leak.
"""
import re
from typing import List

from app.services import question_profile

MAX_STANDALONE = 300
_LEADS = re.compile(r"^(and|also|then|so|but|what about|how about|what if|why|how|when|where|who|which|can i|do i)\b", re.IGNORECASE)
_PRONOUNS = {"it", "its", "that", "this", "they", "them", "their", "those", "these", "he", "she", "there", "one", "ones", "same", "former", "latter"}


def needs_context(question: str, previous: List[str]) -> bool:
    """True when there is something earlier to refer to and the question looks incomplete without it."""
    if not previous:
        return False
    words = question_profile.words(question)
    if len(question.split()) <= 6:
        return True
    return bool(words & _PRONOUNS) or bool(_LEADS.match(question.strip()) and len(question.split()) <= 12)


def build_prompt(previous: List[str]) -> str:
    recent = "\n".join(f"- {q}" for q in previous[-3:])
    return (
        "You rewrite a follow-up question so that it can be understood on its own. "
        "Use the earlier questions only to fill in what the new question refers to. "
        "Keep the meaning, the language and any numbers or names exactly. Do not answer the question. "
        "Do not add anything that is not needed. If the new question is already complete, repeat it unchanged. "
        "Reply with the rewritten question only, on one line.\n"
        f"Earlier questions from the same person:\n{recent}"
    )


def clean_standalone(original: str, output: str) -> str:
    """The rewritten question, or the original when the rewrite is unusable or looks like an instruction."""
    text = (output or "").strip().strip('"\'`').strip()
    if not text or "\n" in text or len(text) > MAX_STANDALONE or len(text) < 3:
        return original
    if question_profile.OVERRIDE_PATTERN.search(text) and not question_profile.OVERRIDE_PATTERN.search(original):
        return original
    return text
