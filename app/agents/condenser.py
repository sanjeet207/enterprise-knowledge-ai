"""Condenser agent: turns a follow-up question into a standalone one. Sees the person's earlier questions only."""
from typing import List

from app import config
from app.services import followup, llm

NAME = "condenser"


async def run(previous: List[str], question: str) -> str:
    raw = await llm.chat(followup.build_prompt(previous), question, model=config.agent_model(NAME),
                         num_predict=100, timeout=60.0)
    return followup.clean_standalone(question, raw)
