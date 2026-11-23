"""Does the claim validator accept answers that are correct?  (database and Ollama needed; no server)

For five Northwind questions the answer model drafted the right figure and the validator still rejected it. This script writes the
correct, cited answer by hand (the figure is taken from the passage that really contains it), gives the validator the passages the
application's retriever returns for the question, and prints the validator's verdict three times, because the model is not
deterministic. If correct answers are rejected, the validator is too strict for them; if they pass, the rejection came from what the
answer model wrote. Nothing is changed.

Usage:  python -m scripts.validator_replay          writes evaluation/VALIDATOR_REPLAY.md
"""
import asyncio
from pathlib import Path

CASES = [
    ("what is the daily meal allowance under the latest travel policy", "1,500",
     "The daily meal allowance under the latest travel policy is INR 1,500 [{n}]."),
    ("at what trip cost does a director need to approve before booking", "150,000",
     "A trip with an estimated cost above INR 150,000 needs the approval of a director before it is booked [{n}]."),
    ("under the old travel policy, what hotel limit applied in metro cities", "9,000",
     "Under the old travel policy, the hotel limit in metro cities was INR 9,000 per night [{n}]."),
    ("how much maternity leave in the UK", "39 weeks", "Maternity leave in the UK is 39 weeks [{n}]."),
    ("how much can I spend on a client dinner per head", "4,000",
     "Client entertainment, including client dinners, is reimbursed up to INR 4,000 per person [{n}]."),
]


async def main():
    from app.agents import validator
    from app.agents.retriever import Retriever
    from app.services import users
    from app.services.vector_store import VectorStoreService

    retriever = Retriever(VectorStoreService())
    user = users.get_with_password_hash("analyst@northwind.test")[0]
    out = ["# Validator replay on correct answers (Northwind)", "",
           "Answer written by hand from the passage that contains the figure; passages as the retriever returns them; "
           "validator run three times.", ""]
    for question, figure, template in CASES:
        hits = retriever.run(user, question, 5)
        passages = [h["parent_content"] for h in hits]
        titles = [str(h["metadata"].get("title")) for h in hits]
        idx = [i + 1 for i, p in enumerate(passages) if figure in p]
        out.append(f"## {question}")
        out.append("Passages: " + "; ".join(f"[{i + 1}] {t}" for i, t in enumerate(titles)))
        if not idx:
            out += [f"- the figure {figure} is in none of the {len(passages)} passages the retriever returned, so the answer model could not have used it", ""]
            continue
        n = idx[0]
        answer = template.format(n=n)
        pos = passages[n - 1].find(figure)
        out.append(f"Figure {figure} is in passage [{n}] (also in {idx[1:] or 'no other'}): ...{' '.join(passages[n - 1][max(0, pos - 160):pos + 90].split())}...")
        out.append(f"Answer checked: {answer}")
        for k in range(3):
            ok, detail = await validator.run(question, answer, passages)
            out.append(f"- run {k + 1}: {'SUPPORTED' if ok else 'UNSUPPORTED ' + detail[:200]}")
        out.append("")
    Path("evaluation/VALIDATOR_REPLAY.md").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    asyncio.run(main())
