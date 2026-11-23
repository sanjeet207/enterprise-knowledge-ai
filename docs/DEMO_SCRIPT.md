# Demo video script (about 4 minutes)

Record on your own screen with your own voice. Run it locally on the Ollama model (the hosted model is rate-limited and can
change between runs). Before recording: `bash scripts/quickstart.sh` passes, `python -m scripts.seed_demo` has been run, the
server is at http://127.0.0.1:8000, and you have rehearsed each question once so you know how long the model takes (about 10 to
15 seconds per answer; cut the waiting in editing, but say that you did).

Two browser windows help: one normal, one private, so two people can be signed in at once. Password for every account is
`DemoPass2026x`.

## 0:00 Opening (20 s), on the README

Say: "This is an internal company brain. Employees ask questions and get answers only from their own company's documents,
with citations, and only from documents they are allowed to see. Everything in it is fictional data."

Show the top of the README and the architecture diagram.

## 0:20 Same question, two people (60 s)

1. Sign in as `director_titan@acme.test`. Ask: *What is the indicative valuation for Project Titan?*
   Point at the answer, the citation marker and the source list.
2. Sign in as `director@acme.test` (private window). Ask the same question.
   It is refused. Say: "Same clearance level, but this person is not on the deal team. The refusal text is identical to any
   other refusal, so it does not even reveal that the document exists."

Say: "The reason is where the rule lives. Access is a condition of the SQL query. The model only receives passages this person
may read, so no prompt can make it leak what it never saw."

## 1:20 Rights change while signed in (40 s)

As admin (`admin@acme.test`), remove `director_titan` from the Titan team (or lower a level). Back in the first window, with the
same session, ask again. It is now refused. Say: "The token carries only the user id. Rights are read from the database on every
request, so this took effect at once. This is checked live in the security matrix."

If this is too fiddly to do live, show `evaluation/SECURITY_MATRIX_RESULTS.md` rows M1, M3 and M4 instead and say that you are
showing a recorded test result.

## 2:00 It says no when it should (30 s)

As `analyst@acme.test` ask *Can you suggest a good biryani recipe?* and *What is the CEO's bonus amount?* Both are refused. Say:
"Questions the documents cannot answer are refused instead of guessed. And an answer that cannot be verified after retries is not
shown at all."

## 2:30 Proof, not claims (60 s), in the terminal

Run `python -m scripts.security_matrix --no-model` (20 checks, quick). Then open `evaluation/` and show one report.

Say, and mean it: "Here is what is measured: 160 access checks, a live security matrix, 57 attacks, and four question sets.
Every question set was written by me or by the AI assistant that helped build this, so none of them is independent. On the
messier Northwind company it answers 78 percent of answerable questions correctly, and I have kept the failures listed. It has
not leaked a document in any run."

## 3:30 Closing (30 s)

Say: "What is not done: it is not deployed to Azure yet, single sign-on has not been tried against a live tenant, and nobody
outside the project has reviewed it. Those are the next steps. The code, the tests and the reports are all in the repository."

Show the README title and the repository address.

## Do not

- Do not say "production-ready", "validated" or "independently tested".
- Do not show the `.env` file, the Groq page or any key.
- Do not claim the hosted-model result is stable; it was 7/12, 10/12 and 12/12 on a 12-question set.
- Do not read numbers from memory; read them from the report on screen.
