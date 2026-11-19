-- Creates one contained database user for a service, with only the rights it needs (A2 deployment guide, step 4).
-- Run it against that service's own database. The password comes from a sqlcmd variable, never from this file.
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$(APP_USER)')
    CREATE USER [$(APP_USER)] WITH PASSWORD = '$(APP_PASSWORD)';
ALTER ROLE db_ddladmin ADD MEMBER [$(APP_USER)];
ALTER ROLE db_datareader ADD MEMBER [$(APP_USER)];
ALTER ROLE db_datawriter ADD MEMBER [$(APP_USER)];