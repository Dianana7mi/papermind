"""Tools receive authenticated scope from the server, never from paper/model text."""

import asyncio
import logging
import time

from fastapi import HTTPException
from sqlalchemy import select

from app.experiments import compare, verify_claim
from app.ingestion.pipeline import evidence_dict
from app.models import Evidence, Experiment, Library, Paper
from app.retrieval import search
from app.schemas import (
    AtomicClaim,
    ComparisonInput,
    ExperimentFilters,
    ExperimentRecord,
    SearchInput,
    StrictModel,
)
from app.services.public_search import public_search

log = logging.getLogger("papermind.tools")


class PaperInput(StrictModel):
    paper_id: str


class PublicSearchInput(StrictModel):
    query: str
    year_from: int | None = None
    year_to: int | None = None


class VerifyInput(StrictModel):
    claims: list[AtomicClaim]


class ResearchTools:
    """Request-local context. All SQL and vector tools enforce owner AND library scope."""

    def __init__(self, db, user_id: str, library_id: str):
        self.db, self.user_id, self.library_id = db, user_id, library_id

    async def execute(self, name: str, payload: dict):
        allowed = {
            "search_papers",
            "retrieve_evidence",
            "get_paper_metadata",
            "get_paper_sections",
            "query_experiments",
            "compare_experiments",
            "verify_claims",
            "search_public_papers",
        }
        if name not in allowed:
            raise ValueError("Unknown research tool")
        library = await self.db.scalar(
            select(Library.id).where(Library.id == self.library_id, Library.owner_id == self.user_id)
        )
        if not library:
            raise HTTPException(404, "Library not found")
        started = time.perf_counter()
        try:
            async with asyncio.timeout(90):
                return await getattr(self, name)(payload)
        finally:
            log.info(
                "tool_finished", extra={"tool": name, "latency_ms": (time.perf_counter() - started) * 1000}
            )

    async def search_papers(self, payload):
        request = SearchInput.model_validate({**payload, "library_id": self.library_id, "level": "paper"})
        return await search(self.db, self.user_id, request)

    async def retrieve_evidence(self, payload):
        request = SearchInput.model_validate({**payload, "library_id": self.library_id, "level": "evidence"})
        return await search(self.db, self.user_id, request)

    async def _paper(self, payload):
        request = PaperInput.model_validate(payload)
        row = await self.db.scalar(
            select(Paper).where(
                Paper.id == request.paper_id,
                Paper.owner_id == self.user_id,
                Paper.library_id == self.library_id,
            )
        )
        if not row:
            raise HTTPException(404, "Paper not found")
        return row

    async def get_paper_metadata(self, payload):
        paper = await self._paper(payload)
        return {
            "id": paper.id,
            "title": paper.title,
            "status": paper.status,
            "abstract": paper.metadata_json.get("abstract"),
        }

    async def get_paper_sections(self, payload):
        paper = await self._paper(payload)
        rows = (
            await self.db.scalars(
                select(Evidence).where(Evidence.paper_id == paper.id, Evidence.owner_id == self.user_id)
            )
        ).all()
        return {
            "sections": list(dict.fromkeys(e.section for e in rows if e.section)),
            "evidence": [evidence_dict(e) for e in rows],
        }

    async def query_experiments(self, payload):
        from app.agents.research import query_experiments

        request = ExperimentFilters.model_validate({**payload, "library_id": self.library_id})
        return [row.record for row in await query_experiments(self.db, self.user_id, request)]

    async def compare_experiments(self, payload):
        request = ComparisonInput.model_validate(payload)
        rows = (
            await self.db.scalars(
                select(Experiment).where(
                    Experiment.id.in_(request.experiment_ids),
                    Experiment.owner_id == self.user_id,
                    Experiment.library_id == self.library_id,
                )
            )
        ).all()
        if len(rows) != len(set(request.experiment_ids)):
            raise HTTPException(404, "Experiment not found")
        import itertools

        return [
            compare(ExperimentRecord.model_validate(a.record), ExperimentRecord.model_validate(b.record))
            for a, b in itertools.combinations(rows, 2)
        ]

    async def verify_claims(self, payload):
        request = VerifyInput.model_validate(payload)
        evidence_ids = {i for c in request.claims for i in c.evidence_ids}
        experiment_ids = {c.experiment_id for c in request.claims if c.experiment_id}
        evidence = (
            await self.db.scalars(
                select(Evidence).where(
                    Evidence.id.in_(evidence_ids),
                    Evidence.owner_id == self.user_id,
                    Evidence.library_id == self.library_id,
                )
            )
        ).all()
        experiments = (
            await self.db.scalars(
                select(Experiment).where(
                    Experiment.id.in_(experiment_ids),
                    Experiment.owner_id == self.user_id,
                    Experiment.library_id == self.library_id,
                )
            )
        ).all()
        return [
            verify_claim(
                c,
                {e.id: evidence_dict(e) for e in evidence},
                {e.id: ExperimentRecord.model_validate(e.record) for e in experiments},
            )
            for c in request.claims
        ]

    async def search_public_papers(self, payload):
        request = PublicSearchInput.model_validate(payload)
        return await public_search(request.query, request.year_from, request.year_to, 1)
