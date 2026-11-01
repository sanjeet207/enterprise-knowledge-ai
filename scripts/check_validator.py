"""Check the validator agent against answers we know are right or wrong. Needs the model server running.

Usage: python -m scripts.check_validator
Each wrong answer is planted by hand; the validator should call it UNSUPPORTED.
"""
import asyncio
import sys

from app.agents import validator

SOURCES = [
    "Full-time employees receive twenty-four days of paid annual leave each year. Up to ten unused days may be "
    "carried forward to the next year. Leave of more than five consecutive days needs manager approval.",
    "Claims must be submitted within 30 days of travel. Meal expenses on single-day trips are reimbursable up to "
    "the daily cap and need itemised receipts.",
]
Q = "Tell me about leave and travel claims."

CASES = [
    ("correct, cited", "Employees get twenty-four days of annual leave [1].", True),
    ("correct, two sources", "Leave is twenty-four days [1] and travel claims are due within 30 days [2].", True),
    ("wrong number", "Employees get thirty days of annual leave [1].", False),
    ("wrong carry-forward", "Up to twenty unused days may be carried forward [1].", False),
    ("invented fact", "Employees also receive a yearly travel allowance of 50000 [2].", False),
    ("wrong citation", "Travel claims must be submitted within 30 days [1].", False),
    ("mixed true and invented", "Employees get twenty-four days of leave [1] and free hotel stays on all trips [2].", False),
]


async def main() -> int:
    wrong = 0
    for name, answer, expected in CASES:
        ok, raw = await validator.run(Q, answer, SOURCES)
        status = "ok " if ok == expected else "BAD"
        wrong += ok != expected
        print(f"{status} {name:28} expected {'SUPPORTED' if expected else 'UNSUPPORTED':11} got: {raw[:70]}")
    print(f"\n{len(CASES) - wrong}/{len(CASES)} as expected")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
