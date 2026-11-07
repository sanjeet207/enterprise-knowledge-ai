# Security

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private reporting
(Security tab, "Report a vulnerability") or email sanjeet207@gmail.com. Expect a first reply within a few days.

## How the system protects data

- **Access control is enforced in the database query**, not after retrieval. A document is only a search
  candidate if the user's tenant, level and (for sensitive documents) engagement-team membership allow it.
  `scripts/verify_access.py` checks this for every demo user and document (160 checks) and runs in CI.
- **Tokens carry only the user id.** Level, tenant, active flag and engagement membership are read from the
  database on every request, so a role change or deactivation takes effect immediately.
- **Passwords** are stored as bcrypt hashes. `JWT_SECRET` must be set in the environment; `scripts/quickstart.sh`
  generates a random one.
- **Prompt injection:** document text and questions are treated as data. A plain-code guard blocks override
  attempts before any model sees the question, answers must cite a permitted document, and a validator checks
  every claim.
- **Refusals look identical** whether a document is forbidden or does not exist, so refusals reveal nothing.
- **Audit:** every question is logged with its outcome and trace. Only Partners (level 4) can read the log.
- **Publishing is separated from reading.** Only administrators publish company-wide documents, and engagement managers only to their own team. An administrator manages documents and people without gaining access to restricted content. All of it is tenant-scoped, and every upload, delete and account change is logged. Uploads by non-administrators stay unsearchable until an administrator approves them. Five wrong passwords lock an account for 15 minutes, and the response is identical to a wrong password. Uploads are limited by type and size, checked by content, de-duplicated and cleaned up if indexing fails.
- **Conversations are private and context is limited.** A conversation is visible only to its owner. Follow-up rewriting uses the person's own earlier questions only, never earlier answers, and the rewritten question goes through all normal checks. Saved answers are what the person was allowed to see at the time; they stay in the owner's history until deleted.
- **Privacy rights and retention.** People can download their data and erase it (password required): conversations are deleted and the audit log keeps only counts, not their words. Old audit rows and conversations are purged after the retention period. Logs carry request ids and timings, never names, emails or questions. `/metrics` is disabled unless a token is configured.
- **Single sign-on** (optional): authorization code flow with PKCE, state and nonce; ID tokens are verified (RS256 signature, issuer, audience, expiry, nonce). Only accounts an administrator created can sign in, and the first sign-in binds the account to the provider's stable subject id. Not yet tested against a live provider; no group mapping yet.
- **General-knowledge answers** never use company documents, carry no sources, and are labelled in the UI.

## Known limits

- This is a portfolio project with fictional demo data and demo passwords. Do not deploy it with the demo
  accounts or the default seed data.
- Question limit is in memory (one process); behind several instances it moves to Redis. Sign-in lockout is per account, not per address. Administrators reset passwords; there is no self-service reset.
- Administrators publish without a second approver. Scanned PDFs are not read (no OCR).
- Answers come from a local 7B model; the validator is a model check, not a proof.
