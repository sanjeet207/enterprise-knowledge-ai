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

from scripts.security_probe import login, subject, wait_job

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
    parser.add_argument("--no-model", action="store_true",
                        help="skip rows that need a language model (for CI); uploads must run with INSPECT_UPLOADS=false")
    args = parser.parse_args()
    NO_MODEL = args.no_model
    rows = []

    def record(row_id, label, ok, detail=""):
        rows.append((row_id, label, "PASS" if ok else "FAIL", detail))
        print(f"{'PASS' if ok else 'FAIL'}  {row_id:<4} {label}" + (f"  ({detail})" if detail else ""), flush=True)

    def note(row_id, label, detail):
        rows.append((row_id, label, "NOTE", detail))
        print(f"NOTE  {row_id:<4} {label}  ({detail})", flush=True)

    def skip(row_id, label):
        note(row_id, label, "skipped: needs a language model")

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
            if NO_MODEL:
                saved_id = None
                skip("M1c", "Saved conversation before the level change")
            else:
                saved = c.post("/chat/query", headers=session, json={"query": "How are performance reviews and promotions rated?"})
                saved_id = saved.json().get("conversation_id")
                saved_before = c.get(f"/chat/conversations/{saved_id}", headers=session) if saved_id else None
                record("M1c", "Before: the saved conversation shows the level 2 answer and its source",
                       saved_before is not None and saved_before.status_code == 200 and has(saved_before, PERFREV) and "redacted" not in saved_before.text)
            c.patch(f"/admin/users/{pid}", headers=admin, json={"level": 1})
            if NO_MODEL:
                skip("M1d", "Saved conversation after the level change")
            else:
                saved_after = c.get(f"/chat/conversations/{saved_id}", headers=session) if saved_id else None
                record("M1d", "Level lowered: the saved conversation now hides that answer and its source",
                       saved_after is not None and saved_after.status_code == 200 and not has(saved_after, PERFREV) and "redacted" in saved_after.text)
            after = search(session, q)
            record("M1", "Level lowered mid-session: the SAME token no longer finds it in search", status(after) == 200 and not has(after, PERFREV))
            if NO_MODEL:
                skip("M1b", "Chat answer after the level change")
            else:
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
                if NO_MODEL:
                    conv_id = rep_id = None
                    skip("M5c", "Saved research report before team removal")
                    skip("M5a", "Saved conversation before team removal")
                else:
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
                if NO_MODEL:
                    skip("M4b", "New chat answer after team removal")
                else:
                    again = c.post("/chat/query", headers=director_titan, json={"query": "What is the Project Titan valuation?"}).json()
                    record("M4b", "...nor in a new chat answer", TITAN not in json.dumps(again.get("sources", [])), again.get("outcome", ""))
                if NO_MODEL:
                    skip("M5", "Old conversation after team removal")
                else:
                    old = c.get(f"/chat/conversations/{conv_id}", headers=director_titan) if conv_id else None
                    record("M5", "Old conversation after losing access: restricted answer and source title are hidden",
                           old is not None and old.status_code == 200 and not has(old, TITAN) and "redacted" in old.text,
                           "answer replaced by a notice" if old is not None and "redacted" in old.text else "still readable")
                if NO_MODEL:
                    skip("M5r", "Saved research report after team removal")
                else:
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
            if NO_MODEL:
                skip("M9", "Refused chat answer lists no sources")
            else:
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

            # ---------- M15-M22: document and conversation routes ----------
            print("\n-- Document routes: approval, versions, compare, jobs, duplicates, deletion, conversations --")
            stamp = int(time.time())
            if not titan_team:
                record("M15", "Needs the Project Titan team", False, "seed data missing?")
            else:
                def text_for(tag):
                    return f"Matrix check {tag} {stamp}. " + " ".join(
                        f"The routine {tag}{stamp}x{i} covers records, review dates and filing steps for the quarter." for i in range(8))

                def add_doc(headers, title, text, level, team=""):
                    return c.post("/documents/upload", headers=headers, files={"file": ("m.txt", text.encode(), "text/plain")},
                                  data={"title": title, "classification_level": str(level), "engagement_id": team})

                owner_email = f"owner.{stamp}@acme.test"
                om = c.post("/admin/users", headers=admin, json={"email": owner_email, "password": TEST_PASSWORD, "level": 2})
                owner_id = om.json()["id"]
                restore.append(lambda: c.patch(f"/admin/users/{owner_id}", headers=admin, json={"is_active": False}))
                owner = {"Authorization": "Bearer " + c.post("/auth/login", data={"username": owner_email, "password": TEST_PASSWORD}).json()["access_token"]}
                c.post(f"/admin/teams/{titan_team['id']}/members", headers=admin, json={"user_id": owner_id})
                restore.append(lambda: c.delete(f"/admin/teams/{titan_team['id']}/members/{owner_id}", headers=admin))

                t1, t3 = f"Matrix Owner Doc {stamp}", f"Matrix Company Doc {stamp}"
                text1, text3 = text_for("alpha"), text_for("omega")
                up = add_doc(owner, t1, text1, 2, titan_team["id"])
                doc1, job1 = up.json().get("document_id"), up.json().get("job_id")
                if job1:
                    wait_job(c, owner, job1)
                gone_ids = [doc1]

                # approval: only an administrator, and only while the upload is waiting
                no_approve = [c.post(f"/admin/documents/{doc1}/approve", headers=h).status_code for h in (manager, analyst, owner)]
                yes = c.post(f"/admin/documents/{doc1}/approve", headers=admin)
                record("M15", "Only an administrator approves a pending document (manager, analyst and the uploader get 403)",
                       up.status_code in (200, 202) and no_approve == [403, 403, 403] and yes.status_code == 200, f"{no_approve}, admin {yes.status_code}")

                # versions and compare: found for a team member, 404 for everyone else (same answer as for a missing id)
                nowhere = "00000000-0000-4000-8000-000000000000"
                v = {n: c.get(f"/documents/{doc1}/versions", headers=h).status_code
                     for n, h in (("owner", owner), ("analyst", analyst), ("globex", globex))}
                v["missing"] = c.get(f"/documents/{nowhere}/versions", headers=analyst).status_code
                record("M16", "Version history: visible to the team member, 404 for an outsider, another company, and a missing id alike",
                       v == {"owner": 200, "analyst": 404, "globex": 404, "missing": 404}, str(v))
                body = {"document_a": doc1, "document_b": doc1}
                cp = {n: c.post("/documents/compare", headers=h, json=body).status_code for n, h in (("owner", owner), ("analyst", analyst), ("globex", globex))}
                cp["missing"] = c.post("/documents/compare", headers=analyst, json={"document_a": nowhere, "document_b": nowhere}).status_code
                record("M17", "Compare: works for the team member, 404 for an outsider, another company, and a missing id alike",
                       cp == {"owner": 200, "analyst": 404, "globex": 404, "missing": 404}, str(cp))

                # jobs (only when uploads are indexed in the background)
                if job1:
                    j = {n: c.get(f"/documents/jobs/{job1}", headers=h).status_code for n, h in (("owner", owner), ("admin", admin), ("manager", manager), ("globex", globex))}
                    listed = {n: has(c.get("/documents/jobs", headers=h), job1) for n, h in (("owner", owner), ("manager", manager), ("globex", globex))}
                    record("M18", "Upload jobs: seen by the uploader and an administrator, not by another manager or another company",
                           j == {"owner": 200, "admin": 200, "manager": 404, "globex": 404} and listed == {"owner": True, "manager": False, "globex": False},
                           f"{j} {listed}")
                else:
                    note("M18", "Upload jobs not exercised", "the server indexes uploads inside the request (INGEST_ASYNC=false)")

                # duplicate content must not name a document the uploader cannot read
                up3 = add_doc(admin, t3, text3, 3)
                doc3, job3 = up3.json().get("document_id"), up3.json().get("job_id")
                if job3:
                    wait_job(c, admin, job3)
                gone_ids.append(doc3)
                dup_secret = add_doc(owner, "x", text3, 2, titan_team["id"])
                dup_own = add_doc(owner, "x", text1, 2, titan_team["id"])
                record("M19", "Uploading the same text as a level 3 document refuses it but does not name that document",
                       dup_secret.status_code == 409 and t3 not in dup_secret.text, f"{dup_secret.status_code}")
                record("M19a", "Control: duplicating a document the uploader can read does name it",
                       dup_own.status_code == 409 and t1 in dup_own.text, f"{dup_own.status_code}")

                # deletion follows current access, not ownership
                c.delete(f"/admin/teams/{titan_team['id']}/members/{owner_id}", headers=admin)
                refused = c.delete(f"/documents/{doc1}", headers=owner)
                still = any(d["document_id"] == doc1 for d in c.get("/documents", headers=admin).json()["documents"])
                record("M20", "An uploader removed from the team can no longer delete their own document, and it is still there",
                       refused.status_code == 404 and still, f"{refused.status_code}")
                c.post(f"/admin/teams/{titan_team['id']}/members", headers=admin, json={"user_id": owner_id})
                ok_del = c.delete(f"/documents/{doc1}", headers=owner)
                record("M20a", "Control: while still on the team the uploader can delete their own document", ok_del.status_code == 200, f"{ok_del.status_code}")
                gone_ids.remove(doc1)
                for d in gone_ids:
                    c.delete(f"/documents/{d}", headers=admin)

                # conversations: delete and feedback belong to the owner only
                if NO_MODEL:
                    mconv = None
                    skip("M21", "Conversation delete by another person")
                    skip("M22", "Feedback by another person")
                else:
                    mq = c.post("/chat/query", headers=manager, json={"query": "How many days of annual leave do employees get?"}).json()
                    mconv = mq.get("conversation_id")
                    msgs = c.get(f"/chat/conversations/{mconv}", headers=manager).json().get("messages", []) if mconv else []
                    answer_id = next((m["id"] for m in msgs if m["role"] == "assistant"), None)
                    theirs = c.delete(f"/chat/conversations/{mconv}", headers=analyst) if mconv else None
                    kept = c.get(f"/chat/conversations/{mconv}", headers=manager) if mconv else None
                    record("M21", "Another person cannot delete someone's conversation, and it is still there",
                           theirs is not None and theirs.status_code == 404 and kept is not None and kept.status_code == 200)
                    fb = c.post(f"/chat/messages/{answer_id}/feedback", headers=analyst, json={"rating": -1}) if answer_id else None
                    own_fb = c.post(f"/chat/messages/{answer_id}/feedback", headers=manager, json={"rating": 1}) if answer_id else None
                    record("M22", "Another person cannot rate someone's answer (404); the owner can (control)",
                           fb is not None and fb.status_code == 404 and own_fb is not None and own_fb.status_code == 200)
                if mconv:
                    c.delete(f"/chat/conversations/{mconv}", headers=manager)

            # ---------- M13-M14: research assistant ----------
            print("\n-- Research assistant --")
            if NO_MODEL:
                skip("M13", "Research report citing nothing restricted")
                skip("M13a", "Research control")
                skip("M14", "Research report privacy")
            else:
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
