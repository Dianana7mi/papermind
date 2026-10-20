"""Synthetic boundary fixtures; all model substitutes are confined to these tests."""

import pytest
from pydantic import SecretStr
from sqlalchemy import insert, select, text, update
from test_evaluation import source_fixture
from test_resume import setup_paper

from app.agents.research import query_experiments
from app.core.config import settings
from app.core.db import Session, engine
from app.experiments import SemanticVerdict, align_record, entity_matches, source_unit
from app.models import Evidence, Experiment, Paper, experiment_filter_expression, touch_library, uid
from app.schemas import ExperimentFilters
from app.services.providers import ModelProvider, Usage


def test_linux_lock_has_cpu_torch_without_gpu_stack():
    import tomllib
    from pathlib import Path

    packages = tomllib.loads((Path(__file__).resolve().parents[1] / "uv.lock").read_text(encoding="utf-8"))[
        "package"
    ]
    assert any(p["name"] == "torch" and "+cpu" in p["version"] for p in packages)
    assert not any(p["name"].startswith(("cuda-", "nvidia-")) or p["name"] == "triton" for p in packages)


@pytest.mark.parametrize(
    "field,actual",
    [("method_name", "Method AB"), ("model_name", "TestMoE-XL"), ("dataset_name", "PIQA-hard")],
)
def test_complete_entities_cannot_certify_prefixes(synthetic_record, field, actual):
    source = source_fixture()
    if field == "method_name":
        source["locator"]["cells"][1]["text"] = actual
    elif field == "model_name":
        source["locator"]["captions"] = [actual + " accuracy (%)"]
    else:
        source["locator"]["cells"][0]["text"] = actual
    assert align_record(synthetic_record, {"evidence-a": source}).verification_status == "insufficient"


def test_aliases_and_multi_metric_headers(synthetic_record):
    assert entity_matches("perplexity", "WikiText PPL")
    assert entity_matches("wikitext2", "Dataset: WikiText-2")
    assert not entity_matches("OPT-1.3B", "OPT-1.3B-v2")
    assert not entity_matches("AWQ", "AWQ++")
    assert entity_matches("TestMoE", "Evaluated on TestMoE.")
    source = source_fixture()
    source["locator"]["captions"] = ["TestMoE accuracy (%) and perplexity results"]
    source["locator"]["cells"][0]["text"] = "WikiText PPL"
    source["locator"]["cells"][2]["text"] = "12.3"
    synthetic_record.dataset_name, synthetic_record.metric_name = "WikiText", "perplexity"
    synthetic_record.metric_value, synthetic_record.metric_unit = "12.3", "score"
    synthetic_record.provenance.original_value = "12.3"
    assert align_record(synthetic_record, {"evidence-a": source}).verification_status == "supported"
    synthetic_record.metric_name, synthetic_record.metric_unit = "accuracy", "percent"
    assert align_record(synthetic_record, {"evidence-a": source}).verification_status != "supported"
    assert source_unit("12.3", "WikiText", "Accuracy (%) and PPL") == "unknown"


@pytest.mark.parametrize("budget", ["input", "total", "context", "dollars"])
async def test_budget_rejection_precedes_provider_creation(monkeypatch, budget):
    cfg = settings()
    monkeypatch.setattr(cfg, "api_key", SecretStr("isolated-budget-test"))
    monkeypatch.setattr("app.services.providers.estimate_tokens", lambda text, model: (200, "isolated-test"))
    usage = Usage()
    if budget == "input":
        usage.input_tokens = cfg.max_input_tokens
    elif budget == "total":
        usage.output_tokens = cfg.max_total_tokens
    elif budget == "context":
        monkeypatch.setattr(cfg, "context_length", 100)
    else:
        monkeypatch.setattr(cfg, "input_cost_per_million", 10000)
        monkeypatch.setattr(cfg, "output_cost_per_million", 10000)

    def must_not_construct(**kwargs):
        raise AssertionError("Provider must not be reached after budget exhaustion")

    monkeypatch.setattr("app.services.providers.ChatOpenAI", must_not_construct)
    with pytest.raises(RuntimeError):
        await ModelProvider(usage).structured(SemanticVerdict, "Isolated test", {})


async def test_unknown_usage_reserves_budget_after_failure(monkeypatch):
    cfg = settings()
    monkeypatch.setattr(cfg, "api_key", SecretStr("isolated-budget-test"))
    monkeypatch.setattr("app.services.providers.estimate_tokens", lambda text, model: (200, "isolated-test"))

    class FailingProvider:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, *args, **kwargs):
            return self

        async def ainvoke(self, *args):
            raise TimeoutError("Explicit isolated timeout")

    monkeypatch.setattr("app.services.providers.ChatOpenAI", FailingProvider)
    provider = ModelProvider()
    with pytest.raises(TimeoutError):
        await provider.structured(SemanticVerdict, "Isolated test", {})
    reserved = provider.usage.calls[0]["reserved_input_tokens"]
    monkeypatch.setattr(cfg, "max_input_tokens", reserved)
    with pytest.raises(RuntimeError):
        await provider.structured(SemanticVerdict, "Isolated test", {})
    assert len(provider.usage.calls) == 1
    assert not provider.usage.export()["token_accounting_complete"]


