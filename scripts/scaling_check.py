"""Read-only source audit with real isolated SQL/ASGI/BM25 workloads.

Synthetic measurements and provider double are explicitly labeled; no model API is called.
Application data is created in a disposable system-temp directory, never the project's data/.
"""
# ruff: noqa: E402

import argparse
import asyncio
import copy
import cProfile
import io
import json
import os
import platform
import pstats
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
TEMP = Path(tempfile.mkdtemp(prefix="papermind-audit-"))
os.environ.update(
    PM_DATABASE_URL=f"sqlite+aiosqlite:///{(TEMP / 'audit.db').as_posix()}",
    PM_STORAGE_PATH=str(TEMP),
    PM_ENVIRONMENT="development",
    PM_API_KEY="",
    PM_TASK_EAGER="true",
    PM_RATE_LIMIT_PER_MINUTE="100000",
    PM_PARSER="pypdf",
)
sys.path.insert(0, str(BACKEND))

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import event, insert

from app.agents.research import query_experiments
from app.core.config import settings
from app.core.db import Session, engine
from app.core.security import token_for
from app.experiments import SemanticVerdict, align_record
from app.main import app
from app.models import Base, Evidence, Experiment, Library, Paper, User
from app.retrieval import bm25
from app.schemas import ExperimentFilters, ExperimentRecord
from app.services.providers import ModelProvider, Usage

RESULT = {
    "date": "2026-10-20",
    "implementation": "post-scaling-fixes working tree",
    "environment": {
        "python": platform.python_version(),
        "platform": platform.platform(),
    },
    "scope": "Synthetic isolated fixtures; real BM25/SQLAlchemy/SQLite/ASGI code. No live LLM/reranker or production concurrency measurement. Optional dense check uses the actual local model.",
}


def correctness():
    source = {
        "paper_id": "p",
        "page": 1,
        "text": "Synthetic table only",
        "locator": {
            "captions": ["TestMoE-XL accuracy (%) on PIQA-hard"],
            "cells": [
                {
                    "row": 0,
                    "col": 1,
                    "end_col": 2,
                    "text": "PIQA-hard",
                    "column_header": True,
                },
                {"row": 1, "col": 0, "text": "Method AB"},
                {"row": 1, "col": 1, "text": "79.2"},
            ],
        },
    }
    record = ExperimentRecord(
        method_name="Method A",
        model_name="TestMoE",
        dataset_name="PIQA",
        metric_name="accuracy",
        metric_value="79.2",
        metric_unit="percent",
        provenance={
            "evidence_ids": ["e"],
            "original_value": "79.2",
            "row_index": 1,
            "column_index": 1,
        },
    )
    exact = copy.deepcopy(source)
    exact["locator"]["captions"] = ["TestMoE accuracy (%) on PIQA"]
    exact["locator"]["cells"][0]["text"] = "PIQA"
    exact["locator"]["cells"][1]["text"] = "Method A"
    cases = []
    for field, replacement in [
        ("method_name", "Method AB"),
        ("model_name", "TestMoE-XL"),
        ("dataset_name", "PIQA-hard"),
    ]:
        changed = copy.deepcopy(exact)
        if field == "method_name":
            changed["locator"]["cells"][1]["text"] = replacement
        elif field == "model_name":
            changed["locator"]["captions"] = [f"{replacement} accuracy (%) on PIQA"]
        else:
            changed["locator"]["captions"] = ["TestMoE accuracy (%) on PIQA-hard"]
            changed["locator"]["cells"][0]["text"] = replacement
        aligned = align_record(record, {"e": changed})
        cases.append(
            {
                "case": field + "_prefix_collision",
                "expected": "insufficient",
                "actual": aligned.verification_status,
            }
        )
    mixed = copy.deepcopy(exact)
    mixed["locator"]["captions"] = ["TestMoE accuracy (%) and perplexity results"]
    mixed["locator"]["cells"][0]["text"] = "WikiText PPL"
    mixed["locator"]["cells"][2]["text"] = "12.3"
    ppl = ExperimentRecord(
        method_name="Method A",
        model_name="TestMoE",
        dataset_name="WikiText",
        metric_name="perplexity",
        metric_value="12.3",
        metric_unit="score",
        provenance={
            "evidence_ids": ["e"],
            "original_value": "12.3",
            "row_index": 1,
            "column_index": 1,
        },
    )
    cases.append(
        {
            "case": "mixed_metric_caption",
            "expected": "supported",
            "actual": align_record(ppl, {"e": mixed}).verification_status,
        }
    )
    RESULT["correctness"] = cases


