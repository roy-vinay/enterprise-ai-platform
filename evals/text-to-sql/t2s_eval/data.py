"""Synthetic B2B SaaS warehouse in DuckDB.

Everything here is invented. The generator is seeded, so every run of the
eval sees exactly the same data and results are reproducible.

Tables
  accounts         one row per customer account (some are internal test accounts)
  subscriptions    one subscription per account, with cancellation details
  mrr_monthly      month-end MRR snapshot per account
  invoices         monthly invoices, with soft deletes
  usage_monthly    product usage per account per month
  support_tickets  tickets with priority and optional CSAT
  contacts         people at each customer account; names, emails and phones are
                   personal data that analysts may not read (see access_policy)
  events           ~2M product events, stored in time order so a time filter can
                   skip most of the table (the cost checks measure exactly that)

contacts and events are generated from their own random streams after the
original six tables, so adding them did not change a single existing row.
"""
from __future__ import annotations

import csv
import random
import tempfile
from datetime import date, timedelta
from pathlib import Path

import duckdb

SEED = 20261001
START = date(2024, 1, 1)
END = date(2026, 9, 30)  # last day of data; the eval's "today" is 2026-10-01

SEGMENTS = [("SMB", 0.60), ("MidMarket", 0.30), ("Enterprise", 0.10)]
REGIONS = [("NA", 0.45), ("EMEA", 0.30), ("APAC", 0.17), ("LATAM", 0.08)]
INDUSTRIES = ["fintech", "healthcare", "retail", "manufacturing", "media", "education"]
PLANS = {"Starter": 0.5, "Growth": 0.35, "Scale": 0.15}
BASE_MRR = {"Starter": 300, "Growth": 1500, "Scale": 6000}
SEGMENT_MULT = {"SMB": 1.0, "MidMarket": 2.2, "Enterprise": 6.0}
CANCEL_REASONS = [
    ("price", 0.30),
    ("missing_feature", 0.25),
    ("switched_competitor", 0.20),
    ("budget_cut", 0.15),
    ("company_closed", 0.05),
    ("other", 0.05),
]

DDL = """
CREATE TABLE accounts (
  account_id INTEGER PRIMARY KEY, name VARCHAR, segment VARCHAR, region VARCHAR,
  industry VARCHAR, created_at DATE, is_test BOOLEAN);
CREATE TABLE subscriptions (
  subscription_id INTEGER PRIMARY KEY, account_id INTEGER, plan VARCHAR,
  status VARCHAR, start_date DATE, end_date DATE,
  canceled_by VARCHAR, cancel_reason VARCHAR);
CREATE TABLE mrr_monthly (
  month DATE, account_id INTEGER, plan VARCHAR, mrr_usd DOUBLE);
CREATE TABLE invoices (
  invoice_id INTEGER PRIMARY KEY, account_id INTEGER, invoice_date DATE,
  amount_usd DOUBLE, status VARCHAR, is_deleted BOOLEAN);
CREATE TABLE usage_monthly (
  month DATE, account_id INTEGER, active_users INTEGER, api_calls BIGINT);
CREATE TABLE support_tickets (
  ticket_id INTEGER PRIMARY KEY, account_id INTEGER, created_at DATE,
  priority VARCHAR, csat_score INTEGER);
CREATE TABLE contacts (
  contact_id INTEGER PRIMARY KEY, account_id INTEGER, full_name VARCHAR,
  email VARCHAR, phone VARCHAR, role VARCHAR);
CREATE TABLE events (
  event_id BIGINT, account_id INTEGER, event_time TIMESTAMP, event_type VARCHAR);
"""

