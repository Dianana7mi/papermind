"""Real production-service integration gate. Requires running Postgres/Redis/Qdrant/Celery.

Run from backend using its Python after migrations and worker startup.
Synthetic PDF is explicitly test input, not a research experiment or benchmark label.
"""

import asyncio
import io
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from httpx import ASGITransport, AsyncClient  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


async def main():
    cfg = settings()
    assert cfg.database_url.startswith("postgresql"), "Service gate requires real PostgreSQL"
    assert cfg.qdrant_url and not cfg.task_eager, "Service gate requires remote Qdrant and worker queue"
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ready = await client.get("/health/ready")
            ready.raise_for_status()
            auth = await client.post(
                "/api/v1/auth/register",
                json={"email": f"service-{uuid.uuid4().hex[:8]}@example.org", "password": uuid.uuid4().hex},
            )
            auth.raise_for_status()
            client.headers["Authorization"] = "Bearer " + auth.json()["access_token"]
            library = await client.post(
                "/api/v1/libraries", json={"name": "Synthetic service integration gate"}
            )
            library.raise_for_status()
            library_id = library.json()["id"]
            buffer = io.BytesIO()
            pdf = canvas.Canvas(buffer)
            pdf.drawString(50, 750, "SYNTHETIC SERVICE TEST: quantization evidence retrieval")
            pdf.save()
            paper = await client.post(
                "/api/v1/papers/upload",
                data={"library_id": library_id},
                files={"file": ("service-fixture.pdf", buffer.getvalue(), "application/pdf")},
            )
            paper.raise_for_status()
            paper_id = paper.json()["id"]
            for _ in range(90):
                status = await client.get(f"/api/v1/papers/{paper_id}/status")
                status.raise_for_status()
                if status.json()["status"] in ("ready", "failed"):
                    break
                await asyncio.sleep(2)
            assert status.json()["status"] == "ready", status.text
            for mode in ("bm25", "dense", "hybrid"):
                found = await client.post(
                    "/api/v1/search",
                    json={"library_id": library_id, "query": "quantization evidence retrieval", "mode": mode},
                )
                found.raise_for_status()
                assert found.json()["items"], mode
            pdf_response = await client.get(f"/api/v1/papers/{paper_id}/file")
            assert pdf_response.content.startswith(b"%PDF")
            deleted = await client.delete(f"/api/v1/libraries/{library_id}")
            assert deleted.status_code == 204, deleted.text
            assert (await client.get(f"/api/v1/papers/{paper_id}")).status_code == 404
    print(
        json.dumps(
            {
                "service_gate": "PASS",
                "services": ["PostgreSQL", "Redis", "Celery", "Qdrant"],
                "input": "explicitly synthetic PDF, no accuracy claims",
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
