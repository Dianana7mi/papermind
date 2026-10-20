# PaperMind persistent development record

## Current state — 2026-10-20

Scaling/boundary fixes completed: complete entity-name/alias checks, column-first unit selection, token-unit budget accounting with tokenizer estimates and unknown-usage reservations, tenant/version-scoped threaded BM25 cache, bounded candidate-only SQL hydration for dense retrieval, projected paper metadata, SQL JSON expression indexes for bits/method/architecture and a fifth Alembic migration. Linux torch/torchvision are locked to the official CPU index; CUDA/NVIDIA/Triton packages removed. Added15 tests (84 total). See `docs/scaling-fixes.md`, ADR0005 and `evaluation/results/scaling-before.json` / `scaling-after.json`. Warm10k requests114ms, warm4-way218–231ms; numeric filter51→1 SQL, median1,584→60ms. First10k index build remains1.58s. These are isolated synthetic ASGI/SQLite observations, not production P95.

The original GitHub run39215378166 completed successfully for unit/frontend/services. Source commitc7fb77b was pushed and CI39393849989 passed all four jobs: unit/frontend/services/containers. This includes fifth-revision PostgreSQL migration/index filtering, actual Redis/Celery/remote Qdrant, both Docker image builds and CPU-only Docling parser imports. Metadata: `docs/verification/github-actions-scaling.json`. The new service dependency step was6s versus the historical495s, with both CPU dependency and cache changes; no isolated causal speedup is inferred. Public HTTPS/full target Compose/Langfuse/human benchmark remain separate unverified work.

Review hardening completed: source-derived units (including persisted-record revalidation), server-owned per-field verification, explicit audited human condition confirmation, streaming/keyset condition filtering with pagination and ready-paper scope, SQL paper scoping before Agent limits, atomic Paper/Job claim and legacy orphan recovery. Follow-up planning may refine basic queries without downgrading explicitly routed comparison/research tasks. Added11 regression cases; latest69 backend tests and2 real browser tests passed. Published public repository: https://github.com/Dianana7mi/papermind (`origin/main`, initial commit `c18f35e`). GitHub Actions unit/frontend/services jobs were dispatched; outcomes are recorded after completion. No credentials, local DBs, downloaded PDFs/models, node_modules or virtual environments were included.

Resumable extraction completed and verified: `/papers/{id}/extract`, durable leases, stable cell dedup, preserved corrections and batch progress. Real AWQ run: 18 initial records,18 after a repeat,24 after the next batch, all original IDs retained (`ingestion-resume-smoke.json`). Running HTTP repeat preserved24 IDs with no additional model calls (`http-resume-smoke.json`). Status UI permits continuation/retry, and explorer refreshes while open. Browser logout/scope guards discard late responses and clear account state.

Local runnable delivery complete: source, real model/PDF flows, tests, deployment configuration, evaluation pilots and portfolio. **Production runtime verification and the target human benchmark remain incomplete.** See `ACCEPTANCE.md` for all 20 deliverables with PASS/PARTIAL/BLOCKED evidence. Source task: `REQUIREMENTS.md`.

## Phase ledger

| Phase | State | Evidence |
| --- | --- | --- |
| 0 Initialization | Complete | Separate Git repo; other workspace projects untouched; official APIs checked; dependencies installed and locked |
| 1 Basic RAG | Local PASS | Real PDF/Docling/dense/model/citation flow |
| 2 Advanced retrieval | PASS | Real BM25/RRF/CrossEncoder and 12-query pilot |
| 3 Structured extraction | PARTIAL | Real18→24 resumable extraction and idempotent repeat; corrections/leases tested; independent annotation/complete-paper quality not claimed |
| 4 Comparability | PASS tested scope | Configurable hard/soft/missing rules; synthetic cases and real UI conditions |
| 5 Verification | PASS tested scope | Cell/ID/entity/value/unit rules, bounded repair and fallible semantic judge |
| 6 Research graph | PASS | Conditional graph, limits, persistence, SSE, trace IDs and real seven-variant run |
| 7 Web product | PASS local | Core pages, structured filters, metadata bookmarks, audit, reports and actual PDF.js source rendering |
| 8 Evaluation | PARTIAL | Real retrieval/system pilots + synthetic rules; independent human quality annotations unfinished |
| 9 Deployment | Runtime BLOCKED | Compose/static config, Dockerfiles/Caddy/health/migration/worker/scheduler/service gate supplied; daemon fails before containers start |
| 10 Portfolio | Complete | Technical guide, demo, 25 grounded Q&A, CN/EN resume |

## Actual checks and artifacts

