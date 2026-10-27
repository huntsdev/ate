"""Synthetic probe in a dedicated database; never changes application tables."""

import argparse
import re

import psycopg
from psycopg import sql

from sentinelforge.core.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify", "cleanup"])
    parser.add_argument("token")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{32}", args.token):
        parser.error("token must be a lowercase UUID hex string")
    name = f"ate_phase0_probe_{args.token}"
    settings = get_settings()
    url = settings.database_url.set(drivername="postgresql")
    try:
        with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as admin:
            if args.action == "cleanup":
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {};").format(sql.Identifier(name)))
                print("Synthetic persistence database cleaned up.")
                return
            if args.action == "prepare":
                admin.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(name)))
        probe_url = url.set(database=name).render_as_string(hide_password=False)
        with psycopg.connect(probe_url) as connection:
            if args.action == "prepare":
                connection.execute("CREATE TABLE foundation_probe (token text PRIMARY KEY)")
                connection.execute("INSERT INTO foundation_probe VALUES (%s)", (args.token,))
            else:
                row = connection.execute("SELECT token FROM foundation_probe").fetchone()
                assert row and row[0] == args.token
        print(f"Synthetic persistence probe {args.action}: passed.")
    except Exception as exc:
        raise SystemExit(f"Persistence probe failed: {type(exc).__name__}") from None


if __name__ == "__main__":
    main()
