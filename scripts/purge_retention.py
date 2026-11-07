"""Remove audit rows and conversations older than RETENTION_DAYS. Run it daily (cron, or an Azure scheduled job).

Usage: python -m scripts.purge_retention [--days N]
"""
import argparse

from app import config
from app.services import governance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=config.RETENTION_DAYS)
    args = parser.parse_args()
    if args.days < 30:
        raise SystemExit("Refusing to keep less than 30 days of audit history")
    print(governance.purge_old(args.days))


if __name__ == "__main__":
    main()
