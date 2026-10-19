"""Explicitly isolated provider doubles; live provider evidence is stored separately."""

import pytest
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from app.core.config import settings
from app.experiments import SemanticVerdict
from app.services.providers import ModelProvider


@pytest.mark.parametrize("always_invalid", [False, True])
async def test_schema_repair_is_bounded_and_metered(monkeypatch, always_invalid):
    import app.services.providers as providers

    monkeypatch.setattr(settings(), "api_key", SecretStr("isolated-test-provider"))

    class TestChat:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, *args, **kwargs):
            return self

        async def ainvoke(self, messages):
            invalid = always_invalid or not any(
                "Previous response failed" in str(m.content) for m in messages
            )
            return {
                "raw": AIMessage(
                    content="{}", usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
                ),
                "parsing_error": ValueError("synthetic schema failure") if invalid else None,
                "parsed": None
                if invalid
                else SemanticVerdict(status="supported", rationale="synthetic test"),
            }

    monkeypatch.setattr(providers, "ChatOpenAI", TestChat)
    provider = ModelProvider()
    if always_invalid:
        with pytest.raises(ValueError):
            await provider.structured(SemanticVerdict, "Test only", {})
    else:
        assert (await provider.structured(SemanticVerdict, "Test only", {})).status == "supported"
    assert len(provider.usage.calls) == 2
    assert provider.usage.input_tokens == 20
    assert provider.usage.output_tokens == 10
    assert provider.usage.calls[-1]["schema_repair"] is True


async def test_failed_call_marks_incomplete_accounting(monkeypatch):
    import app.services.providers as providers

    monkeypatch.setattr(settings(), "api_key", SecretStr("isolated-test-provider"))
    monkeypatch.setattr(settings(), "input_cost_per_million", 1)
    monkeypatch.setattr(settings(), "output_cost_per_million", 1)

    class FailingChat:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, *args, **kwargs):
            return self

        async def ainvoke(self, messages):
            raise TimeoutError("explicit test timeout")

    monkeypatch.setattr(providers, "ChatOpenAI", FailingChat)
    provider = ModelProvider()
    with pytest.raises(TimeoutError):
        await provider.structured(SemanticVerdict, "Test only", {})
    assert provider.usage.export()["token_accounting_complete"] is False
    assert provider.usage.export()["estimated_cost_usd"] is None
