-- Management of Kraal and Ramas

--Table for Ronda solar
CREATE TABLE IF NOT EXISTS rondas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_label TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

--Table for Kraal

CREATE TABLE IF NOT EXISTS volunteers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    joined_date TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

--Table for roles

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id),
    role_name TEXT NOT NULL,
    UNIQUE(ronda_id, role_name)
);


-- Table for Ramas (groups of children within a Ronda)

CREATE TABLE IF NOT EXISTS ramas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),
    name TEXT NOT NULL,
    UNIQUE(ronda_id, name)
);
--junction table
CREATE TABLE IF NOT EXISTS rama_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rama_id INTEGER NOT NULL REFERENCES ramas(id),
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id),
    availability_pct INTEGER,
    notes TEXT,
    UNIQUE(rama_id, volunteer_id)
);


--meetings table
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),
    date TEXT NOT NULL,
    title TEXT NOT NULL
);


--agenda items table

CREATE TABLE IF NOT EXISTS agenda_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    section_title TEXT NOT NULL,
    content TEXT,
    position INTEGER NOT NULL DEFAULT 0
);

--decisions

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agenda_item_id INTEGER NOT NULL REFERENCES agenda_items(id),
    description TEXT NOT NULL,
    vote_result TEXT
);


--calendar events table
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id INTEGER NOT NULL REFERENCES rondas(id),
    start_date TEXT NOT NULL,
    end_date TEXT,
    activity_type TEXT NOT NULL,
    assigned_volunteers TEXT
);