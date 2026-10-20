import asyncio
import hashlib
import io
import itertools
import json
import logging
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
from pypdf import PdfReader
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.agents.research import query_experiments, run_agent
from app.core.config import settings
from app.core.security import DB, Auth, passwords, token_for
from app.experiments import ComparisonRules, align_record, canonical, compare
from app.ingestion.pipeline import cleanup, evidence_dict, ingest, reindex_paper, resume_extraction
from app.models import (
    Cleanup,
    Conversation,
    EvaluationRun,
    Evidence,
    Experiment,
    Job,
    Library,
    Message,
    Paper,
    PublicReference,
    Revision,
    User,
    touch_library,
    uid,
)
from app.retrieval import experiment_text, index_documents, retrieval_metrics, search
from app.schemas import (
    ChatInput,
    ComparisonInput,
    Credentials,
    EvaluationInput,
    ExperimentFilters,
    ExperimentRecord,
    ExtractionRequest,
    LibraryInput,
    PublicImport,
    RevisionInput,
    SearchInput,
)
from app.services.public_search import public_search, public_work

router = APIRouter(prefix="/api/v1")
log = logging.getLogger("papermind.api")


async def owned(db, entity, entity_id, user_id):
    owner = entity.owner_id
    row = await db.scalar(select(entity).where(entity.id == entity_id, owner == user_id))
    if row is None:
        raise HTTPException(404, "Resource not found")
    return row


def paper_out(p):
    metadata = {k: v for k, v in p.metadata_json.items() if k != "document"}
    return {
        "id": p.id,
        "library_id": p.library_id,
        "title": p.title,
        "filename": p.filename,
        "status": p.status,
        "error": p.error,
        "metadata": metadata,
        "created_at": p.created_at,
    }


def library_out(row):
    return {"id": row.id, "name": row.name, "description": row.description, "created_at": row.created_at}


