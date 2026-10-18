-- Deterministic synthetic customer-support dataset (v1).
-- All dates are fixed. Re-seeding must reproduce this file byte-for-byte
-- in effect: no random values, no CURRENT_TIMESTAMP.

CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  segment     TEXT NOT NULL,  -- SMB | Mid-Market | Enterprise
  region      TEXT NOT NULL,  -- NA West | NA East | EMEA | APAC
  since_date  TEXT NOT NULL   -- ISO date
);

CREATE TABLE agents (
  agent_id TEXT PRIMARY KEY,
  name     TEXT NOT NULL
);

CREATE TABLE support_tickets (
  ticket_id          TEXT PRIMARY KEY,
  customer_id        TEXT NOT NULL REFERENCES customers(customer_id),
  opened_at          TEXT NOT NULL,  -- ISO datetime
  closed_at          TEXT,           -- NULL when open
  priority           TEXT NOT NULL,  -- P1 | P2 | P3 | P4
  status             TEXT NOT NULL,  -- open | closed
  channel            TEXT NOT NULL,  -- email | chat | phone
  agent_id           TEXT REFERENCES agents(agent_id),
  resolution_minutes INTEGER         -- NULL when open
);

CREATE TABLE ticket_messages (
  ticket_id   TEXT NOT NULL REFERENCES support_tickets(ticket_id),
  seq         INTEGER NOT NULL,
  author_role TEXT NOT NULL,  -- customer | agent
  body        TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  PRIMARY KEY (ticket_id, seq)
);

-- Documented business events. The assistant's evidence access includes this
-- table: a causal question may only be rejected for an undocumented event
-- if the event is genuinely absent here. Withholding the causal LINK is a
-- separate matter -- org_events establishes that events happened, never why
-- ticket metrics moved.
CREATE TABLE org_events (
  event_id   TEXT PRIMARY KEY,
  event_date TEXT NOT NULL,  -- ISO date
  category   TEXT NOT NULL,  -- headcount | product | pricing | policy | expansion
  title      TEXT NOT NULL,
  detail     TEXT NOT NULL
);
