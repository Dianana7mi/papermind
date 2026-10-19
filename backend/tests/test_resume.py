"""Resumable extraction uses synthetic table fixtures and an explicitly isolated model double."""

from decimal import Decimal

from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import Session
from app.models import Evidence, Experiment, Job, Paper, Revision, uid
from app.schemas import ExtractionBatch


async def setup_paper(client, auth, library):
    owner = (await client.get("/api/v1/auth/me", headers=auth)).json()["id"]
    async with Session() as db:
        paper = Paper(
            id=uid(),
            library_id=library,
            owner_id=owner,
            title="Synthetic resumable table",
            filename="test.pdf",
            sha256=uid().replace("-", "") * 2,
            status="ready",
        )
        db.add(paper)
        await db.flush()
        source = Evidence(
            id=uid(),
            paper_id=paper.id,
            library_id=library,
            owner_id=owner,
            page=1,
            section="Experiments",
            kind="table",
            text="Synthetic table",
            locator={
                "source_order": 0,
                "captions": ["TestMoE accuracy (%) on PIQA"],
                "cells": [
                    {"row": 0, "col": 1, "end_col": 2, "text": "PIQA", "column_header": True},
                    {"row": 1, "col": 0, "text": "Method A"},
                    {"row": 1, "col": 1, "text": "79.2"},
                    {"row": 2, "col": 0, "text": "Method B"},
                    {"row": 2, "col": 1, "text": "80.1"},
                ],
            },
        )
        db.add(source)
        await db.commit()
        return paper.id, source.id


async def test_resume_preserves_ids_corrections_and_deduplicates(
    client, auth, library, synthetic_record, monkeypatch
):
    import app.api.routes as routes
    import app.ingestion.pipeline as pipeline

    monkeypatch.setattr(settings(), "api_key", SecretStr("synthetic-test-provider"))
    calls = []

    async def test_model(self, schema, instruction, data):
        calls.append(data)
        records = []
        for cell in data["target_cells"]:
            r = synthetic_record.model_copy(deep=True)
            r.method_name = "Method A" if cell["row"] == 1 else "Method B"
            r.metric_value = Decimal(cell["original_value"])
            r.provenance.evidence_ids = [data["evidence"]["id"]]
            r.provenance.original_value = cell["original_value"]
            r.provenance.row_index = cell["row"]
            r.provenance.column_index = cell["col"]
            records.append(r)
        return ExtractionBatch(experiments=records)

    async def no_index(*args):
        pass

    monkeypatch.setattr(pipeline.ModelProvider, "structured", test_model)
    monkeypatch.setattr(pipeline, "index_documents", no_index)
    monkeypatch.setattr(routes, "index_documents", no_index)
    paper_id, source_id = await setup_paper(client, auth, library)
    response = await client.post(
        f"/api/v1/papers/{paper_id}/extract", headers=auth, json={"offset": 0, "limit": 1}
    )
    assert response.status_code == 202, response.text
    rows = (await client.get("/api/v1/experiments", headers=auth, params={"library_id": library})).json()[
        "items"
    ]
    assert len(rows) == 2
    ids = {r["id"] for r in rows}
    record = rows[0]["record"]
    record["additional_conditions"] = {"review_note": "human test correction retained"}
    edited = await client.patch(
        f"/api/v1/experiments/{rows[0]['id']}",
        headers=auth,
        json={"record": record, "reason": "Check synthetic source", "version": 1},
    )
    assert edited.status_code == 200, edited.text
    repeated = await client.post(
        f"/api/v1/papers/{paper_id}/extract", headers=auth, json={"offset": 0, "limit": 1}
    )
    assert repeated.status_code == 202
    assert len(calls) == 1  # known cells skip both new LLM calls and duplicate insertion
    async with Session() as db:
        saved = (await db.scalars(select(Experiment).where(Experiment.paper_id == paper_id))).all()
        assert {r.id for r in saved} == ids
        assert await db.scalar(select(func.count()).select_from(Revision)) == 1
        corrected = await db.get(Experiment, rows[0]["id"])
        assert corrected.record["additional_conditions"] == {"review_note": "human test correction retained"}
        assert corrected.version == 2
        assert (await db.get(Paper, paper_id)).extraction_lock is None
        assert await db.get(Evidence, source_id) is not None


async def test_failed_extraction_batch_releases_lease_without_losing_paper(
    client, auth, library, monkeypatch
):
    import app.ingestion.pipeline as pipeline

    monkeypatch.setattr(settings(), "api_key", SecretStr("synthetic-test-provider"))

    async def failing_model(*args, **kwargs):
        raise RuntimeError("explicit synthetic provider failure")

    async def no_index(*args):
        pass

    monkeypatch.setattr(pipeline.ModelProvider, "structured", failing_model)
    monkeypatch.setattr(pipeline, "index_documents", no_index)
    paper_id, _ = await setup_paper(client, auth, library)
    response = await client.post(
        f"/api/v1/papers/{paper_id}/extract", headers=auth, json={"offset": 0, "limit": 1}
    )
    assert response.status_code == 202
    async with Session() as db:
        paper = await db.get(Paper, paper_id)
        assert paper.status == "ready" and paper.extraction_lock is None
        job = await db.get(Job, response.json()["job_id"])
        assert job.details["failed_batches"] == [0]
        assert job.details["next_batch"] == 0


async def test_active_extraction_prevents_duplicate_job_and_delete(client, auth, library, monkeypatch):
    monkeypatch.setattr(settings(), "api_key", SecretStr("synthetic-test-provider"))
    paper_id, _ = await setup_paper(client, auth, library)
    async with Session() as db:
        paper = await db.get(Paper, paper_id)
        paper.extraction_lock = "active-test-lease"
        await db.commit()
    assert (
        await client.post(f"/api/v1/papers/{paper_id}/extract", headers=auth, json={"offset": 0, "limit": 1})
    ).status_code == 409
    assert (await client.delete(f"/api/v1/papers/{paper_id}", headers=auth)).status_code == 409
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Job)) == 0