@router.post("/auth/register", status_code=201)
async def register(body: Credentials, db: DB):
    user = User(
        email=body.email.casefold(), password_hash=await asyncio.to_thread(passwords.hash, body.password)
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Email is already registered") from None
    return {"access_token": token_for(user.id), "token_type": "bearer"}


@router.post("/auth/login")
async def login(body: Credentials, db: DB):
    user = await db.scalar(select(User).where(User.email == body.email.casefold()))
    # Hash a dummy value too, reducing account-existence timing leakage.
    if user:
        valid = await asyncio.to_thread(passwords.verify, body.password, user.password_hash)
    else:
        await asyncio.to_thread(passwords.hash, body.password)
        valid = False
    if not valid:
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": token_for(user.id), "token_type": "bearer"}


@router.get("/auth/me")
async def me(user: Auth):
    return {"id": user.id, "email": user.email}


@router.get("/libraries")
async def libraries(db: DB, user: Auth, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    rows = (
        await db.scalars(
            select(Library)
            .where(Library.owner_id == user.id)
            .order_by(Library.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {"items": [library_out(r) for r in rows]}


@router.post("/libraries", status_code=201)
async def add_library(body: LibraryInput, db: DB, user: Auth):
    row = Library(owner_id=user.id, **body.model_dump())
    db.add(row)
    await db.commit()
    return library_out(row)


@router.get("/libraries/{library_id}")
async def get_library(library_id: str, db: DB, user: Auth):
    return library_out(await owned(db, Library, library_id, user.id))


@router.patch("/libraries/{library_id}")
async def edit_library(library_id: str, body: LibraryInput, db: DB, user: Auth):
    row = await owned(db, Library, library_id, user.id)
    row.name, row.description = body.name, body.description
    await db.commit()
    return library_out(row)


async def delete_paper_rows(db, paper):
    if paper.status == "processing" or paper.extraction_lock:
        raise HTTPException(409, "Paper is processing; retry deletion after the job finishes")
    await db.execute(
        delete(Revision).where(
            Revision.experiment_id.in_(select(Experiment.id).where(Experiment.paper_id == paper.id))
        )
    )
    for entity in (Experiment, Evidence, Job):
        await db.execute(delete(entity).where(entity.paper_id == paper.id))
    db.add(Cleanup(paper_id=paper.id))
    await touch_library(db, paper.library_id)
    await db.delete(paper)


@router.delete("/libraries/{library_id}", status_code=204)
async def remove_library(library_id: str, db: DB, user: Auth, background: BackgroundTasks):
    row = await owned(db, Library, library_id, user.id)
    papers = (await db.scalars(select(Paper).where(Paper.library_id == library_id))).all()
    for paper in papers:
        await delete_paper_rows(db, paper)
    await db.execute(
        delete(Message).where(
            Message.conversation_id.in_(select(Conversation.id).where(Conversation.library_id == library_id))
        )
    )
    await db.execute(delete(Conversation).where(Conversation.library_id == library_id))
    await db.execute(delete(EvaluationRun).where(EvaluationRun.library_id == library_id))
    await db.execute(delete(PublicReference).where(PublicReference.library_id == library_id))
    await db.delete(row)
    await db.commit()
    background.add_task(safe_cleanup)


async def safe_cleanup():
    try:
        await cleanup()
    except Exception as exc:
        log.error("cleanup_pending", extra={"error_type": type(exc).__name__})


async def safe_ingest(paper_id):
    try:
        await ingest(paper_id)
    except Exception:
        pass  # pipeline persisted the failed job; a background exception must not alter the upload response


def schedule_ingest(paper_id, background):
    if settings().task_eager:
        background.add_task(safe_ingest, paper_id)
    else:
        from app.tasks import ingest_task

        ingest_task.delay(paper_id)


@router.post("/papers/upload", status_code=202)
async def upload(
    db: DB, user: Auth, background: BackgroundTasks, library_id: str = Form(), file: UploadFile = File()
):
    await owned(db, Library, library_id, user.id)
    if file.content_type != "application/pdf" or not (file.filename or "").casefold().endswith(".pdf"):
        raise HTTPException(415, "Only application/pdf files are accepted")
    content = bytearray()
    while piece := await file.read(1024 * 1024):
        content.extend(piece)
        if len(content) > settings().max_upload_mb * 1024 * 1024:
            raise HTTPException(413, "PDF exceeds configured size limit")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(415, "Invalid PDF signature")
    try:
        reader = await asyncio.to_thread(PdfReader, io.BytesIO(content))
        if reader.is_encrypted or not 0 < len(reader.pages) <= settings().max_pages:
            raise ValueError("Encrypted, empty or oversized page count")
    except Exception:
        raise HTTPException(422, "PDF is unreadable, encrypted, empty or has too many pages") from None
    digest = hashlib.sha256(content).hexdigest()
    existing = await db.scalar(select(Paper).where(Paper.library_id == library_id, Paper.sha256 == digest))
    if existing:
        return {**paper_out(existing), "duplicate": True}
    name = Path((file.filename or "paper.pdf").replace("\\", "/")).name[:255]
    paper = Paper(
        id=uid(), owner_id=user.id, library_id=library_id, title=name[:-4], filename=name, sha256=digest
    )
    path = settings().storage_path / "papers" / f"{paper.id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, content)
    db.add(paper)
    try:
        await db.flush()
        db.add(Job(paper_id=paper.id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        path.unlink(missing_ok=True)
        existing = await db.scalar(
            select(Paper).where(Paper.library_id == library_id, Paper.sha256 == digest)
        )
        if existing:
            return {**paper_out(existing), "duplicate": True}
        raise
    try:
        schedule_ingest(paper.id, background)
    except Exception:
        paper.status, paper.error = "failed", "Worker broker unavailable; retry processing"
        await db.commit()
    return paper_out(paper)


@router.get("/papers")
async def papers(
    db: DB, user: Auth, library_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
):
    await owned(db, Library, library_id, user.id)
    rows = (
        await db.scalars(
            select(Paper)
            .where(Paper.owner_id == user.id, Paper.library_id == library_id)
            .order_by(Paper.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {"items": [paper_out(p) for p in rows]}


@router.get("/papers/{paper_id}")
async def paper_detail(paper_id: str, db: DB, user: Auth):
    paper = await owned(db, Paper, paper_id, user.id)
    sections = (
        await db.execute(
            select(Evidence.section, func.count())
            .where(Evidence.paper_id == paper_id)
            .group_by(Evidence.section)
        )
    ).all()
    return {
        **paper_out(paper),
        "sections": [{"name": name, "evidence_count": count} for name, count in sections],
    }


@router.get("/papers/{paper_id}/status")
async def paper_status(paper_id: str, db: DB, user: Auth):
    paper = await owned(db, Paper, paper_id, user.id)
    jobs = (
        await db.scalars(select(Job).where(Job.paper_id == paper_id).order_by(Job.created_at.desc()))
    ).all()
    return {
        "status": paper.status,
        "error": paper.error,
        "jobs": [{"id": j.id, "status": j.status, "stage": j.stage, "details": j.details} for j in jobs],
    }


@router.post("/papers/{paper_id}/retry", status_code=202)
async def retry_paper(paper_id: str, db: DB, user: Auth, background: BackgroundTasks):
    paper = await owned(db, Paper, paper_id, user.id)
    if paper.status != "failed":
        raise HTTPException(409, "Only failed papers may be retried")
    paper.status, paper.error = "pending", None
    db.add(Job(paper_id=paper_id))
    await db.commit()
    schedule_ingest(paper_id, background)
    return {"status": "pending"}


@router.get("/papers/{paper_id}/file")
async def paper_file(paper_id: str, db: DB, user: Auth):
    paper = await owned(db, Paper, paper_id, user.id)
    path = settings().storage_path / "papers" / f"{paper.id}.pdf"
    if not path.is_file():
        raise HTTPException(404, "PDF file unavailable")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=paper.filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/papers/{paper_id}/reindex")
async def reindex(paper_id: str, db: DB, user: Auth):
    await owned(db, Paper, paper_id, user.id)
    await reindex_paper(paper_id)
    return {"status": "reindexed"}


@router.post("/papers/{paper_id}/extract", status_code=202)
async def continue_extraction(
    paper_id: str, body: ExtractionRequest, db: DB, user: Auth, background: BackgroundTasks
):
    paper = await owned(db, Paper, paper_id, user.id)
    if not settings().api_key:
        raise HTTPException(503, "Configure the extraction model before continuing")
    job = Job(
        id=uid(),
        paper_id=paper.id,
        stage="extraction_queued",
        details={"kind": "extraction", "offset": body.offset, "limit": body.limit},
    )
    db.add(job)
    claimed = await db.execute(
        update(Paper)
        .where(Paper.id == paper.id, Paper.status == "ready", Paper.extraction_lock.is_(None))
        .values(extraction_lock=job.id)
    )
    if not claimed.rowcount:
        await db.rollback()
        raise HTTPException(409, "Paper must be ready and have no active extraction job")
    await db.commit()
    if settings().task_eager:
        background.add_task(resume_extraction, job.id)
    else:
        try:
            from app.tasks import extraction_task

            extraction_task.delay(job.id)
        except Exception:
            # The committed pending job is redispatched by the scheduler.
            return {
                "job_id": job.id,
                "status": "pending",
                "warning": "Broker unavailable; durable job awaits scheduler recovery",
            }
    return {"job_id": job.id, "status": "pending"}


@router.delete("/papers/{paper_id}", status_code=204)
async def remove_paper(paper_id: str, db: DB, user: Auth, background: BackgroundTasks):
    await delete_paper_rows(db, await owned(db, Paper, paper_id, user.id))
    await db.commit()
    background.add_task(safe_cleanup)


@router.get("/evidence/{evidence_id}")
async def evidence_detail(evidence_id: str, db: DB, user: Auth):
    return evidence_dict(await owned(db, Evidence, evidence_id, user.id))


@router.post("/search")
async def retrieval(body: SearchInput, db: DB, user: Auth):
    await owned(db, Library, body.library_id, user.id)
    return await search(db, user.id, body)


@router.post("/search/experiments")
async def experiment_search(
    body: ExperimentFilters,
    db: DB,
    user: Auth,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    await owned(db, Library, body.library_id, user.id)
    rows = await query_experiments(db, user.id, body, limit=limit + 1, offset=offset)
    return {
        "items": [experiment_out(e) for e in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


def experiment_out(e):
    return {
        "id": e.id,
        "paper_id": e.paper_id,
        "library_id": e.library_id,
        "record": e.record,
        "version": e.version,
    }


@router.get("/experiments")
async def experiments(
    db: DB,
    user: Auth,
    library_id: str,
    paper_id: str | None = None,
    model_name: str | None = None,
    dataset_name: str | None = None,
    metric_name: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    await owned(db, Library, library_id, user.id)
    stmt = select(Experiment).where(Experiment.owner_id == user.id, Experiment.library_id == library_id)
    for key, value in (
        ("paper_id", paper_id),
        ("model_name", model_name),
        ("dataset_name", dataset_name),
        ("metric_name", metric_name),
    ):
        if value:
            stmt = stmt.where(getattr(Experiment, key) == (value if key == "paper_id" else canonical(value)))
    rows = (await db.scalars(stmt.order_by(Experiment.id).offset(offset).limit(limit))).all()
    return {"items": [experiment_out(e) for e in rows]}


@router.post("/experiments/compare")
async def compare_experiments(body: ComparisonInput, db: DB, user: Auth):
    if len(set(body.experiment_ids)) != len(body.experiment_ids):
        raise HTTPException(422, "Select distinct experiment IDs")
    records = [await owned(db, Experiment, i, user.id) for i in body.experiment_ids]
    return {
        "items": [
            {
                "left_id": a.id,
                "right_id": b.id,
                **compare(
                    ExperimentRecord.model_validate(a.record), ExperimentRecord.model_validate(b.record)
                ),
            }
            for a, b in itertools.combinations(records, 2)
        ]
    }


@router.get("/experiments/{experiment_id}")
async def experiment_detail(experiment_id: str, db: DB, user: Auth):
    row = await owned(db, Experiment, experiment_id, user.id)
    revisions = (
        await db.scalars(
            select(Revision).where(Revision.experiment_id == row.id).order_by(Revision.created_at)
        )
    ).all()
    return {
        **experiment_out(row),
        "original_record": row.original_record,
        "revisions": [
            {"before": r.before, "after": r.after, "reason": r.reason, "created_at": r.created_at}
            for r in revisions
        ],
    }


@router.patch("/experiments/{experiment_id}")
async def revise_experiment(experiment_id: str, body: RevisionInput, db: DB, user: Auth):
    row = await owned(db, Experiment, experiment_id, user.id)
    record = body.record.model_copy(deep=True)
    ids = record.provenance.evidence_ids
    sources = (
        await db.scalars(
            select(Evidence).where(
                Evidence.id.in_(ids), Evidence.owner_id == user.id, Evidence.paper_id == row.paper_id
            )
        )
    ).all()
    if len(sources) != len(set(ids)):
        raise HTTPException(422, "Evidence must belong to the same paper")
    record = align_record(record, {e.id: evidence_dict(e) for e in sources})
    rules = ComparisonRules()
    allowed = set(rules.required + rules.hard + rules.soft) - {
        "model_name",
        "dataset_name",
        "metric_name",
        "metric_unit",
    }
    if set(ids) == set(row.record["provenance"]["evidence_ids"]):
        previous = ExperimentRecord.model_validate(row.record)
        for key, status in row.record.get("field_verification", {}).items():
            if (
                key in allowed
                and status == "reviewed"
                and canonical(getattr(record, key)) == canonical(getattr(previous, key))
            ):
                record.field_verification[key] = "reviewed"
                record.provenance.field_sources[key] = [e.id for e in sources]
    for key in body.confirmed_fields:
        if key not in allowed or getattr(record, key) in (None, "unknown", [], {}):
            raise HTTPException(422, "Confirm only non-empty comparison fields after checking their sources")
        if not sources:
            raise HTTPException(422, "Reviewed conditions require original paper evidence")
        record.field_verification[key] = "reviewed"
        record.provenance.field_sources[key] = [e.id for e in sources]
    record.experiment_id, record.paper_id = row.id, row.paper_id
    record.review_status = "corrected"
    record_json = record.model_dump(mode="json")
    before = row.record.copy()
    result = await db.execute(
        update(Experiment)
        .where(Experiment.id == row.id, Experiment.version == body.version)
        .values(
            record=record_json,
            version=body.version + 1,
            model_name=canonical(record.model_name),
            dataset_name=canonical(record.dataset_name),
            metric_name=canonical(record.metric_name),
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Record changed; reload before saving")
    db.add(
        Revision(experiment_id=row.id, user_id=user.id, before=before, after=record_json, reason=body.reason)
    )
    await touch_library(db, row.library_id)
    await db.commit()
    try:
        await index_documents(
            "experiment",
            [
                {
                    "id": row.id,
                    "paper_id": row.paper_id,
                    "library_id": row.library_id,
                    "owner_id": user.id,
                    "text": experiment_text(record_json),
                }
            ],
        )
    except Exception:
        return {
            "id": row.id,
            "record": record_json,
            "version": body.version + 1,
            "warning": "Saved to SQL; vector reindex required via /papers/{id}/reindex. Use structured search until then.",
        }
    return {"id": row.id, "record": record_json, "version": body.version + 1}


async def prepare_conversation(body, db, user):
    await owned(db, Library, body.library_id, user.id)
    if body.conversation_id:
        conversation = await owned(db, Conversation, body.conversation_id, user.id)
        if conversation.library_id != body.library_id:
            raise HTTPException(422, "Conversation belongs to another library")
    else:
        conversation = Conversation(
            id=uid(), owner_id=user.id, library_id=body.library_id, title=body.query[:120]
        )
        db.add(conversation)
        await db.flush()
    history = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(6)
        )
    ).all()
    history = [{"role": m.role, "content": m.content[:2000]} for m in reversed(history)]
    db.add(Message(conversation_id=conversation.id, role="user", content=body.query))
    await db.commit()
    return conversation, history


async def persist_answer(db, conversation, result):
    details = {
        k: result.get(k)
        for k in (
            "citations",
            "verification",
            "comparisons",
            "trace",
            "trace_id",
            "usage",
            "latency_ms",
            "errors",
            "task_type",
            "tool_count",
        )
    }
    details = jsonable_encoder(details, custom_encoder={Decimal: str})
    message = Message(
        id=uid(),
        conversation_id=conversation.id,
        role="assistant",
        content=result["final_answer"],
        details=details,
    )
    db.add(message)
    await db.commit()
    return {
        "conversation_id": conversation.id,
        "message_id": message.id,
        "answer": message.content,
        **details,
    }


@router.post("/research/chat")
async def chat(body: ChatInput, db: DB, user: Auth):
    conversation, history = await prepare_conversation(body, db, user)
    result = await run_agent(db, body, user.id, history)
    return await persist_answer(db, conversation, result)


@router.post("/research/report")
async def report(body: ChatInput, db: DB, user: Auth):
    return await chat(body.model_copy(update={"report": True}), db, user)


@router.post("/research/chat/stream")
async def stream_chat(body: ChatInput, db: DB, user: Auth):
    conversation, history = await prepare_conversation(body, db, user)
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    async def on_node(event):
        await queue.put(("status", event))

    async def work():
        try:
            result = await run_agent(db, body, user.id, history, on_node)
            output = await persist_answer(db, conversation, result)
            # Emit verified text only. These are server chunks, not unverified raw model tokens.
            for offset in range(0, len(output["answer"]), 100):
                await queue.put(("token", {"text": output["answer"][offset : offset + 100]}))
            await queue.put(("done", output))
        except Exception as exc:
            await queue.put(
                (
                    "error",
                    {"code": type(exc).__name__, "message": "Research task failed or exceeded its budget"},
                )
            )
        finally:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass  # done/error already terminates the consumer; cancellation must not block on a full queue

    async def events():
        task = asyncio.create_task(work())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), 15)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if event is None:
                    break
                name, data = event
                yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
                if name in ("done", "error"):
                    break
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/research/conversations")
async def conversations(
    db: DB, user: Auth, library_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
):
    await owned(db, Library, library_id, user.id)
    rows = (
        await db.scalars(
            select(Conversation)
            .where(Conversation.owner_id == user.id, Conversation.library_id == library_id)
            .order_by(Conversation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {"items": [{"id": r.id, "title": r.title, "created_at": r.created_at} for r in rows]}


@router.get("/research/conversations/{conversation_id}")
async def conversation_detail(conversation_id: str, db: DB, user: Auth):
    await owned(db, Conversation, conversation_id, user.id)
    rows = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .limit(200)
        )
    ).all()
    return {"items": [{"id": r.id, "role": r.role, "content": r.content, "details": r.details} for r in rows]}


@router.get("/public/papers")
async def public_papers(
    user: Auth,
    q: str = Query(min_length=2, max_length=300),
    year_from: int | None = Query(None, ge=1900, le=2100),
    year_to: int | None = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1, le=100),
):
    try:
        return await public_search(q, year_from, year_to, page)
    except (httpx.HTTPError, RuntimeError):
        raise HTTPException(502, "Academic search provider unavailable or rate limited") from None


@router.get("/settings")
async def get_settings(user: Auth):
    cfg = settings()
    return {
        "chat_configured": bool(cfg.api_key),
        "chat_model": cfg.chat_model,
        "embedding_backend": cfg.embedding_backend,
        "embedding_model": cfg.embedding_model,
        "reranker": cfg.reranker_model,
        "parser": cfg.parser,
        "langfuse_enabled": cfg.langfuse_enabled,
        "max_upload_mb": cfg.max_upload_mb,
        "max_tools": cfg.agent_max_tools,
        "temperature": cfg.temperature,
    }


@router.post("/public/import", status_code=201)
async def import_public(body: PublicImport, db: DB, user: Auth):
    await owned(db, Library, body.library_id, user.id)
    external_id = "https://openalex.org/" + body.openalex_id.rsplit("/", 1)[-1]
    existing = await db.scalar(
        select(PublicReference).where(
            PublicReference.library_id == body.library_id, PublicReference.external_id == external_id
        )
    )
    if existing:
        return {"id": existing.id, "metadata": existing.metadata_json, "duplicate": True}
    try:
        metadata = await public_work(external_id)
    except (httpx.HTTPError, RuntimeError):
        raise HTTPException(502, "Academic metadata provider unavailable") from None
    row = PublicReference(
        owner_id=user.id, library_id=body.library_id, external_id=external_id, metadata_json=metadata
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        row = await db.scalar(
            select(PublicReference).where(
                PublicReference.library_id == body.library_id, PublicReference.external_id == external_id
            )
        )
        if not row:
            raise
    return {"id": row.id, "metadata": row.metadata_json, "content_scope": "metadata_only"}


@router.get("/public/references")
async def public_references(
    library_id: str, db: DB, user: Auth, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
):
    await owned(db, Library, library_id, user.id)
    rows = (
        await db.scalars(
            select(PublicReference)
            .where(PublicReference.owner_id == user.id, PublicReference.library_id == library_id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {"items": [{"id": r.id, "metadata": r.metadata_json} for r in rows]}


@router.delete("/public/references/{reference_id}", status_code=204)
async def delete_reference(reference_id: str, db: DB, user: Auth):
    row = await owned(db, PublicReference, reference_id, user.id)
    await db.delete(row)
    await db.commit()


@router.get("/stats")
async def stats(db: DB, user: Auth):
    result = {}
    for name, entity in (
        ("libraries", Library),
        ("papers", Paper),
        ("experiments", Experiment),
        ("conversations", Conversation),
    ):
        result[name] = await db.scalar(
            select(func.count()).select_from(entity).where(entity.owner_id == user.id)
        )
    return result


@router.post("/evaluation/run", status_code=201)
async def evaluate(body: EvaluationInput, db: DB, user: Auth):
    await owned(db, Library, body.library_id, user.id)
    allowed_ids = set(
        (
            await db.scalars(
                select(Evidence.id).where(
                    Evidence.owner_id == user.id, Evidence.library_id == body.library_id
                )
            )
        ).all()
    )
    if any(set(q.relevant_ids) - allowed_ids for q in body.questions):
        raise HTTPException(422, "Relevance labels must refer to evidence in this library")
    results = []
    async with asyncio.timeout(300):
        for mode in body.modes:
            for question in body.questions:
                response = await search(
                    db,
                    user.id,
                    SearchInput(library_id=body.library_id, query=question.query, mode=mode, top_k=10),
                )
                results.append(
                    {
                        "mode": mode,
                        "query": question.query,
                        **retrieval_metrics([e["id"] for e in response["items"]], question.relevant_ids),
                        **response["timing"],
                    }
                )
    run = EvaluationRun(
        owner_id=user.id,
        library_id=body.library_id,
        status="completed",
        result={
            "rows": results,
            "labels": "user-supplied relevance judgments",
            "model_generation": False,
            "cost_usd": None,
        },
    )
    db.add(run)
    await db.commit()
    return {"id": run.id, "status": run.status, "result": run.result}


@router.get("/evaluation/runs")
async def evaluation_runs(
    db: DB, user: Auth, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
):
    rows = (
        await db.scalars(
            select(EvaluationRun)
            .where(EvaluationRun.owner_id == user.id)
            .order_by(EvaluationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {
        "items": [
            {"id": r.id, "status": r.status, "library_id": r.library_id, "created_at": r.created_at}
            for r in rows
        ]
    }


@router.get("/evaluation/runs/{run_id}")
async def evaluation_detail(run_id: str, db: DB, user: Auth):
    row = await owned(db, EvaluationRun, run_id, user.id)
    return {"id": row.id, "status": row.status, "result": row.result}
