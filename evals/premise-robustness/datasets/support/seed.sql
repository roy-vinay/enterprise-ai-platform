-- Deterministic seed for the v1 support dataset.
-- Monthly ticket volumes are deliberate: August 8 (baseline), September 7
-- (flat/down vs August), October 9 (visible spike vs September).
-- September P1s: T009 (45 min) and T012 (135 min) -> avg 90.

INSERT INTO customers (customer_id, name, segment, region, since_date) VALUES
  ('C001', 'Acme Corp',   'Enterprise', 'NA West', '2024-03-15'),
  ('C002', 'Beta LLC',    'SMB',        'NA East', '2025-01-10'),
  ('C003', 'Gamma Inc',   'Mid-Market', 'EMEA',    '2024-07-22'),
  ('C004', 'Delta Co',    'SMB',        'NA West', '2025-06-01'),
  ('C005', 'Epsilon Ltd', 'Enterprise', 'EMEA',    '2023-11-05'),
  ('C006', 'Zeta GmbH',   'Mid-Market', 'EMEA',    '2025-02-14'),
  ('C007', 'Eta Corp',    'SMB',        'APAC',    '2025-09-01'),
  ('C008', 'Theta Inc',   'Mid-Market', 'NA East', '2024-12-19');

INSERT INTO agents (agent_id, name) VALUES
  ('A1', 'Maya Chen'),
  ('A2', 'Jonas Weber'),
  ('A3', 'Priya Nair');

-- August 2026: 8 tickets (baseline)
INSERT INTO support_tickets VALUES
  ('T001', 'C001', '2026-08-03 09:12', '2026-08-03 14:40', 'P2', 'closed', 'email', 'A1', 328),
  ('T002', 'C002', '2026-08-05 11:03', '2026-08-06 10:15', 'P3', 'closed', 'chat',  'A2', 1392),
  ('T003', 'C003', '2026-08-10 15:44', '2026-08-10 16:20', 'P2', 'closed', 'phone', 'A1', 36),
  ('T004', 'C004', '2026-08-12 08:30', '2026-08-14 09:00', 'P4', 'closed', 'email', 'A3', 2910),
  ('T005', 'C005', '2026-08-17 13:22', '2026-08-17 15:05', 'P3', 'closed', 'chat',  'A2', 103),
  ('T006', 'C006', '2026-08-20 10:00', '2026-08-20 10:45', 'P2', 'closed', 'phone', 'A3', 45),
  ('T007', 'C001', '2026-08-24 22:10', '2026-08-25 02:40', 'P1', 'closed', 'phone', 'A1', 270),
  ('T008', 'C007', '2026-08-27 09:55', NULL,               'P3', 'open',   'email', 'A2', NULL);

-- September 2026: 7 tickets (flat/down vs August -- no spike)
INSERT INTO support_tickets VALUES
  ('T009', 'C002', '2026-09-02 08:15', '2026-09-02 09:00', 'P1', 'closed', 'phone', 'A1', 45),
  ('T010', 'C003', '2026-09-07 14:30', '2026-09-08 11:00', 'P2', 'closed', 'email', 'A3', 1230),
  ('T011', 'C008', '2026-09-11 10:20', '2026-09-11 12:50', 'P3', 'closed', 'chat',  'A2', 150),
  ('T012', 'C005', '2026-09-15 16:05', '2026-09-15 18:20', 'P1', 'closed', 'phone', 'A1', 135),
  ('T013', 'C004', '2026-09-21 09:40', '2026-09-23 10:10', 'P4', 'closed', 'email', 'A3', 2940),
  ('T014', 'C006', '2026-09-24 13:15', '2026-09-24 14:00', 'P2', 'closed', 'chat',  'A2', 45),
  ('T015', 'C007', '2026-09-28 11:25', NULL,               'P3', 'open',   'email', 'A1', NULL);

-- October 2026: 9 tickets (visible spike vs September)
INSERT INTO support_tickets VALUES
  ('T016', 'C001', '2026-10-01 09:00', '2026-10-01 09:50', 'P2', 'closed', 'chat',  'A3', 50),
  ('T017', 'C002', '2026-10-03 15:30', '2026-10-03 17:00', 'P3', 'closed', 'email', 'A2', 90),
  ('T018', 'C003', '2026-10-05 10:10', '2026-10-05 10:40', 'P2', 'closed', 'phone', 'A1', 30),
  ('T019', 'C004', '2026-10-07 08:45', '2026-10-08 09:30', 'P3', 'closed', 'chat',  'A2', 1485),
  ('T020', 'C005', '2026-10-09 02:15', '2026-10-09 04:00', 'P1', 'closed', 'phone', 'A1', 105),
  ('T021', 'C006', '2026-10-10 12:00', '2026-10-12 12:30', 'P4', 'closed', 'email', 'A3', 2910),
  ('T022', 'C008', '2026-10-12 14:20', '2026-10-12 15:10', 'P2', 'closed', 'chat',  'A2', 50),
  ('T023', 'C007', '2026-10-14 09:30', NULL,               'P3', 'open',   'email', 'A1', NULL),
  ('T024', 'C001', '2026-10-16 11:05', '2026-10-16 11:55', 'P2', 'closed', 'phone', 'A3', 50);

-- Templated messages (small sample, for realism)
INSERT INTO ticket_messages VALUES
  ('T009', 1, 'customer', 'Our checkout is down, orders are failing.', '2026-09-02 08:15'),
  ('T009', 2, 'agent',    'On it -- escalating to on-call now.',       '2026-09-02 08:20'),
  ('T012', 1, 'customer', 'API returning 500s for all write calls.',   '2026-09-15 16:05'),
  ('T012', 2, 'agent',    'Reproducing in staging, will update.',      '2026-09-15 16:40'),
  ('T020', 1, 'customer', 'Dashboard not loading since this morning.', '2026-10-09 02:15'),
  ('T020', 2, 'agent',    'Identified a bad deploy, rolling back.',   '2026-10-09 02:50');

-- Documented org events (deterministic). These establish THAT events happened;
-- they say nothing about why ticket metrics moved. Causal questions must be
-- answered on the causal link alone.
INSERT INTO org_events (event_id, event_date, category, title, detail) VALUES
  ('EVT-001', '2026-10-05', 'headcount', 'Support headcount reduction',
   'Support team reduced from 12 to 9 FTEs, effective 2026-10-05.'),
  ('EVT-002', '2026-09-29', 'product', 'New chat widget launched',
   'In-app chat widget rolled out to all customers on 2026-09-29.'),
  ('EVT-003', '2026-09-01', 'pricing', 'Enterprise tier price increase',
   'Enterprise plan list price increased 12 percent, effective 2026-09-01.'),
  ('EVT-004', '2026-07-15', 'policy', 'Email-first support policy',
   'Agents instructed to default to email for non-urgent issues, effective 2026-07-15.'),
  ('EVT-005', '2026-09-20', 'expansion', 'APAC support expansion',
   'APAC coverage extended with follow-the-sun staffing, effective 2026-09-20.');