FIRST_NAMES = ["Ada", "Ben", "Chloe", "Dev", "Elena", "Femi", "Grace", "Hiro", "Isla", "Jon",
               "Kavya", "Liam", "Maya", "Noor", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tara"]
LAST_NAMES = ["Abara", "Brandt", "Costa", "Dube", "Evans", "Fischer", "Garcia", "Hughes",
              "Ito", "Jensen", "Kim", "Lopez", "Mehta", "Novak", "Okafor", "Park"]
CONTACT_ROLES = [("admin", 0.30), ("billing", 0.25), ("champion", 0.20), ("user", 0.25)]
# Weighted by repetition (40% login, 30% report_viewed, 10% each of the rest), so
# "most common" has a single right answer.
EVENT_TYPES = ["login"] * 4 + ["report_viewed"] * 3 + ["export", "invite_sent", "api_key_created"]
N_EVENTS = 2_000_000
# Spread events evenly from START through END: 1004 days / 2M events ~ 43.37 s apart.
EVENT_STEP_MS = 43_372


def _pick(rng: random.Random, weighted):
    r, acc = rng.random(), 0.0
    for value, w in weighted:
        acc += w
        if r <= acc:
            return value
    return weighted[-1][0]


def _month_starts(a: date, b: date):
    d = date(a.year, a.month, 1)
    while d <= b:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def build(path: str | Path, n_accounts: int = 600) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rng = random.Random(SEED)
    con = duckdb.connect(str(path))
    con.execute(DDL)

    accounts, subs, mrr, invoices, usage, tickets = [], [], [], [], [], []
    inv_id = ticket_id = 1
    span = (END - START).days

    for aid in range(1, n_accounts + 1):
        segment = _pick(rng, SEGMENTS)
        created = START + timedelta(days=int(span * rng.random() ** 1.3))
        is_test = rng.random() < 0.03
        accounts.append((aid, f"Account {aid:04d}", segment, _pick(rng, REGIONS),
                         rng.choice(INDUSTRIES), created, is_test))

        plan = _pick(rng, list(PLANS.items()))
        base = BASE_MRR[plan] * SEGMENT_MULT[segment] * rng.uniform(0.8, 1.2)

        # Cancellation: monthly hazard, higher for SMB.
        hazard = {"SMB": 0.025, "MidMarket": 0.015, "Enterprise": 0.008}[segment]
        end_date = canceled_by = reason = None
        status = "active"
        for m in _month_starts(created, END):
            if m > date(created.year, created.month, 1) and rng.random() < hazard:
                end_date = min(m + timedelta(days=rng.randint(0, 27)), END)
                status = "canceled"
                if rng.random() < 0.75:
                    canceled_by, reason = "customer", _pick(rng, CANCEL_REASONS)
                else:
                    canceled_by, reason = "system_nonpayment", None
                break
        if status == "active" and rng.random() < 0.02:
            status = "paused"
        subs.append((aid, aid, plan, status, created, end_date, canceled_by, reason))

        last = end_date or END
        level = base
        for m in _month_starts(created, last):
            level *= rng.uniform(0.99, 1.03)  # mild expansion over time
            amount = round(level, 2)
            mrr.append((m, aid, plan, amount))
            inv_status = _pick(rng, [("paid", 0.92), ("open", 0.04),
                                     ("void", 0.02), ("refunded", 0.02)])
            if m + timedelta(days=27) > END:
                inv_status = "open" if inv_status == "paid" and rng.random() < 0.5 else inv_status
            invoices.append((inv_id, aid, m, amount, inv_status, rng.random() < 0.01))
            inv_id += 1
            seats = max(1, int(rng.gauss(SEGMENT_MULT[segment] * 12, 4)))
            usage.append((m, aid, seats, int(seats * rng.uniform(800, 2500))))
            for _ in range(rng.choices([0, 1, 2, 3], [0.55, 0.28, 0.12, 0.05])[0]):
                d = m + timedelta(days=rng.randint(0, 27))
                if d > END:
                    continue
                pr = _pick(rng, [("low", 0.35), ("normal", 0.40), ("high", 0.18), ("urgent", 0.07)])
                csat = None if rng.random() < 0.4 else rng.choices([1, 2, 3, 4, 5], [5, 8, 17, 35, 35])[0]
                tickets.append((ticket_id, aid, d, pr, csat))
                ticket_id += 1

    # Bulk load through CSV: much faster than row-by-row inserts.
    with tempfile.TemporaryDirectory() as tmp:
        for table, rows in [("accounts", accounts), ("subscriptions", subs),
                            ("mrr_monthly", mrr), ("invoices", invoices),
                            ("usage_monthly", usage), ("support_tickets", tickets)]:
            f = Path(tmp) / f"{table}.csv"
            with f.open("w", newline="") as fh:
                csv.writer(fh).writerows(["" if v is None else v for v in r] for r in rows)
            con.execute(f"COPY {table} FROM '{f}' (HEADER false, NULLSTR '')")
    _add_contacts(con, n_accounts)
    _add_events(con, n_accounts)
    con.close()
    return path


def _add_contacts(con, n_accounts: int) -> None:
    """One to four contacts per account. Fictional names, example.com-style
    domains and 555 phone numbers: nothing here belongs to a real person."""
    rng = random.Random(SEED + 1)
    rows, cid = [], 1
    for aid in range(1, n_accounts + 1):
        for _ in range(rng.choices([1, 2, 3, 4], [0.35, 0.35, 0.2, 0.1])[0]):
            first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            rows.append((cid, aid, f"{first} {last}",
                         f"{first.lower()}.{last.lower()}@account-{aid:04d}.example",
                         f"+1-555-01{rng.randint(0, 99):02d}", _pick(rng, CONTACT_ROLES)))
            cid += 1
    con.executemany("INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?)", rows)


def _add_events(con, n_accounts: int) -> None:
    """Product events, generated in SQL and inserted in time order.

    Time order matters: DuckDB keeps min/max per row group, so a filter on
    event_time skips most of the table, the same way a partitioned warehouse
    prunes partitions. A filter that wraps the column in a function (strftime,
    CAST) cannot use that and reads every row. The answers are identical; the
    cost is not.
    """
    types = ", ".join(f"'{t}'" for t in EVENT_TYPES)
    con.execute(f"""
        INSERT INTO events
        SELECT i,
               ((i * 104729) % {n_accounts}) + 1,
               TIMESTAMP '{START.isoformat()}' + INTERVAL ({EVENT_STEP_MS} * i) MILLISECOND,
               [{types}][((i * 7919) % {len(EVENT_TYPES)}) + 1]
        FROM range({N_EVENTS}) t(i)
        ORDER BY i""")


def schema_ddl() -> str:
    return DDL.strip()


if __name__ == "__main__":
    p = build(Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb")
    print(f"built {p}")
