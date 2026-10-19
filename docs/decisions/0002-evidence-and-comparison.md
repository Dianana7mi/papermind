# ADR 0002 — Conservative deterministic rules and fallible semantic review

Accepted 2026-10-19. LLMs extract structured records and propose atomic claims. The server binds IDs, source pages and cell positions. Comparison is deterministic and domain configurable; hard mismatch wins, then missing required information, then soft differences. Unknown never equals confirmed compatibility.

Numeric normalization requires explicit units. Numeric answer prose is reconstructed by the server after record/citation/value/entity checks. Complex prose uses a separate structured semantic judgment and remains labeled fallible. The same provider may supply generation and judgment; it is not independent human evidence.

Structured comparison never declares causal superiority or statistical significance. Supported source alignment certifies the checked measurement/header association, not every experimental setting. Missing calibration/protocol fields remain visible for review.
