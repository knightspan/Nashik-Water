"""Management commands.

    python -m app.cli bootstrap                       # seed admin + first API key (idempotent)
    python -m app.cli set-password admin@x.org        # reads the new password from stdin
    python -m app.cli retention [--full]              # hourly roll-up + prune old raw readings
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.bootstrap import bootstrap
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User


def _bootstrap() -> int:
    with SessionLocal() as db:
        done = bootstrap(db, get_settings())
    print("bootstrap:", "; ".join(done) if done else "nothing to do")
    return 0


def _set_password(email: str) -> int:
    password = getpass.getpass("New password: ") if sys.stdin.isatty() else sys.stdin.readline()
    password = password.rstrip("\n")
    if len(password) < 12:
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            print(f"No user {email}", file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        db.commit()
    print(f"Password updated for {email}")
    return 0


def _retention(full: bool) -> int:
    from app.retention import run_retention

    with SessionLocal() as db:
        res = run_retention(db, full=full)
    print(
        "retention:",
        (
            "skipped (another run in progress)"
            if res.skipped
            else f"{res.hours_upserted} hourly rows upserted, "
            f"{res.readings_deleted} raw readings deleted"
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging(get_settings().log_level)
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap", help="create admin user and first ingest key from env vars")
    sp = sub.add_parser("set-password", help="reset a user's password")
    sp.add_argument("email")
    rp = sub.add_parser("retention", help="roll up hourly aggregates and prune old readings")
    rp.add_argument("--full", action="store_true", help="re-aggregate all history")
    args = parser.parse_args(argv)

    if args.cmd == "bootstrap":
        return _bootstrap()
    if args.cmd == "set-password":
        return _set_password(args.email)
    if args.cmd == "retention":
        return _retention(args.full)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
