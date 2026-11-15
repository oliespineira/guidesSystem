
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
