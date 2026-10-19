import io

from conftest import account
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.core.db import Session
from app.models import Evidence, Experiment, Job, Paper, uid
from app.schemas import ExperimentRecord


def pdf_bytes():
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.setTitle("Synthetic fixture, NOT research evidence")
    pdf.drawString(60, 760, "Synthetic test paper - Experiments")
    pdf.drawString(60, 730, "Method A uses mixed precision quantization of expert weights.")
    pdf.drawString(60, 700, "TestMoE PIQA accuracy 79.2 percent with 2.5 average bits.")
    pdf.save()
    return output.getvalue()


async def test_auth_and_library_crud(client, auth, library):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=auth)).status_code == 200
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": "alice@example.org", "password": "wrong-password"}
        )
    ).status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.org", "password": "test-password-123"}
    )
    assert login.status_code == 200
    changed = await client.patch(f"/api/v1/libraries/{library}", headers=auth, json={"name": "Updated"})
    assert changed.json()["name"] == "Updated"
    assert (await client.get("/api/v1/libraries", headers=auth)).json()["items"]
    assert (await client.delete(f"/api/v1/libraries/{library}", headers=auth)).status_code == 204


async def test_cross_user_isolation(client, auth, library):
    bob = await account(client, "bob@example.org")
    assert (await client.get(f"/api/v1/libraries/{library}", headers=bob)).status_code == 404
    assert (
        await client.post(
            "/api/v1/search", headers=bob, json={"library_id": library, "query": "private", "mode": "bm25"}
        )
    ).status_code == 404
    assert (
        await client.get("/api/v1/experiments", headers=bob, params={"library_id": library})
    ).status_code == 404
    async with Session() as db:
        owner = (await client.get("/api/v1/auth/me", headers=auth)).json()["id"]
        paper = Paper(
            id=uid(),
            owner_id=owner,
            library_id=library,
            title="private",
            filename="private.pdf",
            sha256="a" * 64,
            status="ready",
        )
        db.add(paper)
        await db.commit()
    for suffix in ("", "/file", "/status"):
        assert (await client.get(f"/api/v1/papers/{paper.id}{suffix}", headers=bob)).status_code == 404


