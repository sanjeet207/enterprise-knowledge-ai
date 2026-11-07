"""Does the research assistant add anything over a single question, and does it ever show more than the asker may see?

Usage (server running):  python -m scripts.evaluate_research [--base-url URL]

For every task in tests/research_set.json it asks for a report as the named user and, as a baseline, asks the
same request once as an ordinary question. It then counts, per task:
  coverage  how many of the expected documents were cited (report vs the single question)
  leaks     forbidden documents cited anywhere in the report (must be 0)
Writes evaluation/RESEARCH_EVAL.md. The tasks are written by the author; an independent set is still needed.
"""
import argparse
import json
import time
from pathlib import Path

import httpx

PASSWORD = "DemoPass2026x"  # local demo data only
ROOT = Path(__file__).resolve().parent.parent


def coverage(expected, cited):
    return sum(1 for d in expected if d in cited)


def score_task(task: dict, report_titles: set, baseline_titles: set) -> dict:
    """Pure scoring of one task."""
    return {"expected": len(task["expect_docs"]),
            "report_hits": coverage(task["expect_docs"], report_titles),
            "baseline_hits": coverage(task["expect_docs"], baseline_titles),
            "leaks": sorted(d for d in task["forbidden_docs"] if d in report_titles)}


def login(client, email):
    r = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    tasks = json.loads((ROOT / "tests" / "research_set.json").read_text())
    rows = []
    with httpx.Client(base_url=args.base_url, timeout=600.0) as client:
        for t in tasks:
            h = login(client, t["user"])
            started = time.perf_counter()
            rep = client.post("/research", headers=h, json={"request": t["request"]})
            took = time.perf_counter() - started
            body = rep.json() if rep.status_code == 200 else {}
            titles = {s["title"] for s in body.get("sources", [])}
            base = client.post("/chat/query", headers=h, json={"query": t["request"]})
            base_titles = {s["title"] for s in base.json().get("sources", [])} if base.status_code == 200 else set()
            row = score_task(t, titles, base_titles)
            row.update(id=t["id"], http=rep.status_code, seconds=round(took), gaps=len(body.get("gaps", [])),
                       findings=len(body.get("sections", [])), summary=bool(body.get("summary")))
            rows.append(row)
            print(f"{t['id']:16} report {row['report_hits']}/{row['expected']}  single question {row['baseline_hits']}/{row['expected']}"
                  f"  leaks {len(row['leaks'])}  {row['seconds']}s  http {rep.status_code}", flush=True)
            if rep.status_code == 200:
                client.delete(f"/research/{body['id']}", headers=h)
    exp = sum(r["expected"] for r in rows)
    rep_hits, base_hits = sum(r["report_hits"] for r in rows), sum(r["baseline_hits"] for r in rows)
    leaks = sum(len(r["leaks"]) for r in rows)
    lines = ["# Research assistant evaluation", "",
             f"{len(rows)} tasks written by the author (not independent). Same model and retrieval for both columns.", "",
             "| Task | Expected documents | Report cites | Single question cites | Leaks | Gaps | Seconds |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['expected']} | {r['report_hits']} | {r['baseline_hits']} | {len(r['leaks'])} | {r['gaps']} | {r['seconds']} |" for r in rows]
    lines += ["", f"**Coverage of expected documents:** report {rep_hits}/{exp}, single question {base_hits}/{exp}.",
              f"**Leaks (forbidden documents cited):** {leaks}.", "",
              "Coverage only counts which documents were cited; it does not judge the quality of the writing."]
    (ROOT / "evaluation" / "RESEARCH_EVAL.md").write_text("\n".join(lines) + "\n")
    print(f"\nCoverage: report {rep_hits}/{exp}, single question {base_hits}/{exp}. Leaks: {leaks}. Wrote evaluation/RESEARCH_EVAL.md")
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
