"""Model outage drill: what the running application does when the language model cannot be reached.

Start the server with a model address that nothing listens on, then run this against it:

    OLLAMA_URL=http://127.0.0.1:9 WARM_UP_MODELS=false uvicorn app.main:app --port 8001
    python -m scripts.outage_drill --base-url http://127.0.0.1:8001

It needs the demo accounts (python -m scripts.seed_demo) and uses no model and no network. Expected behaviour: the
service stays healthy, search (which needs no model) still works and still hides restricted documents, a question gets a
plain 503 within seconds with no internal details, and the server keeps answering afterwards.
"""
import argparse
import json
import sys
import time

import httpx

PASSWORD = "DemoPass2026x"  # local demo data only
INTERNAL_WORDS = ("traceback", "httpx", "connecterror", "127.0.0.1:9", "ollama", "groq", "api key", "exception")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    results = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append(ok)
        print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))

    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        record("The service reports healthy", client.get("/health").status_code == 200)

        r = client.post("/auth/login", data={"username": "analyst@acme.test", "password": PASSWORD})
        record("Sign-in works without a model", r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print("Run python -m scripts.seed_demo first.")
            return 1
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = client.post("/retrieval/search", json={"query": "annual leave carry forward"}, headers=headers)
        found = r.json().get("matches_found", 0) if r.status_code == 200 else 0
        record("Search still works and finds documents", r.status_code == 200 and found > 0, f"{r.status_code}, {found} matches")

        r = client.post("/retrieval/search", json={"query": "Project Titan acquisition valuation"}, headers=headers)
        passages = json.dumps(r.json().get("retrieved_passages", [])).lower() if r.status_code == 200 else ""
        record("Search still hides restricted documents from an analyst",
               r.status_code == 200 and "1.2 billion" not in passages and "valuation memo" not in passages, str(r.status_code))

        started = time.time()
        r = client.post("/chat/query", json={"query": "How many days of annual leave do employees get?"}, headers=headers)
        took = time.time() - started
        record("A question gets a plain 503, not a crash", r.status_code == 503, str(r.status_code))
        record("...within 15 seconds", took < 15, f"{took:.1f}s")
        body = r.text.lower()
        record("...and the message exposes nothing internal", not any(w in body for w in INTERNAL_WORDS), r.text[:120])

        # A question no readable document matches is refused at the relevance gate before any model is called, so
        # 200 with a refusal is also correct. What must never happen is an answer without a model.
        r = client.post("/chat/query", json={"query": "What is the CEO's bonus?"}, headers=headers)
        outcome = r.json().get("outcome") if r.status_code == 200 else None
        record("A second question is a 503 or a plain refusal, never an answer",
               r.status_code == 503 or outcome in ("refused", "no_answer"), f"{r.status_code} {outcome or ''}".strip())
        record("The service is still healthy afterwards", client.get("/health").status_code == 200)

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