async def input_budget():
    cfg = settings()
    calls = []

    class ExplicitProviderDouble:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, *args, **kwargs):
            return self

        async def ainvoke(self, messages):
            from langchain_core.messages import AIMessage

            calls.append(True)
            return {
                "raw": AIMessage(
                    content="{}",
                    usage_metadata={
                        "input_tokens": 1,
                        "output_tokens": 1,
                        "total_tokens": 2,
                    },
                ),
                "parsed": SemanticVerdict(status="insufficient", rationale="Explicit isolated fixture"),
                "parsing_error": None,
            }

    with (
        patch.object(cfg, "api_key", SecretStr("isolated-audit-provider")),
        patch("app.services.providers.ChatOpenAI", ExplicitProviderDouble),
    ):
        usage = Usage(input_tokens=cfg.max_input_tokens)
        try:
            await ModelProvider(usage).structured(SemanticVerdict, "Audit budget only", {})
        except RuntimeError:
            pass
        RESULT["input_budget"] = {
            "scope": "deterministic provider double; no network/model spend",
            "configured_limit": cfg.max_input_tokens,
            "initial_usage": cfg.max_input_tokens,
            "provider_called_after_exhaustion": bool(calls),
            "final_usage": usage.input_tokens,
        }


TEXT = (
    "Synthetic scientific evidence about quantization model evaluation accuracy datasets calibration "
    "mixed precision weights memory perplexity results benchmark retrieval experiment conditions. "
) * 11


