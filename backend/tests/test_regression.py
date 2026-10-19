import io

from conftest import account
from httpx import ASGITransport, AsyncClient
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import Session
from app.main import app
from app.models import Evidence, Experiment, Library, Paper, uid


async def test_revision_keeps_original_and_optimistic_version(
    client, auth, library, synthetic_record, monkeypatch
):
    import app.api.routes as routes

    async def no_index(*args):
        return None

    monkeypatch.setattr(routes, "index_documents", no_index)
    user_id = (await client.get("/api/v1/auth/me", headers=auth)).json()["id"]
    async with Session() as db:
        paper = Paper(
            id=uid(),
            library_id=library,
            owner_id=user_id,
            title="synthetic",
            filename="a.pdf",
            sha256="0" * 64,
            status="ready",
        )
        db.add(paper)
        await db.flush()
        source = Evidence(
            id=uid(),
            paper_id=paper.id,
            library_id=library,
            owner_id=user_id,
            kind="paragraph",
            section="Experiments",
            page=1,
            text="Method A 79.2",
            locator={},
        )
        db.add(source)
        synthetic_record.experiment_id, synthetic_record.paper_id = uid(), paper.id
        synthetic_record.provenance.evidence_ids = [source.id]
        record = synthetic_record.model_dump(mode="json")
        row = Experiment(
            id=synthetic_record.experiment_id,
            paper_id=paper.id,
            library_id=library,
            owner_id=user_id,
            fingerprint="1" * 64,
            record=record,
            original_record=record,
        )
        db.add(row)
        await db.commit()
    changed = {**record, "method_name": "Corrected method"}
    response = await client.patch(
        f"/api/v1/experiments/{row.id}",
        headers=auth,
        json={"record": changed, "reason": "Synthetic review correction", "version": 1},
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    detail = (await client.get(f"/api/v1/experiments/{row.id}", headers=auth)).json()
    assert detail["original_record"]["method_name"] == "Method A"
    assert detail["revisions"][0]["before"]["method_name"] == "Method A"
    assert detail["revisions"][0]["after"]["method_name"] == "Corrected method"
    stale = await client.patch(
        f"/api/v1/experiments/{row.id}",
        headers=auth,
        json={"record": changed, "reason": "Stale version", "version": 1},
    )
    assert stale.status_code == 409
    bob = await account(client, "bob@example.org")
    assert (await client.get(f"/api/v1/experiments/{row.id}", headers=bob)).status_code == 404
    assert (
        await client.post(
            "/api/v1/experiments/compare", headers=bob, json={"experiment_ids": [row.id, uid()]}
        )
    ).status_code == 404


async def test_local_qdrant_scope_and_delete(client, auth, library, monkeypatch):
    import app.retrieval as retrieval

    async def fixture_embed(texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(retrieval, "embed", fixture_embed)
    owner = (await client.get("/api/v1/auth/me", headers=auth)).json()["id"]
    bob_auth = await account(client, "bob@example.org")
    bob = (await client.get("/api/v1/auth/me", headers=bob_auth)).json()["id"]
    async with Session() as db:
        bob_library = Library(id=uid(), owner_id=bob, name="Private B")
        db.add(bob_library)
        await db.flush()
        paper_a = Paper(
            id=uid(),
            owner_id=owner,
            library_id=library,
            title="A",
            filename="a.pdf",
            sha256="a" * 64,
            status="ready",
        )
        paper_b = Paper(
            id=uid(),
            owner_id=bob,
            library_id=bob_library.id,
            title="B",
            filename="b.pdf",
            sha256="b" * 64,
            status="ready",
        )
        db.add_all([paper_a, paper_b])
        await db.flush()
        sources = [
            Evidence(
                id=uid(),
                owner_id=owner,
                library_id=library,
                paper_id=paper_a.id,
                text="private A quantization",
                kind="paragraph",
            ),
            Evidence(
                id=uid(),
                owner_id=bob,
                library_id=bob_library.id,
                paper_id=paper_b.id,
                text="private B quantization",
                kind="paragraph",
            ),
        ]
        db.add_all(sources)
        await db.commit()
    from app.ingestion.pipeline import evidence_dict

    await retrieval.index_documents("evidence", [evidence_dict(e) for e in sources])
    result = await client.post(
        "/api/v1/search", headers=auth, json={"library_id": library, "query": "quantization", "mode": "dense"}
    )
    assert [e["id"] for e in result.json()["items"]] == [sources[0].id]
    assert (await client.delete(f"/api/v1/papers/{paper_a.id}", headers=auth)).status_code == 204
    result = await client.post(
        "/api/v1/search", headers=auth, json={"library_id": library, "query": "quantization", "mode": "dense"}
    )
    assert result.json()["items"] == []
    points = retrieval.vector_client().scroll(retrieval.vector_collection("evidence"), limit=1000)[0]
    assert all(str(p.id) != sources[0].id for p in points)


async def test_extraction_retry_is_idempotent(client, auth, library, monkeypatch):
    import app.ingestion.pipeline as pipeline
    import app.retrieval as retrieval

    async def fixture_embed(texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(retrieval, "embed", fixture_embed)
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(60, 750, "Synthetic retry fixture quantization")
    pdf.save()
    uploaded = await client.post(
        "/api/v1/papers/upload",
        headers=auth,
        data={"library_id": library},
        files={"file": ("fixture.pdf", output.getvalue(), "application/pdf")},
    )
    paper_id = uploaded.json()["id"]
    async with Session() as db:
        first = len((await db.scalars(select(Evidence).where(Evidence.paper_id == paper_id))).all())
    await pipeline.ingest(paper_id)
    await pipeline.ingest(paper_id)
    async with Session() as db:
        assert len((await db.scalars(select(Evidence).where(Evidence.paper_id == paper_id))).all()) == first
    assert (await client.post(f"/api/v1/papers/{paper_id}/retry", headers=auth)).status_code == 409
    assert (await client.post(f"/api/v1/papers/{paper_id}/reindex", headers=auth)).status_code == 200


def test_production_rejects_unsafe_defaults():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(environment="production")


async def test_chunked_oversized_body_rejected():
    async def chunks():
        for _ in range(4):
            yield b" " * (512 * 1024)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login", content=chunks(), headers={"Content-Type": "application/json"}
        )
        assert response.status_code in (400, 413)


async def test_query_fields_whitelist(client, auth, library):
    response = await client.post(
        "/api/v1/search/experiments", headers=auth, json={"library_id": library, "sql": "SELECT * FROM users"}
    )
    assert response.status_code == 422