async def add_evidence(client, auth, library, count):
    paper_id, source_id = await setup_paper(client, auth, library)
    async with Session() as db:
        paper = await db.get(Paper, paper_id)
        await db.execute(
            insert(Evidence),
            [
                {
                    "id": uid(),
                    "paper_id": paper_id,
                    "library_id": library,
                    "owner_id": paper.owner_id,
                    "kind": "paragraph",
                    "text": "target unique" if n == 0 else "other document",
                    "locator": {},
                }
                for n in range(count)
            ],
        )
        await db.commit()
        target = await db.scalar(
            select(Evidence).where(Evidence.paper_id == paper_id, Evidence.text == "target unique")
        )
    return paper_id, target


async def test_more_than_10k_and_dense_only_candidate_hydration(client, auth, library, monkeypatch):
    import app.retrieval as retrieval

    async def explicit_embedding_fixture(texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(retrieval, "embed", explicit_embedding_fixture)
    paper_id, target = await add_evidence(client, auth, library, 10001)
    await retrieval.index_documents(
        "evidence",
        [
            {
                "id": target.id,
                "paper_id": paper_id,
                "owner_id": target.owner_id,
                "library_id": library,
                "text": target.text,
            }
        ],
    )
    for mode in ("bm25", "dense"):
        r = await client.post(
            "/api/v1/search", headers=auth, json={"library_id": library, "query": "target", "mode": mode}
        )
        assert r.status_code == 200, r.text
        assert r.json()["items"][0]["id"] == target.id
    monkeypatch.setattr(settings(), "bm25_max_documents", 1)
    # A new revision forces a cold lexical index, where configured capacity must return a business error.
    async with Session() as db:
        await touch_library(db, library)
        await db.commit()
    r = await client.post(
        "/api/v1/search", headers=auth, json={"library_id": library, "query": "target", "mode": "bm25"}
    )
    assert r.status_code == 422
    r = await client.post(
        "/api/v1/search", headers=auth, json={"library_id": library, "query": "target", "mode": "dense"}
    )
    assert r.status_code == 200


async def test_cached_lexical_index_invalidates_on_committed_revision(client, auth, library, monkeypatch):
    import app.retrieval as retrieval

    _, target = await add_evidence(client, auth, library, 3)
    original = retrieval.BM25Okapi
    builds = []

    def counting_scorer(*args, **kwargs):
        builds.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(retrieval, "BM25Okapi", counting_scorer)

    async def request(word):
        return await client.post(
            "/api/v1/search", headers=auth, json={"library_id": library, "query": word, "mode": "bm25"}
        )

    assert (await request("target")).json()["items"]
    assert (await request("target")).json()["items"]
    assert len(builds) == 1
    async with Session() as db:
        await db.execute(update(Evidence).where(Evidence.id == target.id).values(text="replacement evidence"))
        await touch_library(db, library)
        await db.commit()
    assert not (await request("target")).json()["items"]
    assert (await request("replacement")).json()["items"][0]["id"] == target.id
    assert len(builds) == 2


async def test_indexed_json_filter_and_numeric_equivalence(client, auth, library, synthetic_record):
    paper_id, _ = await setup_paper(client, auth, library)
    async with Session() as db:
        paper = await db.get(Paper, paper_id)
        data = synthetic_record.model_dump(mode="json")
        data["average_bits"] = "2.500"
        data["model_architecture"] = " MoE "
        db.add(
            Experiment(
                id=uid(),
                paper_id=paper_id,
                library_id=library,
                owner_id=paper.owner_id,
                fingerprint="indexed-json",
                record=data,
                original_record=data,
            )
        )
        await db.commit()
        rows = await query_experiments(
            db,
            paper.owner_id,
            ExperimentFilters(library_id=library, average_bits="2.5", model_architecture="moe"),
        )
        assert len(rows) == 1
        stmt = select(Experiment.id).where(
            Experiment.owner_id == paper.owner_id,
            Experiment.library_id == library,
            experiment_filter_expression("average_bits") == 2.5,
        )
        sql = str(stmt.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))
        plan = (await db.execute(text("EXPLAIN QUERY PLAN " + sql))).all()
        assert any("ix_experiment_json_average_bits" in str(row) for row in plan)


async def test_paper_index_projects_abstract_without_raw_document(client, auth, library):
    paper_id, _ = await setup_paper(client, auth, library)
    async with Session() as db:
        paper = await db.get(Paper, paper_id)
        paper.metadata_json = {
            "abstract": "Projected abstract sentinel",
            "document": {"secret-sentinel": "raw layout data"},
        }
        await touch_library(db, library)
        await db.commit()
    r = await client.post(
        "/api/v1/search",
        headers=auth,
        json={"library_id": library, "query": "Projected", "mode": "bm25", "level": "paper"},
    )
    assert r.status_code == 200
    assert r.json()["items"][0]["paper_id"] == paper_id
    assert "Projected abstract" in r.json()["items"][0]["text"]
    assert "raw layout" not in r.text


def test_tokenizer_estimate_and_unknown_fallback(monkeypatch):
    from app.services.providers import estimate_tokens

    class LocalEncoding:
        def encode(self, text, **kwargs):
            return [1, 2, 3]

    monkeypatch.setattr("app.services.providers.model_encoding", lambda model: LocalEncoding())
    assert estimate_tokens("Long " * 1000, "known-model") == (35, "model_tokenizer")
    monkeypatch.setattr("app.services.providers.model_encoding", lambda model: None)
    assert estimate_tokens("中文", "unknown-model") == (38, "utf8_upper_bound")
