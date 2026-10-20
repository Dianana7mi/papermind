# ADR0005 — Reuse scoped sparse indexes and query indexed conditions

Accepted2026-10-20.

The10k review found repeated full-library ORM hydration, synchronous BM25 construction and a shared cap blocking dense retrieval. It also reproduced scientific-name prefix collisions, multi-metric unit confusion and mixed byte/token budget accounting.

Use complete name/alias boundaries and column-first unit resolution. Preserve uncertainty in ambiguous captions. Provider preflight uses token units, reserves output space and stops exhausted budgets before network calls. Known tokenizer work runs in a thread; unknown models use conservative bytes. Missing provider usage reserves estimates without fabricating measured tokens/cost.

Keep real BM25 but reuse its immutable frequencies in a small LRU, with tokenizer/build/query CPU work in threads. Key entries by tenant, library, paper, level and a SQL library revision. Mutations touch that revision transactionally, including worker writes; all final hits still pass SQL authorization and ready-paper filtering. Build once per cache version rather than every request. Cold construction remains serialized/bounded; large lexical corpora receive a clear422. Dense queries have independent capacity and retrieve only bounded authorized candidates.

Use portable SQLAlchemy JSON expressions plus SQL indexes for common structured conditions instead of duplicating authoritative records into additional manually synchronized columns. Retain exact Python comparisons to reject numeric precision ambiguities and handle list conditions. SQLite cannot reflect expression indexes for Alembic autogeneration; explicit migration and EXPLAIN tests check them. PostgreSQL service CI exercises the same filter path.

Lock Linux Torch and Torchvision to the explicit official CPU index. Keep the compatible non-Linux sources. Verify CPU imports in service/image CI and enable uv cache. Do not relabel historical retrieval/model-quality pilots or infer image-size/speed gains from static dependency presence.
