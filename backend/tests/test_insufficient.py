from pydantic import SecretStr

from app.core.config import settings
from app.core.db import Session
from app.models import Evidence, Paper, uid
from app.schemas import Plan


async def test_unmatched_experiment_filter_does_not_generate_unrelated_claims(
    client, auth, library, monkeypatch
):
    from app.services.providers import ModelProvider

    monkeypatch.setattr(settings(), "api_key", SecretStr("isolated-test-provider"))
    called = []

    async def test_model(self, schema, instruction, data):
        called.append(schema.__name__)
        if schema is Plan:
            return Plan(
                task_type="comparison",
                queries=["synthetic quantization"],
                filters={"model_name": "MissingModel"},
            )
        raise AssertionError("Generation must not run without matching experiments")

    monkeypatch.setattr(ModelProvider, "structured", test_model)
    owner = (await client.get("/api/v1/auth/me", headers=auth)).json()["id"]
    async with Session() as db:
        paper = Paper(
            id=uid(),
            library_id=library,
            owner_id=owner,
            title="Synthetic scope test",
            filename="test.pdf",
            sha256="c" * 64,
            status="ready",
        )
        db.add(paper)
        await db.flush()
        db.add(
            Evidence(
                id=uid(),
                paper_id=paper.id,
                library_id=library,
                owner_id=owner,
                kind="paragraph",
                text="Synthetic quantization paper with no matching experiment",
                page=1,
            )
        )
        await db.commit()
    response = await client.post(
        "/api/v1/research/chat",
        headers=auth,
        json={"library_id": library, "query": "Compare quantization on MissingModel", "mode": "bm25"},
    )
    assert response.status_code == 200, response.text
    assert called == ["Plan"]
    assert "未找到符合当前范围与条件的结构化实验记录" in response.json()["answer"]
    assert response.json()["verification"] == []
