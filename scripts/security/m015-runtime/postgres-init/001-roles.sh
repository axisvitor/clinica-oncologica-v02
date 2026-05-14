#!/usr/bin/env bash
set -Eeuo pipefail

# Synthetic M015 role bootstrap for the isolated Postgres service.
# Creates the application owner role and a separate login role that can be
# granted table privileges by later DB-proof tasks but intentionally receives no
# RLS policy membership here.

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${M015_APP_DB_PASSWORD:?M015_APP_DB_PASSWORD is required}"
: "${M015_RLS_DENIED_PASSWORD:?M015_RLS_DENIED_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v app_password="$M015_APP_DB_PASSWORD" \
  -v denied_password="$M015_RLS_DENIED_PASSWORD" \
  -v db_name="$POSTGRES_DB" <<'EOSQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hormonia_app') THEN
    CREATE ROLE hormonia_app
      LOGIN
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      INHERIT;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'm015_rls_denied') THEN
    CREATE ROLE m015_rls_denied
      LOGIN
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      INHERIT;
  END IF;
END
$$;

ALTER ROLE hormonia_app PASSWORD :'app_password';
ALTER ROLE m015_rls_denied PASSWORD :'denied_password';

ALTER DATABASE :"db_name" OWNER TO hormonia_app;
GRANT CONNECT, TEMPORARY ON DATABASE :"db_name" TO hormonia_app;
GRANT CONNECT, TEMPORARY ON DATABASE :"db_name" TO m015_rls_denied;

ALTER SCHEMA public OWNER TO hormonia_app;
GRANT USAGE, CREATE ON SCHEMA public TO hormonia_app;
GRANT USAGE ON SCHEMA public TO m015_rls_denied;

ALTER DEFAULT PRIVILEGES FOR ROLE hormonia_app IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO m015_rls_denied;
ALTER DEFAULT PRIVILEGES FOR ROLE hormonia_app IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO m015_rls_denied;
EOSQL
