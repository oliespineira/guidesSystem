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