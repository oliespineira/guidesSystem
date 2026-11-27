-- 002_role_key: a role name counts as the same role whatever its capitals or accents,
-- so "Tesorería" and "Tesoreria" can no longer both exist in one ronda (fixes the accent half of review defect 2).
-- role_key is computed from role_name: SQL Server fills it in for every existing row (the backfill),
-- and the previous version of the code keeps working, because it never has to write the new column.
ALTER TABLE roles ADD role_key AS (role_name COLLATE Latin1_General_CI_AI) PERSISTED;
GO
CREATE UNIQUE INDEX ux_roles_ronda_role_key ON roles (ronda_id, role_key);