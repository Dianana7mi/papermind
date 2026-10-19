from app.core.db import Session
from app.models import Evidence, Experiment, Paper, uid


async def test_comparison_conversation_persists_decimal_conditions(client, auth, library, synthetic_record):
    owner = (await client.get("/api/v1/auth/me", headers=auth)).json()["id"]
    async with Session() as db:
        paper = Paper(
            id=uid(),
            library_id=library,
            owner_id=owner,
            title="Synthetic comparison persistence fixture",
            filename="test.pdf",
            sha256="d" * 64,
            status="ready",
        )
        db.add(paper)
        await db.flush()
        source = Evidence(
            id=uid(),
            paper_id=paper.id,
            library_id=library,
            owner_id=owner,
            kind="paragraph",
            text="Synthetic PIQA quantization evidence",
            page=1,
        )
        db.add(source)
        for name in ("Synthetic A", "Synthetic B"):
            record = synthetic_record.model_copy(deep=True)
            record.experiment_id = uid()
            record.paper_id = paper.id
            record.method_name = name
            record.provenance.evidence_ids = [source.id]
            data = record.model_dump(mode="json")
            db.add(
                Experiment(
                    id=record.experiment_id,
                    paper_id=paper.id,
                    library_id=library,
                    owner_id=owner,
                    fingerprint=uid(),
                    record=data,
                    original_record=data,
                )
            )
        await db.commit()
    response = await client.post(
        "/api/v1/research/chat",
        headers=auth,
        json={"library_id": library, "query": "Compare PIQA quantization", "mode": "bm25"},
    )
    assert response.status_code == 200, response.text
    output = response.json()
    assert output["comparisons"]
    condition = next(c for c in output["comparisons"][0]["conditions"] if c["field"] == "average_bits")
    assert condition["left"] == "2.50"
    conversation = await client.get(
        "/api/v1/research/conversations/" + output["conversation_id"], headers=auth
    )
    assert conversation.status_code == 200
    assert conversation.json()["items"][-1]["details"]["comparisons"] == output["comparisons"]
