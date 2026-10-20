# API contract

Interactive OpenAPI: `http://localhost:8000/docs`; checked-in [openapi.json](openapi.json) is generated from the running application. Prefix `/api/v1`.

Use `Authorization: Bearer <access_token>`. Registration/login accept JSON `{email,password}`; minimum password length 10. Tokens expire after 120 minutes by default. Login/registration and ordinary API traffic have separate IP rate buckets. Production rate limits use Redis. Every private read checks resource ownership; missing and unauthorized resources return 404.

| Area | Routes |
| --- | --- |
| Authentication | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Libraries | `GET,POST /libraries`; `GET,PATCH,DELETE /libraries/{id}` |
| Papers | `POST /papers/upload`; `GET /papers`; `GET,DELETE /papers/{id}`; `GET /papers/{id}/status`; `GET /papers/{id}/file`; `POST /papers/{id}/retry`; `POST /papers/{id}/reindex`; `POST /papers/{id}/extract` |
| Retrieval | `POST /search`; `POST /search/experiments`; `GET /evidence/{id}` |
| Experiments | `GET /experiments`; `GET,PATCH /experiments/{id}`; `POST /experiments/compare` |
| Research | `POST /research/chat`, `/research/chat/stream`, `/research/report`; `GET /research/conversations`; `GET /research/conversations/{id}` |
| Evaluation | `POST /evaluation/run`; `GET /evaluation/runs`; `GET /evaluation/runs/{id}` |
| Public metadata | `GET /public/papers?q=...&year_from=...&year_to=...&page=1`; `POST /public/import`; `GET /public/references?library_id=...`; `DELETE /public/references/{id}` |
| Workspace | `GET /settings`; `GET /stats` |
| Health | `/health/live`, `/health/ready` (outside version prefix) |

List endpoints use offset/limit with bounded maximums. Structured search uses exact whitelisted fields and decimal budget equality; no raw SQL is accepted. Search example:

```json
{"library_id":"<uuid>","query":"mixed precision quantization","mode":"hybrid","top_k":8,"level":"evidence","paper_id":null}
```

Modes: `dense`, `bm25`, `hybrid`, `rerank`. Levels: `paper`, `evidence`, `experiment`. Structured filters include model, dataset, metric, precision and quantized components; Pydantic rejects unknown keys.

Upload is multipart with `library_id` and `file` (PDF MIME and extension, signature, readable unencrypted PDF, <=30 MB and <=150 pages). The filename is display-only; the server uses generated UUID paths. Response 202 identifies a pending paper; identical SHA within the same library returns the existing paper with `duplicate=true`. Status includes extraction warnings, partial budgets and job errors. A ready paper is not silently reparsed. Failed processing can be retried; ready papers can be reindexed without changing records.

`POST /papers/{id}/extract` accepts `{offset:0,limit:5}` (zero-based batches, limit1–20), queues a durable scoped extraction job and returns 202. It uses stored evidence, never reparses/replaces it, and skips already extracted cells without new model calls. Status reports `next_batch`, `failed_batches`, remaining batches and usage. A lease prevents concurrent extraction/deletion; scheduler recovery releases expired leases. Existing records, IDs and corrections remain intact. Missing model configuration returns 503. The status dialog exposes this operation for continuing or retrying batches.

Experiment PATCH requires `{record:<complete ExperimentRecord>,reason:"...",version:1}`. Evidence must belong to the same paper. The service binds IDs, recalculates measurement verification, appends an audit revision and rejects stale versions with 409. The original model output remains available from the detail endpoint. Vector reindex failure returns a warning without discarding the saved SQL correction.

PATCH optionally accepts `confirmed_fields:["model_version","average_bits"]` for conditions the user explicitly checked against the cited paper. Only non-empty comparison conditions are eligible; deterministic identity/unit fields cannot be overridden this way. The server discards client/model `field_verification` declarations and rebuilds automatic checks, then records explicit condition confirmations as `reviewed`. Existing manual confirmations survive unrelated edits only while values and evidence IDs remain unchanged. A supported measurement does not certify every experimental condition. Older stored records are rechecked against source cells before numerical claims are accepted.

`POST /search/experiments?offset=0&limit=50` returns `{items,next_offset}`; `next_offset:null` means the final page. Conditions are filtered across stable ID-ordered keyset batches, so matches after the former1,000-candidate cap are retained. Both structured and text retrieval exclude non-ready papers. Agent paper scopes are applied before its result limit.

Comparison accepts 2–20 distinct experiment IDs owned by the caller and returns all pairwise results. `COMPARABLE` means checked rule conditions match, not statistical significance. `PARTIALLY_COMPARABLE`, `NOT_COMPARABLE` and `INSUFFICIENT_INFORMATION` preserve differences and unknowns explicitly.

SSE research emits:

```text
event: status
data: {"node":"retrieve","elapsed_ms":42,"tool_count":1}

event: token
data: {"text":"verified text chunk"}

event: done
data: {"answer":"...","citations":[],"trace":[],"usage":{},"conversation_id":"..."}
```

Token events are **verified server text chunks**, not raw model tokens. A heartbeat comment is emitted every 15 seconds while waiting. Errors contain a safe code/message and end the stream. Cancellation cancels the graph task; already executed provider requests may still be billed by the provider.

Ordinary errors use `{"error":{"code":"...","message":"...","request_id":"..."}}`. Validation errors identify field paths without echoing passwords or private inputs. Trace details and model token usage are persisted with assistant messages.

`POST /evaluation/run` uses user-supplied queries and relevant evidence IDs in the same library. It runs actual retrieval, reports Recall@5/@10, MRR, nDCG@10 and timing. It does not manufacture gold labels or infer model cost. Execution is currently bounded synchronous API work (max100 questions/4 modes/300s); large jobs should move to the worker before scaling.

Online search returns metadata only. Import accepts `{library_id,openalex_id}`, validates the ID and fetches metadata from a fixed OpenAlex host. Saved references remain labeled metadata-only/unindexed, with no experiments generated. It never treats an abstract as a parsed experiment table and never automatically downloads a user-supplied URL.

Scaling update: Dense lookup no longer has the lexical corpus cap and hydrates at most40 candidates through authorized SQL. BM25/hybrid/rerank reuse a tenant/version-scoped index. Default lexical capacity is50,000 documents/32million characters (`PM_BM25_MAX_DOCUMENTS`, `PM_BM25_MAX_CHARACTERS`); exceeded capacity returns a structured422 rather than500, with dense/sharding guidance. High-frequency structured conditions are SQL-filtered through expression indexes before pagination. Existing deployments must apply the fifth Alembic revision.
