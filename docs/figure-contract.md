# Pilot figure contract

- Purpose: show observed retrieval quality/latency and the designed rule regression outcomes without claiming general improvements.
- Evidence: `evaluation/results/pilot.json`, `retrieval.csv`, `comparability.csv`; the plotting script exports a data profile first.
- Layout: four separate quantitative panels, Matplotlib, 7.2 inch width, 300 DPI PNG plus editable-text SVG.
- Retrieval: individual query dot plot with mean marks; no invented uncertainty intervals.
- Latency: individual calls, log y-axis explicitly labeled; cold calls retained, fixed order disclosed.
- Ablation: synthetic eight-case pass/fail matrix. Not a full-system scientific ablation.
- Cost: external generation cost is exactly zero only because these retrieval runs make zero generation calls. CPU cost is missing; live-model dollar cost is unknown. Unknown costs must never be plotted as zero.
- Palette: Okabe–Ito, redundant marker shapes; cividis for binary heatmap with PASS/FAIL text.
- Limit: one real paper, agent-curated anchor judgments, zero human-verified annotations. No publication/acceptance claim.
