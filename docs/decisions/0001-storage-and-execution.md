# ADR 0001 — Authoritative SQL, derived vectors, explicit local mode

Accepted 2026-10-19. PostgreSQL owns users, provenance and corrected experiments. Qdrant contains derived vectors and permission metadata. SQL authorization is checked again when vector hits are hydrated. This permits asynchronous cleanup without accepting stale/deleted vector payloads as authority.

Production uses Redis/Celery and a separate worker. A named development mode provides SQLite/local Qdrant/background tasks so missing Docker does not require fabricated services. Production validation rejects that mode. The local embedded Qdrant process cannot be shared with a standalone worker.

The initial schema consolidates sections/tables/cells into typed evidence plus Docling JSON instead of many weak join tables. Correction history remains relational. This is a bounded library application, not a large sparse-search cluster; in-memory scoped BM25 caps at 10,000 evidence units.
