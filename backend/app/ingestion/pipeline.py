import asyncio
import hashlib
import json
import logging
from pathlib import Path

from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.db import Session
from app.experiments import align_record, canonical, parse_measurement
from app.ingestion.parser import chunk_section, parse_pdf
from app.models import Cleanup, Evidence, Experiment, Job, Paper, Revision, now, uid
from app.retrieval import delete_vectors, experiment_text, index_documents
from app.schemas import ExtractionBatch
from app.services.providers import ModelProvider, Usage

log = logging.getLogger("papermind.ingestion")


def extraction_units(sources: list[Evidence]) -> list[dict]:
    """Bound table output without losing header/cell associations or changing coordinates."""
    units = []
    for source in sources:
        data = evidence_dict(source)
        cells = source.locator.get("cells", [])
        if not cells:
            units.append({"evidence": data})
            continue
        measurements = []
        for cell in cells:
            if cell.get("column_header") or cell.get("row_header"):
                continue
            try:
                parse_measurement(cell["text"])
                measurements.append(cell)
            except ValueError:
                continue
        for offset in range(0, len(measurements), 6):
            targets = measurements[offset : offset + 6]
            rows = {c["row"] for c in targets}
            related = [c for c in cells if c.get("column_header") or c["row"] in rows]
            scoped = {
                **data,
                "text": "\n".join(source.locator.get("captions", [])),
                "locator": {**source.locator, "cells": related},
            }
            units.append(
                {
                    "evidence": scoped,
                    "target_cells": [
                        {"row": c["row"], "col": c["col"], "original_value": c["text"].strip()}
                        for c in targets
                    ],
                }
            )
    return units


def evidence_dict(e: Evidence) -> dict:
    return {
        "id": e.id,
        "paper_id": e.paper_id,
        "library_id": e.library_id,
        "owner_id": e.owner_id,
        "text": e.text,
        "page": e.page,
        "section": e.section,
        "kind": e.kind,
        "locator": e.locator,
    }


async def ingest(paper_id: str):
    async with Session() as db:
        claimed = await db.execute(
            update(Paper)
            .where(Paper.id == paper_id, Paper.status == "pending")
            .values(status="processing", error=None)
        )
        if not claimed.rowcount:
            await db.rollback()
            return
        paper = await db.get(Paper, paper_id)
        job = (
            await db.scalars(select(Job).where(Job.paper_id == paper_id).order_by(Job.created_at.desc()))
        ).first()
        if not job:
            job = Job(paper_id=paper_id)
            db.add(job)
        job.status, job.stage = "processing", "parsing"
        job.started_at = now()
        await db.commit()
        usage = Usage()
        try:
            parsed = await asyncio.to_thread(
                parse_pdf, settings().storage_path / "papers" / f"{paper_id}.pdf"
            )
            # Evidence replacement starts cleanly; bounded extraction commits each completed batch.
            await delete_vectors(paper_id)
            exp_ids = select(Experiment.id).where(Experiment.paper_id == paper_id)
            await db.execute(delete(Revision).where(Revision.experiment_id.in_(exp_ids)))
            await db.execute(delete(Experiment).where(Experiment.paper_id == paper_id))
            await db.execute(delete(Evidence).where(Evidence.paper_id == paper_id))
            paper.title = parsed.title
            paper.metadata_json = {"abstract": parsed.abstract, **parsed.metadata}
            sources = []
            for block_order, block in enumerate(parsed.blocks):
                pieces = [block.text] if block.kind == "table" else chunk_section(block.text)
                for chunk_order, text in enumerate(pieces):
                    evidence = Evidence(
                        id=uid(),
                        paper_id=paper.id,
                        library_id=paper.library_id,
                        owner_id=paper.owner_id,
                        kind=block.kind,
                        section=block.section,
                        page=block.page,
                        text=text,
                        locator={**block.locator, "source_order": block_order, "chunk_order": chunk_order},
                    )
                    db.add(evidence)
                    sources.append(evidence)
            await db.flush()
            job.stage = "extracting"
            await db.commit()
            experiments, extraction_info = await extract_range(db, paper, sources, usage)
            extraction_errors = extraction_info["warnings"]
            job.stage = "indexing"
            await db.commit()
            await index_documents(
                "paper",
                [
                    {
                        "id": paper.id,
                        "paper_id": paper.id,
                        "library_id": paper.library_id,
                        "owner_id": paper.owner_id,
                        "text": parsed.title + "\n" + parsed.abstract,
                    }
                ],
            )
            await index_documents("evidence", [evidence_dict(e) for e in sources])
            await index_documents(
                "experiment",
                [
                    {
                        "id": e.id,
                        "paper_id": e.paper_id,
                        "library_id": e.library_id,
                        "owner_id": e.owner_id,
                        "text": experiment_text(e.record),
                    }
                    for e in experiments
                ],
            )
            # If deletion raced processing, the FK/conditional update prevents resurrection.
            await db.refresh(paper)
            paper.status = "ready"
            job.status, job.stage = "completed", "done"
            job.details = {
                "evidence_count": len(sources),
                "experiment_count": len(experiments),
                "extraction_warnings": extraction_errors,
                "extraction": extraction_info,
                "usage": usage.export(),
            }
            await db.commit()
        except Exception as exc:
            await db.rollback()
            try:
                await delete_vectors(paper_id)
            except Exception:
                log.error("failed_index_cleanup", extra={"paper_id": paper_id})
            paper = await db.get(Paper, paper_id)
            if paper:
                paper.status, paper.error = (
                    "failed",
                    f"{type(exc).__name__}: processing failed; inspect worker diagnostics",
                )
                job = (
                    await db.scalars(
                        select(Job).where(Job.paper_id == paper_id).order_by(Job.created_at.desc())
                    )
                ).first()
                if job:
                    job.status, job.stage = "failed", "failed"
                    job.details = {"error_type": type(exc).__name__, "usage": usage.export()}
                await db.commit()
            log.error("ingestion_failed", extra={"paper_id": paper_id, "error_type": type(exc).__name__})
            raise


