# Boundary and scaling fixes — 2026-10-20

The review used freshly cloned commit0b49ded and isolated synthetic data. Original source/data services were no longer running. `scaling-before.json` preserves that measurement; `scaling-after.json` records the revised code with the same2,079-character evidence workload. Both use Python3.12.4 on Windows11, SQLite and in-process ASGI transport. No paid model API or human quality annotations were involved. The optional dense check actually ran CPU MiniLM and embedded Qdrant with two indexed candidates in a10,001-record SQL library.

## Correctness

- Method A/Method AB, TestMoE/TestMoE-XL and PIQA/PIQA-hard now remain insufficient rather than passing by substring. Explicit aliases and complete scientific names are matched; suffixes such as +, version hyphens and model sizes remain significant.
- A PPL column under a caption mentioning accuracy (%) now keeps score units. Ambiguous shared captions remain unknown. Units and metric identity use the addressed column before global caption text.
- An exhausted24,000-token input budget stops before provider creation. Estimates and measured usage share token units; context reserves output space. Known model tokenizers load/count off the event loop. Unknown models/tokenizer assets use a more conservative UTF-8 upper bound, which can reject some otherwise-fitting prompts. Failed calls with unavailable usage reserve budget, while reported usage/cost remains explicitly unknown. Provider-hidden retry billing is not presented as exact cost.

## Observed scaling

| Scenario | Before | After |
| --- | ---: | ---: |
|10k evidence, first index/request |1,142ms |1,578ms cold |
|10k evidence, cache hit |Every request rebuilt index |114ms warm |
|10k evidence,4 simultaneous requests |4,263ms each |218–231ms each, warm |
|Maximum loop lag,10k single request |1,036ms |46ms cold /15ms warm |
|Maximum loop lag,4 requests |3,421ms |15ms warm |
|10,001 evidence, BM25 / Dense |500 /500 |200 /200 |
|Average-bits filter over10k experiments |51 SQL statements |1 SQL statement |
|Average-bits filter,3-run median |1,584ms |60ms |

Each API scenario is one exploratory observation; filter and microbenchmark medians use3 repeats. Background load and cold/warm effects differ, so these are not controlled production latency/P95 claims. The initial index remains costly and was slower in this run. The improvement is index reuse, reduced SQL hydration and removal of synchronous CPU work from the event loop, not a new faster BM25 formula. The standalone uncached BM25 microbenchmark remains in the raw output.

Lexical indexes are keyed by database/user/library/paper/level and authoritative library revision. Ingestion-ready transitions, extraction commits, revisions and deletion increment that revision in the same SQL transaction. Replicas therefore invalidate their own process-local caches after committed changes. Cached ranks are always rehydrated through authorized ready-paper SQL records. The LRU keeps2 entries by default; lexical corpora are bounded by50,000 documents/32million characters and return422 with guidance when exceeded. Dense search has no lexical corpus cap and hydrates at most40 vector candidates. A single threaded cold-build lock bounds CPU; independent cold-library throughput remains a future scaling limit.

Average bits, bit width, method and architecture are pushed into SQL using indexed JSON expressions. The record JSON remains authoritative and numerical conditions still receive exact Decimal checks after SQL selection. SQLite EXPLAIN regression confirms the expression index is used; SQLite/Alembic cannot reflect these expression indexes for autogenerate comparison, so schema-check warnings do not replace that functional check. PostgreSQL migrations/filtering are also covered by the service CI gate.

## CPU deployment

The previous service CI completed in549s, of which495s were dependency installation. The old Linux lock included Torch/CUDA/NVIDIA/Triton wheel candidates estimated at2.79GiB compressed; that was not a Docker image measurement. The new lock contains no CUDA/NVIDIA/Triton packages and explicitly sources Linux torch/torchvision from the [official CPU index using uv sources](https://docs.astral.sh/uv/guides/integration/pytorch/). Windows/macOS retain their appropriate PyPI wheels. Dependency caching is enabled in CI; CI asserts `torch.version.cuda is None`. No replacement wall-time/image-size claim is made until a new job actually completes.

## Reproduce

```powershell
uv sync --project backend --extra dev --extra local --frozen --python 3.12
cd backend
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m pytest -q
cd ..
# With MiniLM already cached; omit HF_HUB_OFFLINE for first download.
$env:HF_HUB_OFFLINE='1'
.\backend\.venv\Scripts\python scripts/scaling_check.py --with-dense
```

The probe writes isolated system-temp data and output artifacts; it does not use the application's paper database. `--with-dense` is optional and uses the real local model. No browser/Docling/public-HTTPS/model-quality benchmark is implied by these measurements. Before/after raw output, CPU package locks, migration SQL and test output are included in the repository.
