"""Security test matrix: attacks that need a LIVE server and a change of access in the middle of a session.

Usage (server running, demo data seeded):  python -m scripts.security_matrix [--base-url URL] [--report FILE]

scripts/security_probe.py covers tokens, other companies, uploads and planted instructions. This script covers what
that one does not: access that is taken away while a person is signed in, restricted titles leaking through lists and
search, the research assistant, and attempts to widen access. Every row has an id (M1...) used in docs/SECURITY_MATRIX.md.

PASS = the attack failed. FAIL = something got through (exit code 1). NOTE = an observation that is reported, not judged.
It creates one throw-away account and puts every change back (team membership, account switched off) when it finishes.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone

import httpx

from scripts.security_probe import login, subject

TEST_PASSWORD = "Matrix-Pass-2026x"  # throw-away local account only
TITAN = "Project Titan Acquisition Valuation Memo"
PERFREV = "Performance Review and Promotion Process"
COMP = "Executive Compensation Framework"


def has(response, text: str) -> bool:
    body = response.text if hasattr(response, "text") else json.dumps(response)
    return text.lower() in body.lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    rows = []

    def record(row_id, label, ok, detail=""):
        rows.append((row_id, label, "PASS" if ok else "FAIL", detail))
        print(f"{'PASS' if ok else 'FAIL'}  {row_id:<4} {label}" + (f"  ({detail})" if detail else ""), flush=True)

    def note(row_id, label, detail):
        rows.append((row_id, label, "NOTE", detail))
        print(f"NOTE  {row_id:<4} {label}  ({detail})", flush=True)

    restore = []  # things to put back, in reverse order
    with httpx.Client(base_url=args.base_url, timeout=400.0) as c:
        admin = login(c, "admin@acme.test")
        analyst = login(c, "analyst@acme.test")
        manager = login(c, "manager@acme.test")
        director_titan = login(c, "director_titan@acme.test")
        globex = login(c, "globex_partner@globex.test")

        def search(headers, query):
            return c.post("/retrieval/search", headers=headers, json={"query": query, "top_k": 5})

        def status(response):
            return response.status_code

        try:
            # ---------- M1-M3: access taken away while signed in ----------
            print("\n-- Access taken away during a session --")
            email = f"matrix.{int(time.time())}@acme.test"
            made = c.post("/admin/users", headers=admin, json={"email": email, "password": TEST_PASSWORD, "level": 2})
            if made.status_code != 201:
                record("M0", "Create the throw-away level 2 account", False, str(made.status_code))
                raise RuntimeError("cannot continue without the throw-away account")
            pid = made.json()["id"]
            restore.append(lambda: c.patch(f"/admin/users/{pid}", headers=admin, json={"is_active": False}))
            session = {"Authorization": "Bearer " + c.post("/auth/login", data={"username": email, "password": TEST_PASSWORD}).json()["access_token"]}
            q = "performance review promotion rating calibration"
            record("M1a", "Before: a level 2 person finds the level 2 document", has(search(session, q), PERFREV))
            saved = c.post("/chat/query", headers=session, json={"query": "How are performance reviews and promotions rated?"})
            saved_id = saved.json().get("conversation_id")
            saved_before = c.get(f"/chat/conversations/{saved_id}", headers=session) if saved_id else None
            record("M1c", "Before: the saved conversation shows the level 2 answer and its source",
                   saved_before is not None and saved_before.status_code == 200 and has(saved_before, PERFREV) and "redacted" not in saved_before.text)
            c.patch(f"/admin/users/{pid}", headers=admin, json={"level": 1})
            saved_after = c.get(f"/chat/conversations/{saved_id}", headers=session) if saved_id else None
            record("M1d", "Level lowered: the saved conversation now hides that answer and its source",
                   saved_after is not None and saved_after.status_code == 200 and not has(saved_after, PERFREV) and "redacted" in saved_after.text)
            after = search(session, q)
            record("M1", "Level lowered mid-session: the SAME token no longer finds it in search", status(after) == 200 and not has(after, PERFREV))
            chat = c.post("/chat/query", headers=session, json={"query": "How are performance reviews and promotions rated?"})
            record("M1b", "...nor in a chat answer", not has(chat, PERFREV), chat.json().get("outcome", ""))

            # an access request records a wish, it does not widen anything
            req = c.post("/access-requests", headers=session, json={"question": "How are performance reviews rated?", "reason": "I am covering the review cycle for my team."})
            record("M2", "A pending access request does not widen what the person can read",
                   req.status_code == 201 and not has(search(session, q), PERFREV), str(req.status_code))

            c.patch(f"/admin/users/{pid}", headers=admin, json={"is_active": False})
            record("M3", "Account switched off mid-session: the SAME token is refused on the next request",
                   c.get("/auth/me", headers=session).status_code in (401, 403) and status(search(session, q)) in (401, 403))

            # ---------- M4-M5: engagement team membership removed ----------
            print("\n-- Engagement membership removed during a session --")
            teams = c.get("/admin/teams", headers=admin).json()["teams"]
            titan_team = next((t for t in teams if t["name"] == "Project Titan"), None)
            dt_id = subject(director_titan)
            if not titan_team:
                record("M4", "Found the Project Titan team", False, "seed data missing?")
            else:
                tq = "Project Titan valuation"
                record("M4a", "Before: a team member finds the deal memo", has(search(director_titan, tq), TITAN))
                conv = c.post("/chat/query", headers=director_titan, json={"query": "What is the Project Titan valuation?"}).json()
                conv_id = conv.get("conversation_id")
                made = c.post("/research", headers=director_titan, json={"request": "Summarise how the Titan deal is valued."}, timeout=300)
                rep_id = made.json().get("id") if made.status_code == 200 else None
                rep_before = c.get(f"/research/{rep_id}", headers=director_titan) if rep_id else None
                record("M5c", "Before: the team member's saved research report cites the deal memo",
                       rep_before is not None and rep_before.status_code == 200 and has(rep_before, TITAN) and "redacted" not in rep_before.text)
                before = c.get(f"/chat/conversations/{conv_id}", headers=director_titan) if conv_id else None
                record("M5a", "Before: the saved conversation shows the answer and its source to the team member",
                       before is not None and before.status_code == 200 and has(before, TITAN) and "redacted" not in before.text)
                removed = c.delete(f"/admin/teams/{titan_team['id']}/members/{dt_id}", headers=admin)
                restore.append(lambda: c.post(f"/admin/teams/{titan_team['id']}/members", headers=admin, json={"user_id": dt_id}))
                record("M4", "Removed from the team mid-session: the SAME token no longer finds the memo",
                       removed.status_code == 200 and not has(search(director_titan, tq), TITAN))
                again = c.post("/chat/query", headers=director_titan, json={"query": "What is the Project Titan valuation?"}).json()
                record("M4b", "...nor in a new chat answer", TITAN not in json.dumps(again.get("sources", [])), again.get("outcome", ""))
                old = c.get(f"/chat/conversations/{conv_id}", headers=director_titan) if conv_id else None
                record("M5", "Old conversation after losing access: restricted answer and source title are hidden",
                       old is not None and old.status_code == 200 and not has(old, TITAN) and "redacted" in old.text,
                       "answer replaced by a notice" if old is not None and "redacted" in old.text else "still readable")
                rep_after = c.get(f"/research/{rep_id}", headers=director_titan) if rep_id else None
                record("M5r", "Saved research report after losing access: restricted findings, summary and source title are hidden",
                       rep_after is not None and rep_after.status_code == 200 and not has(rep_after, TITAN) and "redacted" in rep_after.text)
                if rep_id:
                    c.delete(f"/research/{rep_id}", headers=director_titan)
                if conv_id:
                    c.delete(f"/chat/conversations/{conv_id}", headers=director_titan)

            # ---------- M6-M8: titles and metadata ----------
            print("\n-- Restricted titles and metadata --")
            record("M6", "An analyst gets no document list at all", c.get("/documents", headers=analyst).status_code == 403)
            listing = c.get("/documents", headers=manager)
            record("M7", "A manager's document list holds only their own uploads, no restricted titles",
                   listing.status_code == 200 and not has(listing, TITAN) and not has(listing, COMP))
            hits = search(analyst, "Project Titan valuation and executive compensation")
            record("M8", "Search for restricted topics returns no restricted title or text to an analyst",
                   hits.status_code == 200 and not has(hits, TITAN) and not has(hits, COMP))
            refused = c.post("/chat/query", headers=analyst, json={"query": "What is the Project Titan valuation?"}).json()
            record("M9", "A refused answer lists no sources and names no restricted document",
                   not refused.get("sources") and TITAN not in json.dumps(refused), refused.get("outcome", ""))

            # ---------- M10-M12: widening access ----------
            print("\n-- Attempts to widen access --")
            docs = c.get("/documents", headers=admin).json()["documents"]
            titan_doc = next((d for d in docs if d["title"] == TITAN), None)
            if titan_doc:
                gone = c.delete(f"/documents/{titan_doc['document_id']}", headers=manager)
                still = any(d["title"] == TITAN for d in c.get("/documents", headers=admin).json()["documents"])
                record("M10", "A manager cannot delete a restricted document, and it is still there afterwards", gone.status_code == 404 and still)
            else:
                record("M10", "Found the restricted demo document", False, "seed data missing?")
            record("M11", "A manager cannot raise their own level", c.patch(f"/admin/users/{subject(manager)}", headers=manager, json={"level": 4}).status_code == 403)
            record("M12", "A manager cannot create teams, add members or read the audit log",
                   c.post("/admin/teams", headers=manager, json={"name": "x"}).status_code == 403
                   and c.get("/audit/export.csv", headers=manager).status_code == 403)

            # ---------- M13-M14: research assistant ----------
            print("\n-- Research assistant --")
            rr = c.post("/research", headers=analyst, json={"request": "Summarise the Project Titan deal valuation and what executives are paid."})
            if rr.status_code == 200:
                report = rr.json()
                # The report repeats the request, so judge what it CITES, never the words the person typed.
                cited = json.dumps(report.get("sources", [])) + json.dumps([s.get("sources", []) for s in report.get("sections", [])])
                body = json.dumps({"summary": report.get("summary"), "sections": [s.get("answer") for s in report.get("sections", [])]})
                record("M13", "A research report by an analyst cites no restricted document",
                       TITAN not in cited and COMP not in cited and TITAN not in body and COMP not in body,
                       f"{len(report.get('sources', []))} sources cited")
                ctrl = c.post("/research", headers=analyst, json={"request": "Summarise the annual leave rules and the travel reimbursement rules for employees."})
                if ctrl.status_code == 200:
                    n = len(ctrl.json().get("sources", []))
                    record("M13a", "Control: on an allowed topic the same assistant does cite documents (so M13 is not passing by citing nothing)", n > 0, f"{n} sources cited")
                    c.delete(f"/research/{ctrl.json().get('id')}", headers=analyst)
                else:
                    record("M13a", "Control: on an allowed topic the same assistant does cite documents", False, f"status {ctrl.status_code}")
                rid = rr.json().get("id")
                record("M14", "Another person cannot read that report, nor another company",
                       c.get(f"/research/{rid}", headers=manager).status_code == 404 and c.get(f"/research/{rid}", headers=globex).status_code == 404)
                c.delete(f"/research/{rid}", headers=analyst)
            else:
                record("M13", "A research report by an analyst cites no restricted document", rr.status_code in (422, 503), f"refused with {rr.status_code}")
        except Exception as exc:  # report what we have, then put things back
            record("ERR", "The run stopped early", False, f"{exc.__class__.__name__}: {exc}")
        finally:
            for undo in reversed(restore):
                try:
                    undo()
                except Exception:
                    pass

    failed = [r for r in rows if r[2] == "FAIL"]
    passed = sum(1 for r in rows if r[2] == "PASS")
    print(f"\n{passed}/{passed + len(failed)} attacks defended")
    for row_id, label, _, detail in failed:
        print(f"  GOT THROUGH: {row_id} {label} {detail}")
    if args.report:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"# Security matrix: latest live run ({stamp})", "", "| Row | Attack | Result | Detail |", "|---|---|---|---|"]
        lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in rows]
        with open(args.report, "w") as f:
            f.write("\n".join(lines) + "\n")
        print("Report:", args.report)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