- `python -m pytest -q`: **84 passed**, latest saved timing in `docs/verification/backend-tests.txt`.
- Ruff lint/format over backend/tests/scripts/evaluation: passed. Frontend typecheck and optimized build passed (`frontend-build.txt`).
- Playwright: **2 passed**, latest timing in `docs/verification/browser-tests.txt`: real API registration/all screens/mobile/account switching and actual AWQ comparison/PDF.js page-4 pixels.
- Four Alembic revisions upgraded on SQLite; `alembic check` passed. PostgreSQL offline SQL regenerated; no live PostgreSQL connection is claimed.
- Real MiniLM embedding (384 dimensions), CrossEncoder, Docling/PDFium and DeepSeek calls executed. Actual errors and partial extraction are retained in raw JSON.
- Retrieval: 1 real paper / 46 chunks / 12 Agent source-anchor queries / zero human labels. Hybrid MRR 0.7562; BM25 Recall@5 0.9583. No universal gain claim.
- Seven variants on the same real library/question: 19 measured model calls, no final generation errors; quality accuracy and dollar cost null. `agent-ablation.json/.csv`.
- Real running-server SSE returned two supported textual claims, real PDF files and correlated trace IDs (`api-live-smoke.json`).
- Real running-server complex comparison returned 10 pairs (5 insufficient-information, 5 not-comparable), 3 model calls and no errors; conversation details were read back and matched the response (`api-comparison-smoke.json`). Decimal conditions retain their precision as JSON strings.
- Post-hardening real AWQ/model HTTP check returned10 insufficient-information comparisons and12 supported numeric claims,2 model calls, no errors, and matching persisted comparison details (`hardening-live-smoke.json`). Conditions are conservatively unverified rather than inferred from filled values. This is an integration result, not a human quality annotation.
- Real OpenAlex keyword search and work metadata fetch passed (`openalex-smoke.json`); metadata-import idempotency/isolation/SSRF tests use clearly isolated fixtures.
- Five 300 DPI PNG/editable SVG figures, visual review and figure checker passed after fixing text overlap and removing the heatmap bitmap (`figure-audit.txt`).
- Production/development Compose static config validation passed. Container/runtime verification did not.

## Decisions and observed fixes

1. Production PostgreSQL/Redis/Celery/remote Qdrant; explicit one-process SQLite/local-Qdrant dev mode. SQL owns authoritative data and reauthorizes vector hits.
2. Native docling-parse failed to load resources in this Chinese Windows checkout. PDFium standard pipeline worked. Disabling secondary cell matching recovered the AWQ multi-level table grid.
3. Full-table generation exceeded output limits. Extract six real target cells with retained headers/captions; report unprocessed batches. Unique exact-literal recovery still checks method/model/dataset/metric context; ambiguous duplicates stay insufficient.
4. Large comparison payloads exceeded context limits. Model inputs now omit repeated source text and summarize comparison conditions, while complete data stays in SQL/UI.
5. JSON/schema repair is limited to one extra call; numerical result prose is rebuilt server-side. Semantic judgment is fallible. Unknown failed-call usage marks accounting incomplete.
6. Separate auth/API rate buckets fixed false login throttling. SSE stops on done/error and uses a nonblocking sentinel so cancellation cannot deadlock a full queue.
7. Blank native PDF iframe found during visual QA; replaced with PDF.js worker/canvas/navigation/zoom and a real pixel assertion.
8. Corrections preserve original data and before/after/reason/version. Cleanup is a durable outbox. Public metadata references remain unindexed and distinct from uploaded papers.
9. Added regressions for insufficient experiment matches, section routing, LangGraph no-op updates and precision-preserving comparison persistence. Decimal comparison fields are JSON-encoded as strings before storing messages; missing-model/empty-node paths no longer fail.

ADRs: `docs/decisions/`. Keys remain in process environments/untracked configuration; never print or save them in progress/artifacts.

## Core files and runnable commands

- Backend: `app/main.py`, `core/`, `models.py`, `schemas.py`, `api/routes.py`, `retrieval.py`, `experiments.py`, `ingestion/`, `services/`, `agents/`, `tasks.py`, `evaluation.py`.
- UI: `frontend/app/page.tsx`, `components/PdfViewer.tsx`, `lib/api.ts`. Build copies the matching PDF.js worker into public assets.
- Reproduction: `scripts/`, `evaluation/scripts/`, backend and Playwright tests, `.github/workflows/ci.yml`.
- Delivery: Compose/Dockerfiles/Caddyfile, README/ACCEPTANCE, docs/portfolio and verification artifacts.

From backend: `.venv/Scripts/python -m pytest -q`; `.venv/Scripts/ruff check app tests ../scripts ../evaluation/scripts`; `.venv/Scripts/alembic upgrade head`; `.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.

From frontend: `npm ci`; `npm run typecheck`; `npm run build`; `npm start`; `npm run test:e2e` (API/frontend running; real-library test requires its documented short-lived QA token). Root `scripts/dev.ps1 -DeepSeek` uses an existing environment credential without saving it.

Local app: `http://localhost:3000`; API: `http://localhost:8000/docs`. `live_smoke.py` invokes the real provider. `http_smoke.py` targets the existing local smoke library and assumes trusted local SQLite development. `service_smoke.py` is the separate production-service gate.

## Remaining work and external blocks

- Docker Desktop 4.56.0 fails inference-manager Unix-socket initialization (`dockerInference`: inaccessible/invalid filename). Desktop/CLI startup attempted; no reset/deletion performed. Container builds, live Postgres/Redis/Celery/remote-Qdrant and HTTPS require a working engine/target host. CI service gate is supplied but has not run here.
- No server/domain or Langfuse deployment credentials: no public deployment/remote trace-export success claimed.
- Target 30 papers / 150 human-verified experiments / 100 questions needs real independent annotation. Human-verified count remains 0. Expand real multi-paper/MoE/cross-page-table cases before wider claims.
- API embedding/rerank adapters exist; executed real retrieval used CPU local models. Remote provider-specific embeddings/reranking need their own live checks.
- Advanced figures/equations/highlights, shared memberships, large sparse indexes and high-concurrency testing remain outside verified local scope.

## Next session

Read this record and `ACCEPTANCE.md`, inspect Git status and run existing checks. Target the blocked service gate or independent annotations; preserve the stable modules/real artifacts. Do not regenerate the project or relabel pilot data as human gold.
