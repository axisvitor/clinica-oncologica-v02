# S01 Replan

**Milestone:** M015
**Slice:** S01
**Blocker Task:** T03
**Created:** 2026-05-14T05:30:20.573Z

## Blocker Description

T03 implemented the DB seam probe and supporting redaction/Compose wiring, but full runtime verification `./scripts/security/verify-m015-runtime-security.sh --seam db` now reaches the migrations phase and fails with `failure_class=migration_failure` because psycopg/Alembic receives an invalid connection option `sslminversion`. The DB seam cannot produce evidence artifacts or pass the closure gate until migration-time TLS URL option handling is corrected.

## What Changed

Completed tasks T01-T03 are preserved unchanged. The remaining work is split into a blocker-focused fix task and a closure task: T04 now fixes Alembic/psycopg TLS DSN option compatibility so migrations, FastAPI, and the probe all use strict TLS without passing asyncpg-only options to psycopg; new T05 then restores the original harness contract/redaction regression coverage and runs the full S01 closure gate.
