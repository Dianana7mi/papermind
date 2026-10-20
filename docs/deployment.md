# Deployment and operations

## Local CPU development

See README for `uv sync`, Alembic and Next commands. Default development settings use one API process, SQLite, on-disk Qdrant and FastAPI background tasks. Do not start a separate Celery worker against local Qdrant storage: the embedded database has an exclusive process lock.

`PM_PARSER=pypdf` is an explicit text-only fallback if Docling cannot load. It has no layout/table recovery and cannot serve as validation of Docling. `PM_DOCLING_PIPELINE=simple` is another explicitly limited option; standard Docling is the default and was used for the live AWQ smoke.

For host-side PostgreSQL development, use `docker compose -f docker-compose.dev.yml up -d` and set `PM_DATABASE_URL`, `PM_QDRANT_URL` and `PM_REDIS_URL` to the loopback services. Redis/Qdrant/Postgres development ports bind loopback only.

## Production Compose

1. Install a supported Docker Engine and Compose. Use Linux containers.
2. Copy `.env.example` to `.env`. Choose independent random database password and at least 32-character `PM_SECRET_KEY`; update the PostgreSQL URL consistently. URL-encode reserved password characters in the URL.
3. Set model settings; local embeddings/reranking are CPU capable. First startup downloads models. Allow disk/RAM headroom (start with >=8GB RAM for standard Docling/CPU models and profile the actual workload). The Docker image includes PDF and local-model dependencies; API model mode reduces runtime model memory but not the standard parser dependency.
4. Set `SITE_ADDRESS=research.example.org`, point DNS to the host, and allow inbound 80/443. Caddy obtains/renews HTTPS certificates. For loopback testing use `SITE_ADDRESS=http://localhost` (HTTP); `localhost` enables Caddy's local CA, which requires trusting its local certificate.
5. `docker compose config --quiet`, then `docker compose up --build -d`.
6. `docker compose ps`; inspect `migrate`, `api`, `worker`, `scheduler`, `frontend`, PostgreSQL and Redis logs. The migrate container must exit 0. API readiness checks SQL/Redis/Qdrant; worker health checks Celery ping. Ready does not imply model assets are warmed.
7. Register two accounts. Upload a public PDF, wait for ready, retrieve using four modes, inspect records, compare, open PDF citations, revise a record and delete the test paper. Confirm account B cannot read account A's IDs.
8. Run `python scripts/service_smoke.py` from the configured backend environment or through an API image with the test dependencies installed. This checks real PostgreSQL/Redis/Celery/Qdrant when available.

Only Caddy ports are published. PostgreSQL, Redis and Qdrant are private Docker services; do not publish them on a production host. API proxy-header trust assumes this network boundary. CORS is an explicit allowlist. Secrets must remain in untracked environment/secrets storage.

## Persistence and recovery

Volumes: `pg_data`, `qdrant_data`, `redis_data`, `paper_files`, `model_cache`, Caddy certificate/config volumes. Redis AOF persists queue state. API and worker share original files; only the remote Qdrant server owns vector storage.

- Back up PostgreSQL with `docker compose exec -T postgres pg_dump -U papermind -d papermind > backup.sql`. Secure the backup: it contains private records and password hashes.
- Snapshot Qdrant through its official snapshot API on the private network; back up original PDF volume separately. Keep a consistent backup timestamp and schema revision.
- Restore into new volumes/instance, apply migrations, restore files and recreate vectors with the reindex endpoint if needed. Test restore before relying on it.
- Do not run `docker compose down -v` against valued data. A normal `docker compose down` preserves named volumes.
- A failed paper can be retried through its API/UI. After a worker hard failure the scheduled lease recovery exposes it as failed. Cleanup is retried by the scheduler; SQL hydration prevents stale vector access in the meantime.

After model changes, reindex ready papers. Reindex does not re-extract or overwrite user corrections. For parser/schema changes that need complete re-extraction, export corrections first and use a separately reviewed migration; no automatic destructive path is exposed.

## Environment verification record

On2026-10-20 the earlier GitHub Actions run39215378166 was checked: unit/frontend/services all succeeded, including actual PostgreSQL migration and Redis/Celery/remote-Qdrant smoke. This updates the earlier local-only service limitation, but is not public deployment/HTTPS verification. The scaling fix adds CPU-only Linux locks, a fifth migration and backend/frontend image-build gates. Record the new CI outcome separately from historical results. See `scaling-fixes.md` for configuration limits and reproducible checks.

On 2026-10-19 the local Docker Desktop daemon failed during inference-manager Unix-socket initialization (`dockerInference`: file cannot be accessed / invalid filename). Both Desktop startup and CLI startup were attempted; no reset or deletion of Docker data was performed. Therefore container image builds, live PostgreSQL/Redis/Celery/Qdrant Compose workflow and HTTPS are **BLOCKED**, not PASS. Compose static validation passed, and PostgreSQL migration SQL is in `docs/verification/postgresql-migration.sql`.

Before a public release, run the service smoke and browser flows on the target host, configure monitoring/backup/real model prices, and record actual results. A domain/server was not provided; no public deployment is claimed.
