# Interview questions and grounded answers

1. **Why Agentic RAG?** Complex comparison needs planning, structured retrieval and validation; simple QA skips planning. See graph conditional edges.
2. **Why does ordinary RAG struggle with experiments?** Text similarity cannot guarantee equal model/version/dataset/budget. The SQL experiment schema exposes these constraints explicitly.
3. **Dense vs BM25?** Dense learns semantic similarity; BM25 weights lexical term frequency/inverse document frequency and length. The pilot shows lexical anchors can favor BM25.
4. **How does RRF work?** Sum `1/(60+rank)` per retriever, deduplicating each list. It avoids calibrating dense and BM25 scores.
5. **Why rerank?** A CrossEncoder jointly evaluates query/candidate text but adds latency; the actual pilot did not show a gain, so it is optional.
6. **Why an experiment index?** It retrieves and filters model/dataset/budget conditions rather than hoping a chunk mentions them. SQL remains authoritative.
7. **Why not LLM-only fairness judgments?** Missing and mismatched conditions are explicit deterministic branches, testable independently of wording/model randomness.
8. **How is comparability designed?** Configurable required/hard/soft field sets, explicit unit conversion, per-field evidence and four statuses. `experiments.py::compare`.
9. **How are missing fields handled?** Null/unknown stays missing; required unknowns yield INSUFFICIENT_INFORMATION. Two unknown versions do not establish a match.
10. **How are invented numbers prevented?** Strict schema plus exact source-cell/value/entity checks and server-rendered numerical result claims. A parsed record is not automatically trusted.
11. **How are citations located?** Stable evidence IDs link to owned papers and real Docling page/cell metadata. The viewer opens the PDF page and source snippet without invented highlights.
12. **What about two-column/complex tables?** Docling standard pipeline handles layout; raw document/cells are retained. The observed PDFium/cell-matching issue is documented, and ambiguous cases remain reviewable.
13. **What is LangGraph state?** Query/scope/queries/evidence/experiments/comparisons/claims/verdicts/tool counts/retries/budget/answer. Persistent public outputs are stored with messages; prompts are transient.
14. **How is the next action chosen?** Bilingual intent routing and conditional edges select planning, experiment query and comparison; a constrained plan provides retrieval queries and whitelisted filters.
15. **How are loops bounded?** Empty retrieval <=2, verification <=2, max tool calls, recursion limit24, wall-clock timeout, bounded provider retry and token/context caps.
16. **How are vector users isolated?** Mandatory owner/library payload filters plus SQL rehydration. Tests use real local Qdrant to confirm separation and deletion.
17. **How is parsing asynchronous?** Upload validates/stores and queues a Celery job; a worker performs CPU parsing. Local mode uses explicit background tasks. SQL status claims enforce idempotency.
18. **How are ablations made reproducible?** Same library/question/models/config; compare retrieval modes and seven internal graph configurations, recording extra tools/tokens/latency. Independent quality labels are still needed.
19. **Why can agentic RAG be worse?** Additional planning can misroute, retrieval can add irrelevant context, judges can reject valid content, and cost/latency rise. Pilot results are disclosed without cherry-picking.
20. **How are costs controlled?** Bounded context/input/total/output tokens, calls/retries/time and six-cell extraction units. Dollar cap requires configured prices; unknown cost is null.
21. **How would deployment work?** Caddy → Next/API; private Postgres/Redis/Qdrant; worker/scheduler; migration gate; persistent volumes/health checks/backups. Local Docker failure prevents claiming this was actually deployed.
22. **How does this differ from PaperQA2/ScholarQA?** The project's chosen engineering focus is structured experimental conditions and deterministic provenance/comparison checks. It does not claim those are absent from all prior systems or establish superiority.
23. **What was implemented vs reused?** Business schemas/orchestration/rules/alignment/evaluation are local. Parser/ranking library/model/provider/graph/database/UI framework components are reused and attributed.
24. **Which improvement helped most?** On the 12-query agent-anchor pilot, hybrid had the best MRR/nDCG; BM25 had the best Recall@5 and reranking did not help. This cannot establish a general best component.
25. **What remains?** Human gold annotation at target scale, more real multi-paper/MoE cases, full controlled quality ablations, production service/HTTPS validation, richer table/figure recovery and scale testing.
