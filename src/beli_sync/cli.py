from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .db import Database
from .filtering import FilterConfig
from .pipeline import build_candidates, run_review
from .places import GooglePlacesClient, GooglePlacesError
from .review import Reviewer
from .sinks.checklist import write_checklist
from .sources.csv_inbox import CsvInboxSource, StatementFormatError

ROOT = Path(__file__).resolve().parents[2]


def _cmd_run(args: argparse.Namespace) -> int:
    load_dotenv(ROOT / ".env")
    inbox = Path(args.inbox or ROOT / "inbox")
    source = CsvInboxSource(inbox)
    files = source.files()
    if not files:
        print(f"No CSV files in {inbox}. Drop your statement exports there first.")
        return 1

    db = Database(ROOT / "data" / "restaurants.db")
    try:
        places = GooglePlacesClient(os.environ.get("GOOGLE_PLACES_API_KEY", ""), cache=db)
        cfg = FilterConfig.load(ROOT / "config" / "filters.yaml")
        print(f"Reading {len(files)} statement file(s) from {inbox} ...")
        result = build_candidates(source, db, places, cfg, os.environ.get("HOME_LOCATION", ""),
                                  record_known=not args.dry_run, since=args.since, until=args.until)
    except (GooglePlacesError, StatementFormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    s = result.stats
    print(f"{s['transactions']} transactions: {s['outside date range']} outside date range, "
          f"{s['already processed']} already processed, {s['not dining']} not dining by name/category, "
          f"{s['not dining (place lookup)']} not restaurants per Google, {s['skipped before']} skipped before, "
          f"{s['visits at known restaurants']} visits at restaurants you already have. "
          f"({s['merchants looked up']} Google lookups)")
    if args.show_excluded:
        print("\nExcluded (merchant: reason):")
        for (name, reason), n in sorted(Counter(result.excluded).items()):
            print(f"  {name}  x{n}: {reason}")
    print(f"{len(result.candidates)} new restaurant(s) to review.")

    if args.dry_run:
        for c in result.candidates:
            m = f"{c.match.place.name} ({c.match.confidence:.2f} {c.match.level})" if c.match else "NO MATCH"
            print(f"  {c.name:30} -> {m}")
        print("Dry run: nothing saved.")
        return 0
    if not result.candidates:
        return 0

    run_review(db, Reviewer(places), result, date.today())
    path = write_checklist(result.approved, ROOT / "output")
    print(f"\n{s['approved']} approved, {s['skipped']} skipped"
          + (f", {result.unreviewed} left for next run" if result.unreviewed else "") + ".")
    if path:
        print(f"Checklist: {path}")
    return 0


def _cmd_restaurants(_: argparse.Namespace) -> int:
    db = Database(ROOT / "data" / "restaurants.db")
    rows = db.list_restaurants()
    for r in rows:
        print(f"{r['name']:35} {r['status']:9} {r['visit_count']:>2} visits  {r['first_visit'] or ''} .. {r['last_visit'] or ''}")
    print(f"{len(rows)} restaurants")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="beli-sync", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="process the inbox and review new restaurants")
    run.add_argument("--inbox", help="folder of statement CSVs (default: ./inbox)")
    run.add_argument("--from", dest="since", type=date.fromisoformat, metavar="YYYY-MM-DD",
                     help="ignore transactions before this date")
    run.add_argument("--to", dest="until", type=date.fromisoformat, metavar="YYYY-MM-DD",
                     help="ignore transactions after this date")
    run.add_argument("--dry-run", action="store_true", help="show what would be reviewed; save nothing")
    run.add_argument("--show-excluded", action="store_true", help="list filtered-out transactions and why")
    run.set_defaults(func=_cmd_run)
    sub.add_parser("restaurants", help="list everything in the local database").set_defaults(func=_cmd_restaurants)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
