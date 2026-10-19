# Resume descriptions

## 中文

**PaperMind｜基于实验感知 RAG 与证据校验的科研分析平台**

- 使用 FastAPI、Next.js、SQLAlchemy、LangGraph 与 Qdrant 构建论文上传、检索、结构化实验探索、条件比较和引用溯源的全栈系统；提供 PostgreSQL/Redis/Celery/Caddy 部署配置与资源级用户隔离。
- 自主实现实验 Schema、显式单位规范化、多级表头证据关联、可配置可比性规则和声明校验；未知条件保留 null，不将不同平均位宽结果宣称为等预算比较。
- 实现 Dense/BM25/RRF/CrossEncoder 检索及可复现评测；在 1 篇真实 AWQ 论文、12 道 Agent 来源锚点问题的试评测中，Hybrid MRR 为 0.7562（Dense 0.5343）。该试评测无人工金标准，不主张普遍性能提升。
- 真实模型烟测完成 Docling → 检索 → 回答 → 原 PDF 引用；提供自动化安全/规则/故障测试、浏览器流程、运行记录与未验证部署项清单。

## English

**PaperMind — Evidence-Grounded Research Intelligence Agent**

- Built a full-stack scientific-paper workspace with FastAPI, Next.js, SQLAlchemy, Qdrant and a bounded LangGraph workflow, covering PDF ingestion, hybrid retrieval, structured experiments, explainable comparison and source citations.
- Implemented explicit-unit measurement normalization, table-cell provenance alignment, configurable comparability rules, claim checks, resource-level authorization and audited human corrections.
- Added reproducible Dense/BM25/RRF/CrossEncoder evaluation. On a one-paper, 12-query agent-labeled source-anchor pilot, hybrid MRR was 0.7562 versus 0.5343 for dense retrieval; disclosed incomplete relevance labels and no human gold standard.
- Verified a real Docling/local-model/DeepSeek RAG flow and browser citation/comparison interactions; supplied production Compose/migration/service-gate code while documenting the unavailable local Docker engine.

## Claims to avoid

Do not claim academic novelty, 30-paper/150-record human annotation completion, a production public deployment, remote Langfuse validation, universal retrieval gains, field extraction accuracy without gold data, or fabricated throughput/cost reductions. Update the test count from `docs/verification/backend-tests.txt` if using a numeric count in an interview.
