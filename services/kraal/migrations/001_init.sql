-- 001_init: Kraal's schema, ported from the Assignment 1 SQLite schema.sql.

CREATE TABLE rondas (
    id INT IDENTITY(1,1) PRIMARY KEY,
    year_label NVARCHAR(20) NOT NULL UNIQUE,
    start_date NVARCHAR(10) NOT NULL,                -- ISO date text, YYYY-MM-DD (ADR-3)
    status NVARCHAR(10) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed'))
);

CREATE TABLE volunteers (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    joined_date NVARCHAR(10),
    active INT NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE roles (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ronda_id INT NOT NULL REFERENCES rondas(id),
    volunteer_id INT NOT NULL REFERENCES volunteers(id),
    role_name NVARCHAR(100) NOT NULL,
    UNIQUE (ronda_id, role_name)
);

CREATE TABLE ramas (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ronda_id INT NOT NULL REFERENCES rondas(id),
    name NVARCHAR(100) NOT NULL,
    UNIQUE (ronda_id, name)
);

-- ronda_id is deliberately repeated here (denormalized) so the database itself
-- can enforce "a volunteer is in at most one rama per ronda".
CREATE TABLE rama_assignments (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ronda_id INT NOT NULL REFERENCES rondas(id),
    rama_id INT NOT NULL REFERENCES ramas(id),
    volunteer_id INT NOT NULL REFERENCES volunteers(id),
    availability_pct INT CHECK (availability_pct BETWEEN 0 AND 100),
    notes NVARCHAR(1000),
    UNIQUE (rama_id, volunteer_id),
    UNIQUE (ronda_id, volunteer_id)
);