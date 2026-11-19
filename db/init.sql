-- Creates the two databases and one login per service.
-- Idempotent: every step checks first, so running it again changes nothing.

IF DB_ID('kraal') IS NULL CREATE DATABASE kraal;
IF DB_ID('actas') IS NULL CREATE DATABASE actas;
GO

IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'kraal_app')
    CREATE LOGIN kraal_app WITH PASSWORD = '$(KRAAL_DB_PASSWORD)';
IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'actas_app')
    CREATE LOGIN actas_app WITH PASSWORD = '$(ACTAS_DB_PASSWORD)';
GO

USE kraal;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'kraal_app')
    CREATE USER kraal_app FOR LOGIN kraal_app;
ALTER ROLE db_ddladmin ADD MEMBER kraal_app;
ALTER ROLE db_datareader ADD MEMBER kraal_app;
ALTER ROLE db_datawriter ADD MEMBER kraal_app;
GO

USE actas;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'actas_app')
    CREATE USER actas_app FOR LOGIN actas_app;
ALTER ROLE db_ddladmin ADD MEMBER actas_app;
ALTER ROLE db_datareader ADD MEMBER actas_app;
ALTER ROLE db_datawriter ADD MEMBER actas_app;
GO



-- Test databases: the test suites empty their tables before every test,
-- so they must never point at the real kraal / actas databases.
IF DB_ID('kraal_test') IS NULL CREATE DATABASE kraal_test;
IF DB_ID('actas_test') IS NULL CREATE DATABASE actas_test;
GO

USE kraal_test;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'kraal_app')
    CREATE USER kraal_app FOR LOGIN kraal_app;
ALTER ROLE db_owner ADD MEMBER kraal_app
ALTER ROLE db_ddladmin ADD MEMBER kraal_app;
ALTER ROLE db_datareader ADD MEMBER kraal_app;
ALTER ROLE db_datawriter ADD MEMBER kraal_app;
GO

USE actas_test;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'actas_app')
    CREATE USER actas_app FOR LOGIN actas_app;
ALTER ROLE db_ddladmin ADD MEMBER actas_app;
ALTER ROLE db_datareader ADD MEMBER actas_app;
ALTER ROLE db_datawriter ADD MEMBER actas_app;
GO