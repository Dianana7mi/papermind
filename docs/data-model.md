# Data model and provenance

SQLAlchemy tables: `users`, `libraries`, `papers`, `evidence`, `experiments`, `extraction_revisions`, `extraction_jobs`, `conversations`, `messages`, `evaluation_runs`, `cleanup_outbox`, `public_references`.

Public references are owner-scoped metadata bookmarks, separate from uploaded/indexed papers. Their OpenAlex IDs are validated, metadata is fetched from a fixed provider host, and duplicate IDs within a library return the existing bookmark. No experiment or vector is created from metadata alone.

Stable UUID keys link records. Owner and library IDs appear in every searchable resource. Library owners have private access only; shared memberships are not implemented. Paper SHA-256 is unique within a library. Experiment fingerprints bind method/model/dataset/value/settings plus source row/column. A ready paper cannot be re-extracted through the retry endpoint, protecting human corrections; reindexing is independent and idempotent.

`evidence` stores paragraph/table/heading/caption kind, page, section, source self-ref, real bounding box if present, table cells, merged spans, row/column headers and captions. Parser-order table IDs are explicitly distinguished from printed table numbers. Full Docling JSON is stored in paper metadata but excluded from ordinary API lists.

`ExperimentRecord` defines all requested identity/model/dataset/measurement/quantization/setup/provenance/quality fields. Missing information stays null/unknown. `metric_value`, `bit_width` and `average_bits` use Decimal, serialized as strings. Raw measurement and normalized value/unit/statistics remain separately available. `79%` and fraction `0.79` compare only through explicit unit conversion; unitless `0.79` is not silently interpreted as accuracy.

Cell offsets are `row_index` and `column_index`; human labels remain `row_identifier` and `column_identifier`. If a model returns labels instead of offsets, the server may recover a cell only from a unique exact literal, followed by method/model/dataset/metric header/caption checks. Ambiguous duplicates remain insufficient. Supplied PDF pages are overwritten with the real source page.

Resumable jobs use stored `source_order`/`chunk_order` and a paper-level extraction lease. Stable cell fingerprints and known-cell checks prevent repeated extraction from duplicating rows or replacing corrected data; paragraph dedup also checks the original model record. Each batch commits separately. Failed-batch indices/next offset survive in job results, and already committed data remains available after a failed continuation. Raw model output and aligned/current records are stored separately.

`verification_status=supported` for an extracted record means its reported measurement and checked entity/header associations passed alignment. It does **not** certify every calibration/inference/precision field, the correctness of the original paper, or independent human review. `review_status` is separate. Human corrections preserve the original model output and append before/after/reason/time; optimistic versions reject stale writes.

`field_verification` is stored inside the experiment JSON, with server-generated `supported` checks and explicit human `reviewed` confirmations. It requires no relational migration. Missing entries are unverified; old records default to an empty map. Comparison never treats a filled but unverified condition as matched. Automatic numeric verification derives the source unit independently of the model-proposed unit. Human confirmations are captured through revision requests, not trusted from arbitrary record JSON.

Paper deletion first removes SQL experiment/revision/evidence/job records and records a durable cleanup item in the same transaction. Cleanup removes vectors across all embedding versions and the file. Stale vector hits are inaccessible because SQL hydration rejects them. Processing papers reject normal deletion until processing finishes. Celery beat retries cleanup and marks processing leases older than 20 minutes failed, allowing explicit retry. Pending jobs are redispatched; atomic SQL status claims prevent duplicate ingestion.

Conversation messages persist answer text, citations, verification decisions, comparisons, graph trace and usage. Evaluation runs hold user-supplied relevance judgments and actual outputs. User-owned data is not used as a public benchmark.

Migrations are explicit Alembic files. SQLite upgrades and PostgreSQL offline SQL generation were executed; live PostgreSQL migration remains blocked by the unavailable container engine.