def measurement_key(record) -> str:
    p = record.provenance
    if p.row_index is not None and p.column_index is not None:
        identity = {"source": sorted(p.evidence_ids), "row": p.row_index, "col": p.column_index}
    else:
        identity = {
            "source": sorted(p.evidence_ids),
            **{
                key: canonical(getattr(record, key))
                for key in (
                    "method_name",
                    "model_name",
                    "dataset_name",
                    "metric_name",
                    "metric_value",
                    "metric_unit",
                )
            },
        }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()


def existing_measurements(rows):
    from app.schemas import ExperimentRecord

    return {
        measurement_key(ExperimentRecord.model_validate(data))
        for row in rows
        for data in (row.record, row.original_record)
    }


async def extract_range(db, paper, sources, usage, offset=0, limit=None, lock_id=None):
    paper_id = paper.id
    limit = settings().max_extraction_sources if limit is None else limit
    units = extraction_units(
        [
            e
            for e in sources
            if e.kind == "table"
            or any(
                word in (e.section or "").casefold()
                for word in ("experiment", "result", "evaluation", "ablation", "appendix")
            )
        ]
    )
    info = {
        "total_batches": len(units),
        "next_batch": offset,
        "failed_batches": [],
        "warnings": [],
        "attempted_batches": [],
        "remaining_batches": max(0, len(units) - offset),
    }
    if not settings().api_key:
        info["warnings"].append({"error": "Extraction pending: chat model not configured"})
        return [], info
    existing = (await db.scalars(select(Experiment).where(Experiment.paper_id == paper.id))).all()
    seen = existing_measurements(existing)
    source_map = {e.id: evidence_dict(e) for e in sources}
    provider = ModelProvider(usage)
    added = []
    added_ids = []
    for batch_index in range(offset, min(len(units), offset + limit)):
        unit = units[batch_index]
        source_id = unit["evidence"]["id"]
        if "target_cells" in unit:
            known_cells = {
                (i, r.record["provenance"].get("row_index"), r.record["provenance"].get("column_index"))
                for r in existing + added
                for i in r.record["provenance"]["evidence_ids"]
            }
            unit = {
                **unit,
                "target_cells": [
                    c for c in unit["target_cells"] if (source_id, c["row"], c["col"]) not in known_cells
                ],
            }
            if not unit["target_cells"]:
                info["next_batch"] = batch_index + 1
                continue
        info["attempted_batches"].append(batch_index)
        try:
            if len(unit["evidence"]["text"]) > 22000:
                raise ValueError("Oversized evidence requires manual review")
            batch = await provider.structured(
                ExtractionBatch,
                "Extract ONLY the supplied target_cells (at most one record per cell), or reported measurements from the paragraph. Copy exact original_value and numeric row_index/column_index. Preserve complete row/column headers, explicit metric units and statistics; do not combine methods. Omit unknown/default fields. Each record must cite the supplied evidence.id. Do not infer missing conditions or extract setup statistics as task performance. PPL is a score; accuracy is percent only when explicitly reported as such.",
                unit,
            )
            if (
                lock_id
                and await db.scalar(select(Paper.extraction_lock).where(Paper.id == paper.id)) != lock_id
            ):
                raise RuntimeError("Extraction lease no longer active")
            for record in batch.experiments:
                original = record.model_dump(mode="json")
                if not record.provenance.evidence_ids or set(record.provenance.evidence_ids) != {source_id}:
                    info["warnings"].append(
                        {"batch_index": batch_index, "error": "Invalid source ID in model extraction"}
                    )
                    continue
                aligned = align_record(record, source_map)
                if "target_cells" in unit and (
                    aligned.provenance.row_index,
                    aligned.provenance.column_index,
                ) not in {(c["row"], c["col"]) for c in unit["target_cells"]}:
                    info["warnings"].append(
                        {
                            "batch_index": batch_index,
                            "error": "Unaligned or out-of-batch cell requires review",
                        }
                    )
                    continue
                key = measurement_key(aligned)
                if key in seen:
                    continue
                seen.add(key)
                aligned.extraction_model = settings().chat_model
                aligned.source_type = "table" if unit["evidence"]["kind"] == "table" else "paragraph"
                aligned.experiment_id = uid()
                aligned.paper_id = paper.id
                data = aligned.model_dump(mode="json")
                row = Experiment(
                    id=aligned.experiment_id,
                    paper_id=paper.id,
                    library_id=paper.library_id,
                    owner_id=paper.owner_id,
                    fingerprint=key,
                    model_name=canonical(aligned.model_name),
                    dataset_name=canonical(aligned.dataset_name),
                    metric_name=canonical(aligned.metric_name),
                    record=data,
                    original_record=original,
                )
                db.add(row)
                added.append(row)
                added_ids.append(row.id)
            await db.commit()
            info["next_batch"] = batch_index + 1
        except Exception as exc:
            await db.rollback()
            # Keep already committed rows, and reload after a failed batch transaction.
            paper = await db.get(Paper, paper_id)
            added = (await db.scalars(select(Experiment).where(Experiment.id.in_(added_ids)))).all()
            existing = (await db.scalars(select(Experiment).where(Experiment.paper_id == paper_id))).all()
            seen = existing_measurements(existing)
            info["failed_batches"].append(batch_index)
            info["warnings"].append(
                {"batch_index": batch_index, "evidence_id": source_id, "error_type": type(exc).__name__}
            )
            if isinstance(exc, RuntimeError):
                if "lease" in str(exc):
                    raise
                info["next_batch"] = batch_index
                break
            info["next_batch"] = batch_index + 1
    info["remaining_batches"] = max(0, len(units) - info["next_batch"])
    return added, info