async def performance():
    docs = [{"id": str(n), "text": TEXT + f" group{n % 97}"} for n in range(10000)]
    micro = []
    for count in (1000, 5000, 10000):
        samples = []
        for _ in range(3):
            start = time.perf_counter()
            bm25("quantization calibration group7", docs[:count], 40)
            samples.append((time.perf_counter() - start) * 1000)
        micro.append(
            {
                "documents": count,
                "characters_per_document": len(TEXT),
                "median_ms": round(statistics.median(samples), 2),
                "samples_ms": [round(x, 2) for x in samples],
            }
        )
    RESULT["bm25_microbenchmark"] = micro
    profiler = cProfile.Profile()
    profiler.enable()
    bm25("quantization calibration group7", docs[:5000], 40)
    profiler.disable()
    output = io.StringIO()
    pstats.Stats(profiler, stream=output).strip_dirs().sort_stats("cumulative").print_stats(12)
    (ROOT / "docs/verification/bm25-profile-after.txt").write_text(
        output.getvalue().rstrip() + "\n", encoding="utf-8"
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as db:
        db.add(
            User(
                id="audit-user",
                email="synthetic-audit@example.test",
                password_hash="not-used",
            )
        )
        await db.flush()
        for count in (1000, 10000, 10001):
            lib = f"lib-{count}"
            paper = f"paper-{count}"
            db.add(Library(id=lib, owner_id="audit-user", name="Synthetic audit"))
            await db.flush()
            db.add(
                Paper(
                    id=paper,
                    owner_id="audit-user",
                    library_id=lib,
                    title="Synthetic only",
                    filename="none.pdf",
                    sha256=str(count),
                    status="ready",
                )
            )
            await db.flush()
            for offset in range(0, count, 500):
                await db.execute(
                    insert(Evidence),
                    [
                        {
                            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"e-{count}-{n:05}")),
                            "owner_id": "audit-user",
                            "library_id": lib,
                            "paper_id": paper,
                            "kind": "paragraph",
                            "text": TEXT + f" group{n % 97}",
                            "page": 1,
                            "locator": {},
                        }
                        for n in range(offset, min(count, offset + 500))
                    ],
                )
            if count == 10000:
                for offset in range(0, count, 500):
                    rows = []
                    for n in range(offset, min(count, offset + 500)):
                        data = ExperimentRecord(
                            model_name="SyntheticModel",
                            average_bits="3" if n == count - 1 else "4",
                        ).model_dump(mode="json")
                        rows.append(
                            {
                                "id": f"x-{n:05}",
                                "paper_id": paper,
                                "library_id": lib,
                                "owner_id": "audit-user",
                                "fingerprint": str(n),
                                "model_name": "syntheticmodel",
                                "record": data,
                                "original_record": data,
                                "version": 1,
                            }
                        )
                    await db.execute(insert(Experiment), rows)
        await db.commit()
    headers = {"Authorization": "Bearer " + token_for("audit-user")}
    api = []
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://audit",
        headers=headers,
        timeout=120,
    ) as client:
        for count, concurrency, temperature in (
            (1000, 1, "cold"),
            (1000, 1, "warm"),
            (10000, 1, "cold"),
            (10000, 1, "warm"),
            (10000, 4, "warm"),
        ):
            lags = []
            stop = asyncio.Event()

            async def heartbeat(stop=stop, samples=lags):
                while not stop.is_set():
                    target = time.perf_counter() + 0.01
                    await asyncio.sleep(0.01)
                    samples.append(max(0, (time.perf_counter() - target) * 1000))

            async def one(count=count):
                start = time.perf_counter()
                r = await client.post(
                    "/api/v1/search",
                    json={
                        "library_id": f"lib-{count}",
                        "query": "quantization calibration group7",
                        "mode": "bm25",
                    },
                )
                return {
                    "status": r.status_code,
                    "wall_ms": round((time.perf_counter() - start) * 1000, 2),
                    "items": len(r.json().get("items", [])),
                }

            beat = asyncio.create_task(heartbeat())
            await asyncio.sleep(0.02)
            requests = await asyncio.gather(*(one() for _ in range(concurrency)))
            stop.set()
            await beat
            api.append(
                {
                    "documents": count,
                    "concurrency": concurrency,
                    "cache": temperature,
                    "requests": requests,
                    "max_event_loop_lag_ms": round(max(lags, default=0), 2),
                }
            )
        cap = []
        modes = ["bm25"]
        if ARGS.with_dense:
            from app.retrieval import index_documents

            async with Session() as db:
                from sqlalchemy import select

                rows = (
                    await db.scalars(select(Evidence).where(Evidence.library_id == "lib-10001").limit(2))
                ).all()
            await index_documents(
                "evidence",
                [
                    {
                        "id": e.id,
                        "paper_id": e.paper_id,
                        "library_id": e.library_id,
                        "owner_id": e.owner_id,
                        "text": e.text,
                    }
                    for e in rows
                ],
            )
            modes.append("dense")
            RESULT["dense_check"] = (
                "Real CPU MiniLM embeddings and embedded Qdrant; two indexed source candidates in a 10,001-record SQL library"
            )
        else:
            RESULT["dense_check"] = "Not run; use --with-dense with locally cached model assets"
        for mode in modes:
            r = await client.post(
                "/api/v1/search",
                json={"library_id": "lib-10001", "query": "quantization", "mode": mode},
            )
            cap.append(
                {
                    "documents": 10001,
                    "mode": mode,
                    "status": r.status_code,
                    "response": r.json(),
                }
            )
        RESULT["search_cap"] = cap
    RESULT["asgi_benchmark"] = api
    counts = []

    def count_sql(*args):
        counts.append(True)

    event.listen(engine.sync_engine, "before_cursor_execute", count_sql)
    structured = []
    try:
        for filters in ({"model_name": "SyntheticModel"}, {"average_bits": "3"}):
            samples, statements = [], []
            for _ in range(3):
                counts.clear()
                start = time.perf_counter()
                async with Session() as db:
                    rows = await query_experiments(
                        db,
                        "audit-user",
                        ExperimentFilters(library_id="lib-10000", **filters),
                        limit=10,
                    )
                samples.append(round((time.perf_counter() - start) * 1000, 2))
                statements.append(len(counts))
            structured.append(
                {
                    "filters": filters,
                    "matching_records": len(rows),
                    "sql_statements": statements,
                    "samples_ms": samples,
                    "median_ms": statistics.median(samples),
                }
            )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count_sql)
    RESULT["structured_filter_benchmark"] = structured
    if ARGS.with_dense:
        from app.retrieval import vector_client

        vector_client().close()
        vector_client.cache_clear()
    await engine.dispose()


async def main():
    correctness()
    await input_budget()
    await performance()
    (ROOT / "evaluation/results/scaling-after.json").write_text(
        json.dumps(RESULT, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "correctness": RESULT["correctness"],
                "input_budget": RESULT["input_budget"],
                "asgi_benchmark": RESULT["asgi_benchmark"],
                "structured_filter_benchmark": RESULT["structured_filter_benchmark"],
                "search_cap": [{"mode": r["mode"], "status": r["status"]} for r in RESULT["search_cap"]],
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-dense",
        action="store_true",
        help="Run real locally cached MiniLM and Qdrant candidate checks",
    )
    ARGS = parser.parse_args()
    asyncio.run(main())
