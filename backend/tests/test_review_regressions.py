"""Regression fixtures are synthetic; no live providers or application data are used."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_evaluation import source_fixture
from test_resume import setup_paper

from app.agents.research import query_experiments
from app.core.db import Session, engine
from app.experiments import align_record, compare, verify_claim
from app.models import Experiment, Job, Paper, uid
from app.schemas import AtomicClaim, ExperimentFilters, ExperimentRecord


@pytest.mark.parametrize(
    "unit,value,expected",
    [
        ("score", "79.2", "contradicted"),
        ("fraction", "0.792", "supported"),
        ("percent", "79.2", "supported"),
    ],
)
def test_units_come_from_original_headers(synthetic_record, unit, value, expected):
    synthetic_record.metric_unit, synthetic_record.metric_value = unit, value
    aligned = align_record(synthetic_record, {"evidence-a": source_fixture()})
    assert aligned.verification_status == expected


def test_legacy_supported_record_is_rechecked(synthetic_record):
    synthetic_record.metric_unit = "score"
    claim = AtomicClaim(
        experiment_id="x",
        text="synthetic wrong unit",
        metric_value="79.2",
        metric_unit="score",
        evidence_ids=["evidence-a"],
    )
    result = verify_claim(claim, {"evidence-a": source_fixture()}, {"x": synthetic_record})
    assert result["status"] == "insufficient"


def test_missing_source_unit_cannot_certify_model_unit(synthetic_record):
    source = source_fixture()
    source["locator"]["captions"] = ["TestMoE accuracy"]
    assert align_record(synthetic_record, {"evidence-a": source}).verification_status == "insufficient"


def test_filled_but_unverified_conditions_are_not_comparable(synthetic_record):
    aligned = align_record(synthetic_record, {"evidence-a": source_fixture()})
    assert aligned.verification_status == "supported"
    assert "average_bits" not in aligned.field_verification
    assert "model_version" not in aligned.provenance.field_sources
    result = compare(aligned, aligned.model_copy(update={"experiment_id": "second"}))
    assert result["status"] == "INSUFFICIENT_INFORMATION"
    assert "average_bits" in result["missing"]
    assert next(c for c in result["conditions"] if c["field"] == "model_version")["left_evidence"] == []


async def test_review_confirmation_is_explicit_audited_and_retained(client, auth, library, monkeypatch):
    import app.api.routes as routes

    async def no_index(*args):
        pass

    monkeypatch.setattr(routes, "index_documents", no_index)
    paper_id, source_id = await setup_paper(client, auth, library)
    async with Session() as db:
        paper = await db.get(Paper, paper_id)
        record = ExperimentRecord(
            method_name="Method A",
            model_name="TestMoE",
            dataset_name="PIQA",
            metric_name="accuracy",
            metric_unit="percent",
            metric_value="79.2",
            average_bits="2.5",
            provenance={
                "evidence_ids": [source_id],
                "original_value": "79.2",
                "row_index": 1,
                "column_index": 1,
            },
        )
        data = record.model_dump(mode="json")
        row = Experiment(
            id=uid(),
            paper_id=paper_id,
            library_id=library,
            owner_id=paper.owner_id,
            fingerprint="review",
            record=data,
            original_record=data,
        )
        db.add(row)
        await db.commit()
    data["field_verification"] = {"average_bits": "reviewed"}
    response = await client.patch(
        f"/api/v1/experiments/{row.id}",
        headers=auth,
        json={"record": data, "version": 1, "reason": "Synthetic check without confirmation"},
    )
    assert response.status_code == 200
    assert "average_bits" not in response.json()["record"]["field_verification"]
    data = response.json()["record"]
    response = await client.patch(
        f"/api/v1/experiments/{row.id}",
        headers=auth,
        json={
            "record": data,
            "version": 2,
            "reason": "Explicit synthetic source review",
            "confirmed_fields": ["average_bits"],
        },
    )
    assert response.status_code == 200
    assert response.json()["record"]["field_verification"]["average_bits"] == "reviewed"
    data = response.json()["record"]
    response = await client.patch(
        f"/api/v1/experiments/{row.id}",
        headers=auth,
        json={"record": data, "version": 3, "reason": "Unchanged reviewed condition"},
    )
    assert response.json()["record"]["field_verification"]["average_bits"] == "reviewed"
    data = response.json()["record"]
    data["average_bits"] = "3"
    response = await client.patch(
        f"/api/v1/experiments/{row.id}",
        headers=auth,
        json={"record": data, "version": 4, "reason": "Changed value needs fresh review"},
    )
    assert "average_bits" not in response.json()["record"]["field_verification"]
    details = (await client.get(f"/api/v1/experiments/{row.id}", headers=auth)).json()
    assert len(details["revisions"]) == 4


async def test_filters_scan_beyond_old_cap_and_paginate(client, auth, library):
    paper_id, _ = await setup_paper(client, auth, library)
    async with Session() as db:
        paper = await db.get(Paper, paper_id)
        for i in range(1003):
            record = ExperimentRecord(bit_width="3" if i >= 1000 else "4").model_dump(mode="json")
            db.add(
                Experiment(
                    id=f"scan-{i:04}",
                    paper_id=paper_id,
                    library_id=library,
                    owner_id=paper.owner_id,
                    fingerprint=str(i),
                    record=record,
                    original_record=record,
                )
            )
        await db.commit()
    body = {"library_id": library, "bit_width": "3"}
    first = await client.post("/api/v1/search/experiments?limit=2", headers=auth, json=body)
    assert [r["id"] for r in first.json()["items"]] == ["scan-1000", "scan-1001"]
    assert first.json()["next_offset"] == 2
    second = await client.post("/api/v1/search/experiments?limit=2&offset=2", headers=auth, json=body)
    assert [r["id"] for r in second.json()["items"]] == ["scan-1002"]
    assert second.json()["next_offset"] is None


async def test_failed_papers_excluded_and_scope_applied_before_limit(client, auth, library):
    a, _ = await setup_paper(client, auth, library)
    b, _ = await setup_paper(client, auth, library)
    async with Session() as db:
        paper = await db.get(Paper, a)
        for i in range(35):
            record = ExperimentRecord().model_dump(mode="json")
            db.add(
                Experiment(
                    id=f"scope-{i:04}",
                    paper_id=a if i < 34 else b,
                    library_id=library,
                    owner_id=paper.owner_id,
                    fingerprint=str(i),
                    record=record,
                    original_record=record,
                )
            )
        await db.commit()
        rows = await query_experiments(
            db, paper.owner_id, ExperimentFilters(library_id=library), limit=30, paper_ids=[b]
        )
        assert [r.id for r in rows] == ["scope-0034"]
        (await db.get(Paper, b)).status = "failed"
        await db.commit()
        assert (
            await query_experiments(db, paper.owner_id, ExperimentFilters(library_id=library, paper_id=b))
            == []
        )


async def test_ingestion_claim_and_job_are_one_transaction(client, auth, library, monkeypatch):
    import app.ingestion.pipeline as pipeline

    paper_id, _ = await setup_paper(client, auth, library)
    async with Session() as db:
        (await db.get(Paper, paper_id)).status = "pending"
        db.add(Job(id="crash-job", paper_id=paper_id))
        await db.commit()

    class SimulatedProcessExit(BaseException):
        pass

    class InterruptedSession(AsyncSession):
        async def commit(self):
            job = await self.get(Job, "crash-job")
            assert job.status == "processing" and job.started_at is not None
            raise SimulatedProcessExit()

    monkeypatch.setattr(
        pipeline, "Session", async_sessionmaker(engine, class_=InterruptedSession, expire_on_commit=False)
    )
    with pytest.raises(SimulatedProcessExit):
        await pipeline.ingest(paper_id)
    async with Session() as db:
        assert (await db.get(Paper, paper_id)).status == "pending"
        assert (await db.get(Job, "crash-job")).status == "pending"


async def test_scheduler_recovers_legacy_orphan_claim(client, auth, library, monkeypatch):
    from app import tasks

    paper_id, _ = await setup_paper(client, auth, library)
    async with Session() as db:
        (await db.get(Paper, paper_id)).status = "processing"
        db.add(Job(id="legacy-orphan", paper_id=paper_id))
        await db.commit()
    monkeypatch.setattr(tasks.ingest_task, "delay", lambda *args: None)
    monkeypatch.setattr(tasks.extraction_task, "delay", lambda *args: None)
    await asyncio.to_thread(tasks.recover_jobs.run)
    async with Session() as db:
        assert (await db.get(Paper, paper_id)).status == "failed"
        assert (await db.get(Job, "legacy-orphan")).status == "failed"
