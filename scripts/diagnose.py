"""Ask one question as a demo user and print every step the assistant took, without saving to the audit log.

Usage: python -m scripts.diagnose manager "who must approve a vendor contract worth 30 lakh rupees"
       python -m scripts.diagnose analyst "Is it ok to keep customer files in my personal Dropbox?" --runs 3
Needs the database and Ollama. The user is a demo user name (analyst, manager, director, ...).
"""
import argparse
import asyncio

from app.agents import orchestrator
from app.agents.retriever import Retriever
from app.services import audit, users
from app.services.vector_store import VectorStoreService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("user")
    parser.add_argument("question")
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    email = args.user if "@" in args.user else f"{args.user}@{'globex' if args.user.startswith('globex') else 'acme'}.test"
    found = users.get_with_password_hash(email)
    if not found:
        print(f"No such user: {email}")
        return 1
    user = found[0]
    retriever = Retriever(VectorStoreService())
    captured = {}
    audit.log_event = lambda u, q, outcome, top, sources, answer, model, ms, notes, steps: captured.update(steps=steps)
    for run in range(1, args.runs + 1):
        result = asyncio.run(orchestrator.answer_question(user, args.question, 5, retriever))
        print(f"\n=== run {run}: {result['outcome']} ===")
        for step in captured.get("steps", []):
            print(f"  {step['agent']:<10} {step['ms']:>6} ms  {step['detail']}")
        print(f"  ANSWER: {result['answer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