async def test_upload_rejects_invalid_and_paths(client, auth, library):
    response = await client.post(
        "/api/v1/papers/upload",
        headers=auth,
        data={"library_id": library},
        files={"file": ("x.pdf", b"not-a-pdf", "application/pdf")},
    )
    assert response.status_code == 415
    response = await client.post(
        "/api/v1/papers/upload",
        headers=auth,
        data={"library_id": library},
        files={"file": ("x.exe", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 415


async def test_end_to_end_real_pdf_with_explicit_test_model(client, auth, library, monkeypatch):
    """Real upload/parser/SQL/graph/SSE; embedding and extraction doubles are isolated to this test."""
    import app.ingestion.pipeline as pipeline
    import app.retrieval as retrieval
    from app.core.config import settings
    from app.schemas import ExtractionBatch
    from app.services.providers import ModelProvider

    cfg = settings()
    monkeypatch.setattr(cfg, "api_key", __import__("pydantic").SecretStr("synthetic-test-key"))

    async def test_embed(texts):
        return [[1.0, float("PIQA" in text), float("quantization" in text), 0.5] for text in texts]

    monkeypatch.setattr(retrieval, "embed", test_embed)

    async def test_structured(self, schema, instruction, data):
        if schema is ExtractionBatch:
            evidence = data["evidence"]
            return ExtractionBatch(
                experiments=[
                    ExperimentRecord(
                        method_name="Method A",
                        model_name="TestMoE",
                        dataset_name="PIQA",
                        metric_name="accuracy",
                        metric_value="79.2",
                        metric_unit="percent",
                        average_bits="2.5",
                        provenance={"evidence_ids": [evidence["id"]], "original_value": "79.2"},
                    )
                ]
            )
        raise RuntimeError("Explicit test model does not generate prose")

    monkeypatch.setattr(ModelProvider, "structured", test_structured)
    # The real pypdf backend has no section model; identify the fixture's experimental page explicitly for this isolated test.
    original_parser = pipeline.parse_pdf

    def test_parser(path):
        parsed = original_parser(path)
        for block in parsed.blocks:
            block.section = "Experiments (synthetic test label)"
        return parsed

    monkeypatch.setattr(pipeline, "parse_pdf", test_parser)
    response = await client.post(
        "/api/v1/papers/upload",
        headers=auth,
        data={"library_id": library},
        files={"file": ("../../fixture.pdf", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 202, response.text
    paper_id = response.json()["id"]
    paper = (await client.get(f"/api/v1/papers/{paper_id}", headers=auth)).json()
    assert paper["status"] == "ready", paper
    assert paper["filename"] == "fixture.pdf"
    # ReportLab embeds a timestamp/ID; use stored identical bytes to check dedup deterministically.
    raw_file = await client.get(f"/api/v1/papers/{paper_id}/file", headers=auth)
    assert raw_file.content.startswith(b"%PDF")
    duplicate = await client.post(
        "/api/v1/papers/upload",
        headers=auth,
        data={"library_id": library},
        files={"file": ("fixture.pdf", raw_file.content, "application/pdf")},
    )
    assert duplicate.json()["duplicate"] is True
    found = await client.post(
        "/api/v1/search",
        headers=auth,
        json={"library_id": library, "paper_id": paper_id, "query": "PIQA", "mode": "hybrid"},
    )
    assert found.status_code == 200, found.text
    evidence_id = found.json()["items"][0]["id"]
    assert (await client.get(f"/api/v1/evidence/{evidence_id}", headers=auth)).status_code == 200
    records = (await client.get("/api/v1/experiments", headers=auth, params={"library_id": library})).json()[
        "items"
    ]
    assert records
    assert records[0]["record"]["metric_value"] == "79.2"
    compare_result = (
        await client.post(
            "/api/v1/experiments/compare",
            headers=auth,
            json={"experiment_ids": [r["id"] for r in records[:2]]},
        )
        if len(records) >= 2
        else None
    )
    if compare_result:
        assert compare_result.json()["items"][0]["status"] == "INSUFFICIENT_INFORMATION"
    streamed = await client.post(
        "/api/v1/research/chat/stream",
        headers=auth,
        json={"library_id": library, "query": "What strategy is used?", "mode": "bm25"},
    )
    assert "event: done" in streamed.text
    assert "event: status" in streamed.text
    assert "api_key" not in streamed.text
    conversations = (
        await client.get("/api/v1/research/conversations", headers=auth, params={"library_id": library})
    ).json()["items"]
    messages = (
        await client.get(f"/api/v1/research/conversations/{conversations[0]['id']}", headers=auth)
    ).json()["items"]
    assert len(messages) == 2
    assert (await client.delete(f"/api/v1/papers/{paper_id}", headers=auth)).status_code == 204
    assert (await client.get(f"/api/v1/evidence/{evidence_id}", headers=auth)).status_code == 404
    async with Session() as db:
        assert await db.scalar(select(Experiment).where(Experiment.paper_id == paper_id)) is None
        assert await db.scalar(select(Evidence).where(Evidence.paper_id == paper_id)) is None
        assert await db.scalar(select(Job).where(Job.paper_id == paper_id)) is None


async def test_agent_failure_exits_budget(client, auth, library, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings(), "agent_max_tools", 1)
    response = await client.post(
        "/api/v1/research/chat",
        headers=auth,
        json={"library_id": library, "query": "Unknown question", "mode": "bm25"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["tool_count"] == 1
    assert len(response.json()["trace"]) <= 5
    assert response.json()["citations"] == []
    assert response.json()["trace_id"] == response.json()["usage"]["trace_id"]


async def test_no_secrets_in_validation(client):
    response = await client.post("/api/v1/auth/register", json={"email": "bad", "password": "SECRET"})
    assert response.status_code == 422
    assert "SECRET" not in response.text
    assert response.json()["error"]["request_id"]
