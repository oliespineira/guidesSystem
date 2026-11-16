-- 001_init: Actas's schema, ported from the Assignment 1 SQLite schema.sql.
-- The ronda_id columns are plain ids: rondas live in kraal's database (ADR-7).

CREATE TABLE meetings (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ronda_id INT NOT NULL,              -- a Kraal ronda id: checked over HTTP at write time, no FK
    date NVARCHAR(10) NOT NULL,         -- ISO date, YYYY-MM-DD
    title NVARCHAR(200) NOT NULL
);

CREATE TABLE agenda_items (
    id INT IDENTITY(1,1) PRIMARY KEY,
    meeting_id INT NOT NULL REFERENCES meetings(id),
    section_title NVARCHAR(200) NOT NULL,
    content NVARCHAR(MAX),
    position INT NOT NULL DEFAULT 0
);

CREATE TABLE decisions (
    id INT IDENTITY(1,1) PRIMARY KEY,
    agenda_item_id INT NOT NULL REFERENCES agenda_items(id),
    description NVARCHAR(1000) NOT NULL,
    vote_result NVARCHAR(500)
);

-- assigned_volunteers is free text on purpose: no link into Kraal's tables.
CREATE TABLE calendar_events (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ronda_id INT NOT NULL,              -- a Kraal ronda id: checked over HTTP at write time, no FK
    start_date NVARCHAR(10) NOT NULL,
    end_date NVARCHAR(10),
    activity_type NVARCHAR(100) NOT NULL,
    assigned_volunteers NVARCHAR(1000),
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX idx_meetings_ronda ON meetings(ronda_id);
CREATE INDEX idx_agenda_meeting ON agenda_items(meeting_id);
CREATE INDEX idx_decisions_agenda ON decisions(agenda_item_id);
CREATE INDEX idx_events_ronda ON calendar_events(ronda_id);

-- Tesorería: budgets, requests and their audit trail

CREATE TABLE budgets (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ronda_id INT NOT NULL,              -- a Kraal ronda id: checked over HTTP at write time, no FK
    category NVARCHAR(100) NOT NULL,
    allocated_cents INT NOT NULL CHECK (allocated_cents >= 0),
    UNIQUE (ronda_id, category)
);

-- rama is free text on purpose, like assigned_volunteers: no link to Kraal.
CREATE TABLE budget_requests (
    id INT IDENTITY(1,1) PRIMARY KEY,
    budget_id INT NOT NULL REFERENCES budgets(id),
    rama NVARCHAR(100) NOT NULL,
    item NVARCHAR(200) NOT NULL,
    item_key NVARCHAR(200) NOT NULL,    -- normalised item, for duplicate detection
    amount_cents INT NOT NULL CHECK (amount_cents > 0),
    status NVARCHAR(10) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'paid'))
);

CREATE TABLE request_events (
    id INT IDENTITY(1,1) PRIMARY KEY,
    request_id INT NOT NULL REFERENCES budget_requests(id),
    action NVARCHAR(20) NOT NULL,
    actor NVARCHAR(100),
    note NVARCHAR(1000),
    payment_ref NVARCHAR(100),
    created_at NVARCHAR(19) NOT NULL DEFAULT (CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120))
);

CREATE INDEX idx_requests_budget ON budget_requests(budget_id);
CREATE INDEX idx_request_events_request ON request_events(request_id);

-- Notices: owned by the messaging package inside the actas service
CREATE TABLE notices (
    id INT IDENTITY(1,1) PRIMARY KEY,
    topic NVARCHAR(200) NOT NULL,
    title NVARCHAR(200) NOT NULL,
    body NVARCHAR(MAX),
    created_at NVARCHAR(19) NOT NULL DEFAULT (CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120))
);

-- Votaciones: a vote opened on a decision, and one row per volunteer who voted
CREATE TABLE votings (
    decision_id INT PRIMARY KEY REFERENCES decisions(id),   -- at most one vote per decision
    closes_at NVARCHAR(19) NOT NULL,                         -- ISO datetime, e.g. 2026-10-05T20:00
    [rule] NVARCHAR(50) NOT NULL,                            -- [ ] because RULE is a reserved word in SQL Server
    closed INT NOT NULL DEFAULT 0 CHECK (closed IN (0, 1))
);

CREATE TABLE votes (
    id INT IDENTITY(1,1) PRIMARY KEY,
    decision_id INT NOT NULL REFERENCES votings(decision_id),
    volunteer_id INT NOT NULL,          -- an opaque id checked through the seam, like ronda_id
    choice NVARCHAR(10) NOT NULL CHECK (choice IN ('yes', 'no', 'abstain')),
    cast_at NVARCHAR(19) NOT NULL DEFAULT (CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120)),
    UNIQUE (decision_id, volunteer_id)  -- one vote per person per decision
);

-- Albergues: an outing that needs accommodation booked before a deadline
CREATE TABLE bookings (
    event_id INT PRIMARY KEY REFERENCES calendar_events(id),    -- one booking per outing
    book_by NVARCHAR(10) NOT NULL,                               -- ISO date: deadline to reserve
    status NVARCHAR(10) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'booked')),
    venue NVARCHAR(200),
    request_id INT REFERENCES budget_requests(id),               -- the payment, via tesorería
    last_reminded NVARCHAR(10)                                   -- ISO date, so we remind once a day at most
);