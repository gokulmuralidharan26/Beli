# beli-sync

Once a month: read credit card statement CSVs, find the restaurants you went to,
resolve them to real places, let you approve/fix/skip each new one, and produce a
checklist to bookmark them in Beli.  Supports Apple Card, Amex, and Chase exports.

## Monthly use

1. Download last month's statement CSVs into `inbox/` (Apple Card: Wallet →
   Card Balance → Export; Amex: Statements & Activity → Download → CSV, choose
   the detailed version so it includes Category and City/State).
2. `./run.sh`
3. For each new restaurant: **Enter** approves (or skips if flagged ⚠ low
   confidence), `f` fixes the name and re-searches, `s` skips, `q` quits and
   keeps your progress.
4. Open `output/beli-checklist-<date>.md` and bookmark each place in the Beli app.

Useful flags: `--dry-run` (preview, saves nothing), `--show-excluded` (what the
filter dropped and why), `--from 2026-05-01 --to 2026-06-30` (only look at that
date range; handy for a first run on a big export).  `.venv/bin/beli-sync restaurants` lists everything in
the database.

## First-time setup

1. `cp .env.example .env`, then add a Google Places API key (Google Cloud
   console → enable **Places API (New)** → Credentials → API key; restrict it to
   that API).  Set `HOME_LOCATION` (e.g. `Austin, TX`); Apple Card exports
   have no city, so this is what stops "Joe's Pizza" resolving to the wrong state.
2. `./run.sh` creates the virtualenv itself (needs Python 3.10+: `brew install python`).
3. Optional monthly reminder: `scripts/install_reminder.sh` (notification at
   10:00 on the 1st; `--uninstall` removes it).

## How it decides

- **Dining filter** (`config/filters.yaml`): if the statement has a category it
  decides (Amex "Restaurant-…", Chase "Food & Drink").  The current Apple Card
  export has **no category column**, so for those charges TST* (Toast) and dining
  words count directly, and everything else is looked up on Google and kept only
  if Google says it's a restaurant/cafe/bar and the match is at least medium
  confidence (so a lookup is made per unique Apple Card merchant).
  Groceries, subscriptions, refunds/payments and bare DoorDash/Uber Eats charges
  are excluded.  Add `include_overrides` to bypass an exclusion.
  Delivery charges that *do* name a restaurant are kept, flagged, and capped at
  medium confidence.
- **Confidence** = name similarity (60%) + Google says it's food/drink (25%) +
  city agrees (15%).  ≥0.85 high, ≥0.65 medium, below that is flagged ⚠.
- **Dedupe**: `data/restaurants.db` (SQLite).  Each transaction is hashed, so
  re-importing the same or an overlapping CSV never double-counts.  Restaurants
  you approved aren't asked about again (new visits are just counted), and a
  bank string you skipped stays skipped.

## Privacy

- Only date, description, amount, category and city are read from each CSV;
  `Account #`, `Card Member`, etc. are never read.
- Every text field is scrubbed of card-number patterns (13–19 digits, 4-4-4-4,
  4-6-5, XXXX1234, "ending 1234") before use.  The DB and output contain no
  account numbers; the original CSVs stay wherever you leave them in `inbox/`
  (delete them when done).
- Secrets live in `.env` (gitignored).  `inbox/`, `data/`, `output/` are also
  gitignored.
- The DB stores Google place names/addresses for dedupe and the checklist, and
  lookups are cached for 30 days.  Fine for personal use; Google's terms limit
  broader caching.

## Swapping the input / output

- Input: implement `TransactionSource.fetch()` (`sources/base.py`) returning
  `Transaction`s; a Plaid source would use Plaid's category as `category`.  Then
  use it in `cli.py` instead of `CsvInboxSource`.
- Output: `sinks/checklist.py`.  Beli has no public API; an auto-bookmark sink is
  not built yet (see below).

## Status / caveats

- Bank CSV layouts are in `sources/banks.py`.  Apple Card (current 5-column
  export), Amex (detailed export) and Chase are verified/handled; an unrecognised
  file errors with its header row only (no data) so a layout can be added.
- Amex cuts merchant names at ~20 characters and glues the city on.  The tool
  uses the `Extended Details` column (read-only, never stored) to complete
  truncated names where it can; the rest are left to the Google match and review.
- Not yet built: auto-adding to Beli through the unofficial
  [beli-api](https://github.com/ProjectBarks/beli-api) SDK (reverse-engineered,
  may break, possible ToS issue).  `BELI_REFRESH_TOKEN` in `.env.example` is
  reserved for it.

## Development

`.venv/bin/pip install -e '.[dev]' && .venv/bin/pytest`
