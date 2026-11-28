-- 003_roles_by_volunteer: an index for the membership lookup actas makes over HTTP
-- (treasurer checks, a volunteer's notice topics, voter checks), which finds a volunteer's roles in a ronda.
-- The existing UNIQUE (ronda_id, role_name) index starts with ronda_id, so it cannot find a volunteer's roles directly.
-- An index only adds a lookup structure: no row is changed, and the previous code keeps working.
-- Note: no question marks in migration files. db.py turns them into query placeholders, even inside comments.
CREATE INDEX ix_roles_volunteer_ronda ON roles (volunteer_id, ronda_id);