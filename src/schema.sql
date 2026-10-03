--  Kraal & Rama Management (feature 1)

-- The if not exists are included to make the file safe to run on every startup, satisfying criterion 7 (no interactive setup)

CREATE TABLE IF NOT EXISTS rondas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_label TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed'))
);

CREATE TABLE IF NOT EXISTS volunteers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    joined_date TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id),
    role_name TEXT NOT NULL,
    UNIQUE (ronda_id, role_name)
);

CREATE TABLE IF NOT EXISTS ramas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),
    name TEXT NOT NULL,
    UNIQUE (ronda_id, name)
);

-- ronda_id is deliberately repeated here (denormalized) so the database itself
-- can enforce "a volunteer is in at most one rama per ronda".
CREATE TABLE IF NOT EXISTS rama_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),
    rama_id INTEGER NOT NULL REFERENCES ramas(id),
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id),
    availability_pct INTEGER CHECK (availability_pct BETWEEN 0 AND 100),
    notes TEXT,
    UNIQUE (rama_id, volunteer_id),
    UNIQUE (ronda_id, volunteer_id)
);

-- Meeting & Decision Log (Actas) (feature 2)

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),  -- the seam
    date TEXT NOT NULL,
    title TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agenda_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    section_title TEXT NOT NULL,
    content TEXT,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agenda_item_id INTEGER NOT NULL REFERENCES agenda_items(id),
    description TEXT NOT NULL,
    vote_result TEXT
);

-- assigned_volunteers is free text on purpose: no link into Domain 1's tables.
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),  -- the seam
    start_date TEXT NOT NULL,
    end_date TEXT,
    activity_type TEXT NOT NULL,
    assigned_volunteers TEXT,
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_meetings_ronda ON meetings(ronda_id);
CREATE INDEX IF NOT EXISTS idx_agenda_meeting ON agenda_items(meeting_id);
CREATE INDEX IF NOT EXISTS idx_decisions_agenda ON decisions(agenda_item_id);
CREATE INDEX IF NOT EXISTS idx_events_ronda ON calendar_events(ronda_id);

-- SubDomain 2(Tesorería): budgets, requests and their audit trial

CREATE TABLE IF NOT EXISTS budgets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id), --esto es el seam
    category TEXT NOT NULL,
    allocated_cents INTEGER NOT NULL CHECK (allocated_cents>=0),
    UNIQUE (ronda_id, category)
);

-- rama is free text on purpose, like assigned_volunteers: no link to domain 1.
CREATE TABLE IF NOT EXISTS budget_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    budget_id INTEGER NNOT NULL REFERENCES budgets(id),
    rama TEXT NOT NULL,
    item TEXT NOT NULL,
    item_key TEXT NOT NULL,        -- normalised item, for duplicate detection
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'paid'))
        
);CREATE TABLE IF NOT EXISTS request_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES budget_requests(id),
    action TEXT NOT NULL,
    actor TEXT,
    note TEXT,
    payment_ref TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_requests_budget ON budget_requests(budget_id);
CREATE INDEX IF NOT EXISTS idx_request_events_request ON request_events(request_id);