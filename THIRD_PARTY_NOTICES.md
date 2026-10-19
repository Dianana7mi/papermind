# Third-party notices and references

PaperMind's business code is independently implemented. Third-party dependencies are installed through their package managers rather than vendored. Their licenses remain applicable; package locks identify the exact resolved versions. Before distributing an image, include the dependency license texts required by those distributions.

Primary component sources:

- [FastAPI](https://github.com/fastapi/fastapi), [Pydantic](https://github.com/pydantic/pydantic), [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy), [Alembic](https://github.com/sqlalchemy/alembic), [Celery](https://github.com/celery/celery).
- [Qdrant and client](https://github.com/qdrant/qdrant), [Docling](https://github.com/docling-project/docling), [rank-bm25](https://github.com/dorianbrown/rank_bm25), [LangChain](https://github.com/langchain-ai/langchain), [LangGraph](https://github.com/langchain-ai/langgraph), [Langfuse](https://github.com/langfuse/langfuse-python).
- [Next.js](https://github.com/vercel/next.js), [React](https://github.com/facebook/react), [TanStack Query](https://github.com/TanStack/query), [Lucide](https://github.com/lucide-icons/lucide), [ReactMarkdown](https://github.com/remarkjs/react-markdown), [Playwright](https://github.com/microsoft/playwright).
- [PDF.js](https://github.com/mozilla/pdf.js) / `pdfjs-dist` renders source pages. Its worker is copied from the installed distribution during build, preserving the bundled license notice.
- CPU model downloads: [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), [ms-marco-TinyBERT-L2-v2](https://huggingface.co/cross-encoder/ms-marco-TinyBERT-L2-v2), Docling layout/table models identified by its installed package. Models have their own model-card licenses and are not republished here.
- PostgreSQL, Redis, Qdrant and Caddy container images retain their own distribution terms. In particular do not assume a single MIT project license relicenses all container software.

Public paper used in local verification: Lin et al., *AWQ: Activation-aware Weight Quantization for On-Device LLM Compression and Acceleration*, [arXiv:2306.00978](https://arxiv.org/abs/2306.00978). Original PDF stays in ignored local data. Source snippets in evaluation results are attributed to this paper and are for reproducibility; do not treat them as original PaperMind writing.

Reference products (not runtime dependencies): PaperQA2, Ai2 ScholarQA, OpenScholar, STORM, GPT Researcher. Citations, agentic retrieval and research synthesis already exist in these systems. PaperMind does not claim those capabilities as original innovations or claim benchmark superiority over them.
