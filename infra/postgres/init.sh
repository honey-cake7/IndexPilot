#!/usr/bin/env bash
set -Eeuo pipefail

# Do not enable shell tracing: these variables contain generated credentials.
IP_META_PASSWORD="$(cat /run/indexpilot-secrets/meta_password)"
IP_DEMO_PASSWORD="$(cat /run/indexpilot-secrets/demo_password)"
IP_ANALYZER_PASSWORD="$(cat /run/indexpilot-secrets/analyzer_password)"
IP_BENCH_PASSWORD="$(cat /run/indexpilot-secrets/bench_password)"
export IP_META_PASSWORD IP_DEMO_PASSWORD IP_ANALYZER_PASSWORD IP_BENCH_PASSWORD

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv meta_password IP_META_PASSWORD
\getenv demo_password IP_DEMO_PASSWORD
\getenv analyzer_password IP_ANALYZER_PASSWORD
\getenv bench_password IP_BENCH_PASSWORD
CREATE ROLE indexpilot_meta LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'meta_password';
CREATE ROLE indexpilot_demo_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'demo_password';
CREATE ROLE indexpilot_analyzer LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'analyzer_password';
CREATE ROLE indexpilot_bench_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'bench_password';
CREATE DATABASE indexpilot_meta OWNER indexpilot_meta;
CREATE DATABASE indexpilot_demo OWNER indexpilot_demo_owner;
CREATE DATABASE indexpilot_bench OWNER indexpilot_bench_owner;
REVOKE ALL ON DATABASE indexpilot_meta, indexpilot_demo, indexpilot_bench FROM PUBLIC;
GRANT CONNECT ON DATABASE indexpilot_demo TO indexpilot_analyzer;
GRANT pg_read_all_stats TO indexpilot_analyzer;
ALTER ROLE indexpilot_analyzer SET default_transaction_read_only = on;
ALTER ROLE indexpilot_analyzer SET statement_timeout = '5s';
ALTER ROLE indexpilot_analyzer SET lock_timeout = '1s';
ALTER ROLE indexpilot_analyzer SET search_path = pg_catalog, public;
SQL

for database in indexpilot_meta indexpilot_demo indexpilot_bench; do
  psql --username "$POSTGRES_USER" --dbname "$database" --set ON_ERROR_STOP=1 <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE EXTENSION pg_stat_statements;
SQL
done

psql --username "$POSTGRES_USER" --dbname indexpilot_demo --set ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION hypopg;
GRANT USAGE ON SCHEMA public TO indexpilot_analyzer;
GRANT SELECT ON public.hypopg_list_indexes TO indexpilot_analyzer;
ALTER DEFAULT PRIVILEGES FOR ROLE indexpilot_demo_owner IN SCHEMA public
  GRANT SELECT ON TABLES TO indexpilot_analyzer;
COMMENT ON DATABASE indexpilot_demo IS 'indexpilot:demo:v1';
SQL
psql --username "$POSTGRES_USER" --dbname indexpilot_bench --set ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION hypopg;
COMMENT ON DATABASE indexpilot_bench IS 'indexpilot:disposable-benchmark:v1';
SQL
unset IP_META_PASSWORD IP_DEMO_PASSWORD IP_ANALYZER_PASSWORD IP_BENCH_PASSWORD
