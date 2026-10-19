import asyncio

from celery import Celery

from app.core.config import settings

celery = Celery("papermind", broker=settings().redis_url, backend=settings().redis_url)
celery.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=900,
    task_soft_time_limit=840,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "retry-cleanup": {"task": "papermind.cleanup", "schedule": 60.0},
        "recover-jobs": {"task": "papermind.recover", "schedule": 60.0},
    },
)


@celery.task(name="papermind.ingest", bind=True, max_retries=2)
def ingest_task(self, paper_id: str):
    from app.ingestion.pipeline import ingest

    # Explicit retries require /papers/{id}/retry, preserving user corrections on ready papers.
    try:
        asyncio.run(ingest(paper_id))
    except Exception:
        raise RuntimeError("Ingestion failed; inspect the persisted safe job diagnostics") from None


@celery.task(name="papermind.cleanup")
def cleanup_task():
    from app.ingestion.pipeline import cleanup

    asyncio.run(cleanup())


@celery.task(name="papermind.extract")
def extraction_task(job_id: str):
    from app.ingestion.pipeline import resume_extraction

    asyncio.run(resume_extraction(job_id))


@celery.task(name="papermind.recover")
def recover_jobs():
    from datetime import timedelta

    from sqlalchemy import select, update

    from app.core.db import Session
    from app.models import Job, Paper, now

    async def recover():
        async with Session() as db:
            # Repair orphaned claims left by older versions which committed Paper before Job.
            active_job = select(Job.id).where(Job.paper_id == Paper.id, Job.status == "processing").exists()
            orphans = (
                await db.scalars(select(Paper).where(Paper.status == "processing", ~active_job).limit(100))
            ).all()
            for paper in orphans:
                paper.status, paper.error = "failed", "Incomplete worker claim; retry processing"
                await db.execute(
                    update(Job)
                    .where(Job.paper_id == paper.id, Job.status == "pending")
                    .values(status="failed")
                )
            stale = (
                await db.scalars(
                    select(Job).where(
                        Job.status == "processing", Job.started_at < now() - timedelta(minutes=20)
                    )
                )
            ).all()
            for job in stale:
                paper = await db.get(Paper, job.paper_id)
                if paper and paper.extraction_lock == job.id:
                    paper.extraction_lock = None
                    job.status = "failed"
                elif paper and paper.status == "processing":
                    paper.status, paper.error = "failed", "Worker lease expired; retry processing"
                    job.status = "failed"
            await db.commit()
            pending = (await db.scalars(select(Paper.id).where(Paper.status == "pending").limit(100))).all()
            for paper_id in pending:
                ingest_task.delay(paper_id)
            extraction_jobs = (
                await db.scalars(
                    select(Job.id).where(Job.status == "pending", Job.stage == "extraction_queued").limit(100)
                )
            ).all()
            for job_id in extraction_jobs:
                extraction_task.delay(job_id)

    asyncio.run(recover())
