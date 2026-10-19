# Five-minute demonstration script

1. Start the backend with real model configuration and the frontend. Check Settings shows configured chat, actual embedding model and parser. Register an account; create a private research library.
2. Upload a public ML PDF that you are permitted to use (the documented AWQ source is one verified example). Show pending/processing/ready and the status dialog's real warnings/batch counts. Do not hide failed/partial extraction.
3. Ask: “What is the key idea behind activation-aware weight quantization?” Show the live node sequence, answer, citation snippets and source page. Explain that text chunks are emitted after verification and that the semantic judge is fallible.
4. Open Experiment Explorer. Inspect method/model/dataset/raw value/precision, null conditions, source IDs and measurement verification status. Open the real PDF page; no fake cell highlight is drawn.
5. Select two experiments and compare. Explain every matched/mismatched/missing field. Missing model versions/protocols should produce INSUFFICIENT_INFORMATION; do not manufacture a COMPARABLE demonstration by filling unknowns.
6. In a separately labeled synthetic test, run `pytest` cases that change only average bits/calibration/metric/version. These demonstrate rule behavior, not real research results.
7. Correct an extraction with evidence and a reason. Show the unchanged original record, revision history and version conflict protection. Open the source again to audit the change.
8. Generate a report, export Markdown, then inspect the graph trace and actual token usage. Unknown dollar cost is shown as unknown.
9. Show the real 12-query JSON/CSV/charts and explain why BM25/reranking results prevent a blanket “more modules is better” claim. The seven-variant trial is exploratory; human benchmark scale is unfinished.
10. Sign in as a second user and attempt a copied paper/evidence ID. It must return 404. Show Docker/production limits openly, alongside the reproducible service gate and configuration files.

Screenshots in `docs/screenshots/` were captured from the actual local application, including real AWQ experiments, comparison and citation view. Empty-state screenshots are intentionally empty; no fabricated paper library was inserted for presentation.
