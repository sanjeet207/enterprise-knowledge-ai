"""Plain-code analysis of a question: how deep to think, what shape the answer should have, and
whether it must never be answered from general knowledge.

No model is used here, so the result is instant, repeatable and easy to test.
"""
import re

# Words that mean the question is about this organisation (its people, money, rules or projects).
# Such a question may only be answered from company documents the user is allowed to see.
# Over-matching is the safe direction: the question is refused instead of answered from model memory.
COMPANY_WORDS = {
    "our", "ours", "we", "my", "mine", "acme", "globex", "titan", "company", "firm", "employer",
    "internal", "employee", "employees", "staff", "manager", "managers", "director", "directors",
    "partner", "partners", "salary", "salaries", "compensation", "bonus", "bonuses", "attrition",
    "headcount", "payroll", "policy", "policies", "allowed", "permitted", "entitled", "eligible",
    "reimburse", "reimbursed", "reimbursable", "reimbursement", "approval", "approve", "approved",
    "sign", "signoff", "limit", "limits", "cap", "caps", "threshold", "thresholds", "deadline", "valuation",
    "board", "client", "clients",
    # Questions about "the top / worst" of an organisation's own risks, teams or figures.
    "enterprise", "top", "worst", "retention",
}

# Attempts to override the assistant's rules are never answered, with or without documents.
OVERRIDE_PATTERN = re.compile(
    r"\b(ignore|disregard|forget)\b.{0,40}\b(instructions?|rules?|prompts?)\b|"
    r"\b(system override|system prompt|developer mode|admin mode|jailbreak|reveal your|you are now)\b",
    re.IGNORECASE,
)

# Live or recent information: a model's memory cannot answer these, so a general answer would mislead.
LIVE_PATTERN = re.compile(
    r"\b(today|tonight|yesterday|tomorrow|right now|latest|recent|recently|news|weather|forecast|scores?|"
    r"who won|this (week|month|year)|last (night|week|month|year|time)|current(ly)?(?! (ratio|assets|liabilit|account)))\b|"
    r"\b(the|a) last\b.*\b(cup|final|match|election|season|game)\b",
    re.IGNORECASE,
)

_STEPS = re.compile(r"\b(how (do|can|should|would|to)|steps?|procedure|walk me through|guide)\b", re.IGNORECASE)
_COMPARE = re.compile(r"\b(compare|difference|differences|differ|versus|vs)\b", re.IGNORECASE)
_LIST = re.compile(r"\b(list|what are|which are|enumerate|name all|types of|kinds of)\b", re.IGNORECASE)
_DEEP = re.compile(
    r"\b(explain|why|analy[sz]e|analysis|evaluate|discuss|implications?|pros and cons|trade-?offs?|"
    r"in detail|step by step|compare|difference)\b",
    re.IGNORECASE,
)


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def blocked_for_general(question: str) -> bool:
    """True when the question must not be answered from the model's own knowledge: it is about the company,
    tries to override the rules, or needs live or recent information."""
    return (bool(words(question) & COMPANY_WORDS) or bool(OVERRIDE_PATTERN.search(question))
            or bool(LIVE_PATTERN.search(question)))


def profile(question: str) -> dict:
    """{'depth': quick|standard|deep, 'format': short|list|steps|compare}."""
    count = len(question.split())
    if _COMPARE.search(question):
        fmt = "compare"
    elif _STEPS.search(question):
        fmt = "steps"
    elif _LIST.search(question):
        fmt = "list"
    else:
        fmt = "short"
    if _DEEP.search(question) or count > 25 or question.count("?") > 1:
        depth = "deep"
    elif count <= 8:
        depth = "quick"
    else:
        depth = "standard"
    return {"depth": depth, "format": fmt}


STYLE_TEXT = {
    "short": "",
    "list": "Present the answer as a short bulleted list.",
    "steps": "Present the answer as short numbered steps.",
    "compare": "Present the answer as a short comparison, one line for each item.",
}


def style_for(fmt: str) -> str:
    return STYLE_TEXT.get(fmt, "")
