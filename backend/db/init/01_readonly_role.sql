-- Defense-in-depth: the application connects with this role only.
-- Even if every other security layer fails (AI guardrail, sqlglot validator, statement
-- timeout), PostgreSQL itself refuses to write, drop, or alter anything.
--
-- This runs AFTER 00_chinook.sh, so the SELECT grants cover the loaded Chinook tables.

BEGIN;

CREATE ROLE dbinspector_ro WITH LOGIN PASSWORD 'dbinspector_ro_pw';

GRANT CONNECT ON DATABASE dbinspector TO dbinspector_ro;

-- Read every table/view/sequence in `public` (where Chinook lives).
GRANT USAGE ON SCHEMA public TO dbinspector_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dbinspector_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO dbinspector_ro;

-- Auto-grant SELECT on FUTURE tables (in case the schema evolves).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO dbinspector_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO dbinspector_ro;

-- Belt and braces: revoke anything PostgreSQL might grant by default beyond SELECT.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public FROM dbinspector_ro;
REVOKE CREATE ON SCHEMA public FROM dbinspector_ro;

COMMIT;
