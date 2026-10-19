# ADR 0004 — Separate measurement checks from condition trust

Status: accepted, 2026-10-19.

Review reproduced five faults: model-proposed score units accepted under percentage headers; unsupported filled conditions receiving comparable status; a split Paper/Job claim becoming unrecoverable after a process exit; JSON conditions filtered after a1,000-row cap; and failed-paper experiment rows entering structured retrieval.

The existing business modules remain in place. Alignment now rebuilds a server-owned `field_verification` map and derives units from source literals/metric labels. Unknown units remain insufficient. Numerical claims realign saved records, protecting records created before this change. Comparison requires verified conditions rather than trusting presence or equality of generated strings. Unsupported source conditions remain unknown; an authenticated user can explicitly confirm selected conditions in the revision API/UI, with before/after/reason audit. Confirmations survive only unchanged values and evidence IDs. Original model outputs are retained.

Structured search joins ready papers and scans ID-keyset batches before applying a response limit. This bounds memory and removes silent candidate truncation; JSON filtering is still linear in candidate count, so promoting commonly queried fields to typed indexed columns remains a future performance option. API/UI expose result pagination. Agent retrieved-paper scope is applied in SQL before taking its30 records.

The initial paper claim and processing Job/started timestamp now share one transaction. The scheduler handles legacy orphan claims as recoverable failures as well as normal expired jobs. These cases are exercised by isolated SQL/regression fixtures, without external model calls.

The existing benchmark outputs are historical executions of the prior code and are not relabeled as new quality measurements. Human annotation counts and production-service verification limits remain unchanged. This hardening establishes regression correctness, not benchmark superiority.
