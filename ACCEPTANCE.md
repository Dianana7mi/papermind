# Delivery acceptance — 2026-10-19

Status is evidence-based: PASS means the stated local acceptance actually ran, PARTIAL means implementation exists with limited verification/scope, BLOCKED identifies an external constraint. This is not a claim that every original target was fully achieved.

| # | Required deliverable | Status | Actual evidence and limits |
| --- | --- | --- | --- |
| 1 | Complete project source | PASS | Independent monorepo, locked Python/npm dependencies; backend tests and frontend build executed. Scope limits below remain. |
| 2 | Web application | PASS | Production build, real API browser test across all pages/mobile/auth; actual AWQ explorer/comparison/PDF test. `docs/verification/browser-tests.txt`, screenshots. |
| 3 | FastAPI backend | PASS | Auth/CRUD/search/experiments/graph/SSE/evaluation exercised; exported OpenAPI. `backend/tests/`, `docs/verification/backend-tests.txt`. |
| 4 | PostgreSQL + migrations | PARTIAL | SQLAlchemy/asyncpg + Alembic code; SQLite migrations executed; PostgreSQL offline SQL generated. Live PostgreSQL blocked by Docker engine. |
| 5 | Qdrant integration | PASS | Actual embedded Qdrant indexing/query/filter/delete and real local dense search; remote server mode implemented but not locally container-verified. |
| 6 | Upload + Docling | PASS | Actual 15-page AWQ standard Docling/PDFium parse, table recovery, source pages and raw document; parser limitations/batch warnings retained. |
| 7 | Dense/BM25/RRF/Reranker | PASS | All four modes invoked with real local models; 12-query real-text pilot and JSON/CSV results. |
| 8 | Structured extraction | PARTIAL | Original pilot extracted 12 source-aligned candidates. Additional real run extracted18, repeated a batch without duplicates, then continued to24 with original IDs retained (`ingestion-resume-smoke.json`, `http-resume-smoke.json`). Resumable jobs/correction preservation tested; independent full-paper gold accuracy remains unavailable. |
| 9 | Comparability Engine | PASS | Deterministic configurable rules; matching/different bits/metrics/calibration/unknown/version/scope cases; real UI comparison returns unknown conditions. No causal or statistical-significance claim. |
| 10 | Claim–evidence verification | PASS | Invalid IDs/entities/values/units tested; real cell alignment, 6 real semantic claims and PDF files; independent LLM judgment remains fallible and not human gold. |
| 11 | LangGraph Research Agent | PASS | Conditional planning/retrieval/structured comparison/verification, retries/tool/time/token bounds, persisted traces; real seven-variant CLI run. Public API cannot bypass verification. |
| 12 | Users and resource isolation | PASS | Real registration/login/library flows; SQL/vector/file/evidence/experiment cross-user denial, revisions, delete/index cleanup tests. Private libraries only; sharing not implemented. |
| 13 | Basic online search | PASS | Real OpenAlex HTTP200 query executed; authenticated fixed-endpoint search supports metadata/years/pagination and bounded retry. Metadata-only results are labeled; automatic fulltext import is not implemented. |
| 14 | Automated RAG evaluation | PARTIAL | Actual 1-paper/12-query ranking pilot, eight synthetic rule cases, six synthetic claim cases, seven real graph variants on one question. No independent human answer/field labels; full 30/150/100 target unfinished. |
| 15 | End-to-end tests | PASS | Upload→real parser→SQL/index→search→test extraction→SSE→citations→deletion test (isolated model doubles clearly labeled), extra real-provider/PDF smoke, and two real browser tests. |
| 16 | Docker deployment | BLOCKED | Dockerfiles, Compose, Caddy, persistence/health/migration/worker/scheduler and service gate supplied; static Compose validation passed. Docker Desktop fails inference-manager socket initialization. No images/startup/HTTPS claimed verified. |
| 17 | README | PASS | Actual local startup/reproduction commands, limits, references, secrets handling and screenshots documented. |
| 18 | API documentation | PASS | Live `/docs`, generated `docs/openapi.json`, request/SSE/error contracts in `docs/api.md`. |
| 19 | Architecture documentation | PASS | Actual module/storage/graph diagram, data model, security and ADRs match implementation. |
| 20 | Resume materials | PASS | `docs/portfolio/`: implementation guide, demo, 25 Q&A and CN/EN resume; only observed numbers, no novelty/production claims. |

## Executed checks

Review hardening:69 backend tests and2 real browser tests passed. Regression evidence includes wrong units, unsupported condition trust, explicit human confirmations, persisted-record revalidation, matches beyond1,000 candidates, ready-paper scopes, atomic worker claims and legacy orphan recovery. Historical live-model/benchmark outputs below retain their original scope and are not new post-hardening quality measurements. See ADR0004 and saved verification outputs.

- `backend/.venv/Scripts/python -m pytest -q` — see latest saved count and timing in `docs/verification/backend-tests.txt`.
- `ruff check app tests` — passed; Python sources formatted.
- Alembic `upgrade head` on SQLite and PostgreSQL `upgrade head --sql` — executed. The latter is SQL generation, not a database connection.
- Frontend `npm run typecheck`, `npm run build`, `npm start` — executed; production standalone server served the browser tests.
- Playwright — 2 tests actually ran and passed, including a real already-ingested AWQ library with a short-lived in-memory QA token. No credential is written to result artifacts.
- Real local Embedding (384 dimensions), CrossEncoder, Docling, DeepSeek and OpenAlex — executed; model/API errors and budgets preserved in actual results.
- Real HTTP complex comparison and persisted conversation readback — passed; 10 comparison pairs, 3 model calls, no errors (`evaluation/results/api-comparison-smoke.json`).
- `docker compose --env-file .env.example config --quiet` with `PM_ENV_FILE=.env.example` — passed. Docker daemon/production integrations remain blocked.

## Known remaining work

Production service gate/HTTPS/Langfuse export; larger independent human-verified benchmark; more cross-paper/MoE fixtures; advanced figure/equation understanding; parser edge cases/cross-page tables; larger-scale sparse retrieval/performance testing. The code does not claim that these have passed. Continue from `PROGRESS.md` rather than replacing the stable modules.
