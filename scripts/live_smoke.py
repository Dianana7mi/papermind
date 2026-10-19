"""Real public-paper/Docling/local models/API smoke. Run from backend with its Python.

    .venv/Scripts/python ../scripts/live_smoke.py --deepseek
No API key or auth token is written to results. This invokes the configured paid model.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
parser = argparse.ArgumentParser()
parser.add_argument(
    "--deepseek", action="store_true", help="Use the existing DEEPSEEK_API_KEY process variable"
)
parser.add_argument("--pdf", default="data/public/awq.pdf")
parser.add_argument("--output", default="live-smoke.json")
parser.add_argument("--resume", action="store_true", help="Check idempotent retry and a new extraction batch")
args = parser.parse_args()
if args.deepseek:
    os.environ["PM_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
    os.environ["PM_BASE_URL"] = "https://api.deepseek.com/v1"
    os.environ["PM_CHAT_MODEL"] = "deepseek-chat"
os.environ.setdefault("PM_MAX_EXTRACTION_SOURCES", "3")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


async def main():
    if not settings().api_key:
        raise RuntimeError("Configure PM_API_KEY or use --deepseek with an existing environment key")
    result = {
        "source": "https://arxiv.org/abs/2306.00978",
        "dataset_scope": "one real public AWQ paper; agent-curated smoke, no human labels",
        "model": settings().chat_model,
        "parser": settings().parser,
        "steps": {},
    }
    started = time.perf_counter()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost", timeout=900
        ) as client:

            async def call(method, path, **kwargs):
                response = await client.request(method, "/api/v1" + path, **kwargs)
                response.raise_for_status()
                return response.json()

            auth = await call(
                "POST",
                "/auth/register",
                json={"email": f"smoke-{uuid.uuid4().hex[:8]}@example.org", "password": uuid.uuid4().hex},
            )
            client.headers["Authorization"] = "Bearer " + auth["access_token"]
            library = await call(
                "POST", "/libraries", json={"name": "AWQ live smoke " + uuid.uuid4().hex[:6]}
            )
            pdf = Path(args.pdf)
            paper = await call(
                "POST",
                "/papers/upload",
                data={"library_id": library["id"]},
                files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
            )
            status = await call("GET", f"/papers/{paper['id']}/status")
            result["steps"]["upload_ingestion"] = status
            result["paper_id"], result["library_id"] = paper["id"], library["id"]
            if status["status"] != "ready":
                raise RuntimeError("Real PDF ingestion failed; see persisted job status")
            experiments = await call(
                "GET", "/experiments", params={"library_id": library["id"], "limit": 100}
            )
            result["experiment_count"] = len(experiments["items"])
            result["experiments"] = experiments["items"]
            if args.resume:
                previous = {e["id"] for e in experiments["items"]}
                await call("POST", f"/papers/{paper['id']}/extract", json={"offset": 0, "limit": 1})
                repeated = await call(
                    "GET", "/experiments", params={"library_id": library["id"], "limit": 100}
                )
                assert {e["id"] for e in repeated["items"]} == previous
                await call("POST", f"/papers/{paper['id']}/extract", json={"offset": 3, "limit": 1})
                extended = await call(
                    "GET", "/experiments", params={"library_id": library["id"], "limit": 100}
                )
                assert previous <= {e["id"] for e in extended["items"]}
                result["resume"] = {
                    "before": len(previous),
                    "after_repeat": len(repeated["items"]),
                    "after_new_batch": len(extended["items"]),
                    "preserved_original_ids": True,
                    "status": await call("GET", f"/papers/{paper['id']}/status"),
                }
                result["experiments_after_resume"] = extended["items"]
            question = "What is the key idea behind activation-aware weight quantization (AWQ)?"
            for mode in ("dense", "bm25", "hybrid", "rerank"):
                found = await call(
                    "POST",
                    "/search",
                    json={"library_id": library["id"], "query": question, "mode": mode, "top_k": 5},
                )
                result["steps"][mode] = {
                    "count": len(found["items"]),
                    "timing": found["timing"],
                    "ids": [e["id"] for e in found["items"]],
                }
            answer = await call(
                "POST",
                "/research/chat",
                json={"library_id": library["id"], "query": question, "mode": "hybrid", "top_k": 4},
            )
            result["steps"]["real_model_rag"] = answer
            result["steps"]["citation_files"] = []
            for citation in answer["citations"]:
                response = await client.get(f"/api/v1/papers/{citation['paper_id']}/file")
                result["steps"]["citation_files"].append(
                    {
                        "status": response.status_code,
                        "is_pdf": response.content.startswith(b"%PDF"),
                        "page": citation["page"],
                    }
                )
    result["total_seconds"] = time.perf_counter() - started
    output = ROOT / "evaluation/results" / Path(args.output).name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "result": str(output),
                "seconds": result["total_seconds"],
                "experiments": result["experiment_count"],
                "claims": len(result["steps"]["real_model_rag"]["verification"]),
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
