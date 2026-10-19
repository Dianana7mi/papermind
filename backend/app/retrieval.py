import asyncio
import math
import re
import time
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client import models as qm
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Evidence, Experiment, Paper
from app.schemas import SearchInput
from app.services.providers import embed, rerank, vector_collection


def tokenize(text: str) -> list[str]:
    latin = re.findall(r"[\w.-]+", text.casefold(), re.ASCII)
    chinese = re.findall(r"[\u4e00-\u9fff]", text)
    return latin + chinese + [a + b for a, b in zip(chinese, chinese[1:], strict=False)]


def bm25(query: str, documents: list[dict], top_k: int = 30) -> list[dict]:
    if not documents:
        return []
    tokens = [tokenize(d["text"]) or ["__empty__"] for d in documents]
    scorer = BM25Okapi(tokens)
    scores = scorer.get_scores(tokenize(query))
    # Real BM25 may give negative IDF for ubiquitous terms; retain lexical matches even at <= 0.
    query_terms = set(tokenize(query))
    ranked = [(i, float(score)) for i, score in enumerate(scores) if query_terms.intersection(tokens[i])]
    return [
        {**documents[i], "score": score}
        for i, score in sorted(ranked, key=lambda x: x[1], reverse=True)[:top_k]
    ]


def rrf(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    scores, documents = {}, {}
    for ranking in rankings:
        seen = set()
        for rank, document in enumerate(ranking, 1):
            key = document["id"]
            if key in seen:
                continue
            seen.add(key)
            scores[key] = scores.get(key, 0) + 1 / (k + rank)
            documents[key] = document
    return [
        {**documents[key], "score": score}
        for key, score in sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    ]


@lru_cache
def vector_client():
    cfg = settings()
    if cfg.qdrant_url:
        return QdrantClient(
            url=cfg.qdrant_url,
            api_key=cfg.qdrant_api_key.get_secret_value() if cfg.qdrant_api_key else None,
            timeout=60,
        )
    return QdrantClient(path=str(cfg.storage_path / "qdrant"), force_disable_check_same_thread=True)


async def index_documents(level: str, documents: list[dict]):
    if not documents:
        return
    vectors = await embed([d["text"] for d in documents])

    def write():
        client = vector_client()
        name = vector_collection(level)
        if not client.collection_exists(name):
            client.create_collection(
                name, vectors_config=qm.VectorParams(size=len(vectors[0]), distance=qm.Distance.COSINE)
            )
            if settings().qdrant_url:
                for key in ("owner_id", "library_id", "paper_id"):
                    client.create_payload_index(name, key, field_schema=qm.PayloadSchemaType.KEYWORD)
        points = [
            qm.PointStruct(id=d["id"], vector=v, payload={**d, "index_version": "1"})
            for d, v in zip(documents, vectors, strict=True)
        ]
        for offset in range(0, len(points), 64):
            client.upsert(name, points=points[offset : offset + 64], wait=True)

    await asyncio.to_thread(write)


async def delete_vectors(paper_id: str):
    def run():
        client = vector_client()
        # Clean all model versions, including collections from a previous configuration.
        for collection in client.get_collections().collections:
            if collection.name.startswith("papermind_"):
                client.delete(
                    collection.name,
                    points_selector=qm.FilterSelector(
                        filter=qm.Filter(
                            must=[qm.FieldCondition(key="paper_id", match=qm.MatchValue(value=paper_id))]
                        )
                    ),
                    wait=True,
                )

    await asyncio.to_thread(run)


async def search(db: AsyncSession, owner_id: str, request: SearchInput) -> dict:
    started = time.perf_counter()
    entity = {"evidence": Evidence, "paper": Paper, "experiment": Experiment}[request.level]
    stmt = select(entity).where(entity.owner_id == owner_id, entity.library_id == request.library_id)
    if request.paper_id:
        stmt = stmt.where((entity.id if entity is Paper else entity.paper_id) == request.paper_id)
    if entity is Paper:
        stmt = stmt.where(Paper.status == "ready")
    else:
        stmt = stmt.join(Paper, Paper.id == entity.paper_id).where(Paper.status == "ready")
    # ponytail: bounded in-memory BM25 for <=10k evidence units per library; move sparse index to Qdrant beyond this.
    rows = (await db.scalars(stmt.limit(10001))).all()
    if len(rows) > 10000:
        raise ValueError("Library exceeds in-memory sparse index limit; shard the library")
    documents = []
    for row in rows:
        if isinstance(row, Evidence):
            item = {
                "id": row.id,
                "paper_id": row.paper_id,
                "text": row.text,
                "page": row.page,
                "section": row.section,
                "kind": row.kind,
                "locator": row.locator,
            }
        elif isinstance(row, Paper):
            item = {
                "id": row.id,
                "paper_id": row.id,
                "text": row.title + "\n" + row.metadata_json.get("abstract", ""),
                "title": row.title,
            }
        else:
            item = {
                "id": row.id,
                "paper_id": row.paper_id,
                "text": experiment_text(row.record),
                "record": row.record,
            }
        documents.append(item)
    lexical = bm25(request.query, documents, 40) if request.mode != "dense" else []
    dense = []
    dense_ms = 0.0
    if request.mode != "bm25" and documents:
        ds = time.perf_counter()
        query = (await embed([request.query]))[0]
        conditions = [
            qm.FieldCondition(key="owner_id", match=qm.MatchValue(value=owner_id)),
            qm.FieldCondition(key="library_id", match=qm.MatchValue(value=request.library_id)),
        ]
        if request.paper_id:
            conditions.append(qm.FieldCondition(key="paper_id", match=qm.MatchValue(value=request.paper_id)))

        def retrieve():
            client = vector_client()
            if not client.collection_exists(vector_collection(request.level)):
                return []
            return client.query_points(
                vector_collection(request.level),
                query=query,
                query_filter=qm.Filter(must=conditions),
                limit=40,
            ).points

        points = await asyncio.to_thread(retrieve)
        allowed = {d["id"]: d for d in documents}
        # Hydrate through authorized SQL records. Deleted/stale points cannot leak through.
        dense = [{**allowed[str(p.id)], "score": p.score} for p in points if str(p.id) in allowed]
        dense_ms = (time.perf_counter() - ds) * 1000
    ranked = (
        lexical if request.mode == "bm25" else dense if request.mode == "dense" else rrf([dense, lexical])
    )
    rerank_ms = 0.0
    if request.mode == "rerank" and ranked:
        rs = time.perf_counter()
        candidates = ranked[:30]
        scores = await rerank(request.query, [d["text"] for d in candidates])
        ranked = sorted(
            [{**d, "score": score} for d, score in zip(candidates, scores, strict=True)],
            key=lambda d: d["score"],
            reverse=True,
        )
        rerank_ms = (time.perf_counter() - rs) * 1000
    return {
        "items": ranked[: request.top_k],
        "mode": request.mode,
        "level": request.level,
        "timing": {
            "total_ms": (time.perf_counter() - started) * 1000,
            "dense_ms": dense_ms,
            "rerank_ms": rerank_ms,
        },
    }


def experiment_text(record: dict) -> str:
    keys = (
        "method_name",
        "model_name",
        "model_architecture",
        "dataset_name",
        "metric_name",
        "metric_value",
        "metric_unit",
        "average_bits",
        "quantized_components",
        "evaluation_protocol",
    )
    return "; ".join(f"{key}: {record[key]}" for key in keys if record.get(key) is not None)


def retrieval_metrics(ranked: list[str], relevant: list[str]) -> dict:
    relevant_set = set(relevant)
    if not relevant_set:
        raise ValueError("Relevance labels cannot be empty")
    seen = set()
    ranked = [i for i in ranked if not (i in seen or seen.add(i))]

    def recall(k):
        return len(set(ranked[:k]) & relevant_set) / len(relevant_set)

    reciprocal = next((1 / n for n, i in enumerate(ranked, 1) if i in relevant_set), 0.0)
    dcg = sum(1 / math.log2(i + 2) for i, item in enumerate(ranked[:10]) if item in relevant_set)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(10, len(relevant_set))))
    return {"recall@5": recall(5), "recall@10": recall(10), "mrr": reciprocal, "ndcg@10": dcg / ideal}
