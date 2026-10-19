# ADR 0003 — PDFium and bounded target-cell extraction

Accepted 2026-10-19 after actual failures. Native docling-parse could not load its resources under this Chinese Windows checkout path. Use Docling's PDFium backend with the standard CPU layout/table pipeline.

The first AWQ parse with secondary cell matching collapsed numeric columns into large text cells. `do_cell_matching=False` recovered the multi-level table grid in a controlled page-4 check. This setting is configurable (`PM_DOCLING_CELL_MATCHING`); no universal parser-accuracy claim is made.

Full-table JSON generation exceeded output limits. Extraction now supplies at most six target cells with their complete relevant headers, captions and row labels. Omitted/ambiguous/default fields remain unknown. A per-upload batch limit bounds cost and reports remaining batches. Model-proposed labels may be resolved only to a unique exact literal plus entity/header checks; duplicate literals require review. Original full tables remain available in SQL.
