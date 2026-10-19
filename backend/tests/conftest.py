import os
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="papermind-test-"))
os.environ["PM_DATABASE_URL"] = f"sqlite+aiosqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["PM_STORAGE_PATH"] = str(TEST_ROOT)
os.environ["PM_PARSER"] = "pypdf"
os.environ["PM_API_KEY"] = ""
os.environ["PM_RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["PM_TASK_EAGER"] = "true"

from app.core.db import engine  # noqa: E402
from app.main import app, windows  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
async def clean_database():
    windows.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def account(client, email="alice@example.org"):
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "test-password-123"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
async def auth(client):
    return await account(client)


@pytest.fixture
async def library(client, auth):
    response = await client.post("/api/v1/libraries", headers=auth, json={"name": "Synthetic test library"})
    return response.json()["id"]


@pytest.fixture
def synthetic_record():
    from app.schemas import ExperimentRecord, Provenance

    return ExperimentRecord(
        method_name="Method A",
        model_name="TestMoE",
        model_version="v1",
        dataset_name="PIQA",
        dataset_split="validation",
        metric_name="accuracy",
        metric_value="79.2",
        metric_unit="percent",
        metric_direction="higher",
        metric_definition="correct / total",
        average_bits="2.50",
        quantized_components=["expert_weights"],
        evaluation_protocol="zero-shot harness 0.4",
        calibration_samples=512,
        verification_status="supported",
        field_verification={
            key: "reviewed"
            for key in (
                "model_name",
                "model_version",
                "dataset_name",
                "dataset_split",
                "metric_name",
                "metric_value",
                "metric_unit",
                "metric_direction",
                "metric_definition",
                "average_bits",
                "quantized_components",
                "evaluation_protocol",
                "calibration_samples",
            )
        },
        provenance=Provenance(
            evidence_ids=["evidence-a"], original_value="79.2", row_identifier="1", column_identifier="1"
        ),
    )
