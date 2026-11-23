"""Refuse to start a production deployment that still holds demo accounts.

The demo password is published in the README, so any account created for the demo must never
be reachable on a real deployment by accident. Setting ALLOW_DEMO_DATA=1 makes it a deliberate
choice (for example a public demo that holds only fictional data).
"""
import psycopg

DEMO_DOMAINS = ("acme.test", "northwind.test", "example.test")


class DemoDataInProduction(RuntimeError):
    pass


def demo_accounts(emails: list[str], domains: tuple[str, ...] = DEMO_DOMAINS) -> list[str]:
    found = []
    for email in emails:
        domain = str(email or "").strip().lower().rpartition("@")[2]
        if any(domain == d or domain.endswith("." + d) for d in domains):
            found.append(email)
    return found


def check(app_env: str, allow_demo: bool, emails: list[str]) -> list[str]:
    """Return the demo accounts found; raise when this is production and they are not allowed."""
    found = demo_accounts(emails)
    if found and app_env.strip().lower() == "production" and not allow_demo:
        raise DemoDataInProduction(
            f"{len(found)} demo account(s) exist (for example {found[0]}). Remove them, or set "
            "ALLOW_DEMO_DATA=1 to run a demo deployment on purpose."
        )
    return found


def check_database(database_url: str, app_env: str, allow_demo: bool) -> list[str]:
    if app_env.strip().lower() != "production":
        return []
    with psycopg.connect(database_url) as conn:
        emails = [r[0] for r in conn.execute("SELECT email FROM users").fetchall()]
    return check(app_env, allow_demo, emails)
