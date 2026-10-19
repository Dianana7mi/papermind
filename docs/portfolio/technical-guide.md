# PaperMind technical portfolio

## Architecture and ownership

The product uses a Next.js research workspace, authenticated FastAPI application, background ingestion worker, PostgreSQL authoritative storage and three derived Qdrant indexes. See [architecture](../architecture.md), [data model](../data-model.md) and [deployment](../deployment.md). Core business logic was implemented in this project; no entire external application was copied.

Owned modules:

| Module | Implementation | Why it exists |
| --- | --- | --- |
| Experiment-aware RAG | `backend/app/ingestion/pipeline.py`, `schemas.py`, `retrieval.py` | Search structured model/dataset/budget constraints as well as original text |
| Comparability | `backend/app/experiments.py::compare` | Hard, soft and missing conditions determine explainable comparison status |
| Claim verification | `experiments.py::align_record`, `verify_claim` | Bind measurement to real source cells and reject wrong IDs/entities/units/values |
| Research graph | `agents/research.py`, `agents/tools.py` | Conditional planning/retrieval/comparison/verification with explicit exits |
| Evaluation | `app/evaluation.py`, `evaluation/scripts/` | Reproduce measured ranking, rule regression, latency, tokens and configured cost |

Reused components: Docling/PDFium layout/table parser, SentenceTransformers/CrossEncoder, rank-bm25, Qdrant client, LangChain provider integration, LangGraph state machine, SQLAlchemy/Alembic, Celery/Redis, FastAPI and React/Next/TanStack. Their behavior is not claimed as original research.

## RAG implementation

The SQL store owns paper/evidence/experiment records; vectors are derived caches. Dense and BM25 rank independently, RRF uses reciprocal rank rather than incomparable raw scores, and optional CrossEncoder reorders top candidates. Queries can target paper/evidence/experiment levels and filter user/library/paper. Vector permission filters are followed by authorized SQL hydration. The BM25 development implementation is bounded to 10k units/library; local model token limits and parser quality remain practical limits.

Experiment lookup parses only allowlisted filters. LLMs cannot issue SQL. Decimal measurements preserve raw value/unit semantics. Automatic extraction selects six real numeric cells per batch and supplies original row/column context. Fields absent from the source remain unknown; partial batch processing is visible.

## Comparability and claims

Rule configuration separates required fields, incompatible hard conditions and qualified soft differences. Missing versions prevent a strict comparison. Different average bits do not imply equal-budget performance, and different calibration counts require a limitation. Returned conditions include matching status and source IDs.

Measurement alignment validates source IDs, server page, raw value, addressed cell and method/model/dataset/metric context. Numerical result claims additionally check record identity/value/unit and are rendered by deterministic code. Textual claims use a separate model judgment and are not treated as mathematical proof. Unsupported claims are removed after bounded repair; fallback shows original quotations.

## LangGraph and cost control

The graph uses conditional edges for simple QA, planning, structured experiments, comparison, empty retrieval retry and verification repair. Runtime state contains server scope, evidence, records, claims, decisions and budget counters. Conversations and public trace summaries persist in SQL; prompts/raw reasoning do not stream to clients. Requests have bounded tool counts, recursion, wall time, output, input and total tokens. Dollar enforcement requires configured prices; unknown costs remain null.

Seven evaluation configurations exist in `agent_ablation.py`, with safety bypasses confined to trusted CLI evaluation. Public ChatInput rejects attempts to disable verification. Baseline outputs are explicitly labeled unverified. The controlled quality study still needs independent human gold answers.

## Measured results and appropriate claims

See [evaluation report](../evaluation-report.md) and raw JSON/CSV. On the 12-query, one-paper anchor pilot, hybrid MRR was 0.7562; dense MRR was 0.5343. BM25 had the best labeled Recall@5, and reranking did not improve this run. This is a tiny agent-labeled pilot, not evidence of universal superiority. Original source, query construction, run order and missing cost measurements are disclosed.

The real-model pipeline parsed AWQ, extracted checked measurements and returned PDF citations. The automated suite separately covers security and failure cases. PostgreSQL/Redis/Celery production service smoke is supplied but blocked locally by Docker startup; do not claim a successful public production deployment.