async def resume_extraction(job_id: str):
    async with Session() as db:
        claimed = await db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "pending")
            .values(status="processing", stage="extraction", started_at=now())
        )
        await db.commit()
        if not claimed.rowcount:
            return
        job = await db.get(Job, job_id)
        paper = await db.get(Paper, job.paper_id)
        if not paper or paper.extraction_lock != job_id:
            job.status = "failed"
            await db.commit()
            return
        parameters = job.details.copy()
        usage = Usage()
        try:
            sources = (
                await db.scalars(select(Evidence).where(Evidence.paper_id == paper.id).order_by(Evidence.id))
            ).all()
            # Stored source order is recovered from the initial source locator/page sequence below.
            sources.sort(
                key=lambda e: (
                    e.locator.get("source_order", e.page or 0),
                    e.locator.get("chunk_order", 0),
                    e.id,
                )
            )
            added, info = await extract_range(
                db, paper, sources, usage, parameters["offset"], parameters["limit"], job_id
            )
            rows = (await db.scalars(select(Experiment).where(Experiment.paper_id == paper.id))).all()
            await index_documents(
                "experiment",
                [
                    {
                        "id": r.id,
                        "paper_id": paper.id,
                        "library_id": paper.library_id,
                        "owner_id": paper.owner_id,
                        "text": experiment_text(r.record),
                    }
                    for r in rows
                ],
            )
            job = await db.get(Job, job_id)
            job.status = "completed"
            job.stage = "extraction_done"
            job.details = {**parameters, **info, "added_records": len(added), "usage": usage.export()}
        except Exception as exc:
            await db.rollback()
            job = await db.get(Job, job_id)
            job.status = "failed"
            job.details = {
                **parameters,
                "error_type": type(exc).__name__,
                "usage": usage.export(),
                "warning": "Committed SQL records retained; retry batch or reindex",
            }
        await db.execute(
            update(Paper)
            .where(Paper.id == job.paper_id, Paper.extraction_lock == job_id)
            .values(extraction_lock=None)
        )
        await db.commit()


async def cleanup():
    async with Session() as db:
        for item in (await db.scalars(select(Cleanup).where(Cleanup.done.is_(False)).limit(100))).all():
            await delete_vectors(item.paper_id)
            path: Path = settings().storage_path / "papers" / f"{item.paper_id}.pdf"
            path.unlink(missing_ok=True)
            item.done = True
        await db.commit()


async def reindex_paper(paper_id: str):
    async with Session() as db:
        paper = await db.get(Paper, paper_id)
        if not paper or paper.status != "ready":
            raise ValueError("Only ready papers can be reindexed")
        sources = (await db.scalars(select(Evidence).where(Evidence.paper_id == paper_id))).all()
        experiments = (await db.scalars(select(Experiment).where(Experiment.paper_id == paper_id))).all()
        common = {"paper_id": paper.id, "library_id": paper.library_id, "owner_id": paper.owner_id}
        await index_documents(
            "paper",
            [
                {
                    "id": paper.id,
                    "text": paper.title + "\n" + paper.metadata_json.get("abstract", ""),
                    **common,
                }
            ],
        )
        await index_documents("evidence", [evidence_dict(e) for e in sources])
        await index_documents(
            "experiment", [{"id": e.id, "text": experiment_text(e.record), **common} for e in experiments]
        )
