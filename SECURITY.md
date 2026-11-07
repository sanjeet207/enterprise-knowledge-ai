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
- **General-knowledge answers** never use company documents, carry no sources, and are labelled in the UI.

## Known limits

- This is a portfolio project with fictional demo data and demo passwords. Do not deploy it with the demo
  accounts or the default seed data.
- No rate limiting, account lockout or password reset yet.
- Answers come from a local 7B model; the validator is a model check, not a proof.
