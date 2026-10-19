from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.agents.research import classify
from app.experiments import (
    ComparisonRules,
    align_record,
    compare,
    measurement_equal,
    parse_measurement,
    verify_claim,
)
from app.ingestion.parser import chunk_section
from app.retrieval import bm25, retrieval_metrics, rrf
from app.schemas import AtomicClaim, ExperimentRecord


@pytest.mark.parametrize(
    ("field", "value", "status"),
    [
        (None, None, "COMPARABLE"),
        ("average_bits", Decimal("3"), "PARTIALLY_COMPARABLE"),
        ("metric_name", "perplexity", "NOT_COMPARABLE"),
        ("calibration_samples", 128, "PARTIALLY_COMPARABLE"),
        ("model_version", None, "INSUFFICIENT_INFORMATION"),
        ("dataset_split", "test", "NOT_COMPARABLE"),
        ("quantized_components", ["all_weights"], "PARTIALLY_COMPARABLE"),
    ],
)
def test_comparison(synthetic_record, field, value, status):
    other = synthetic_record.model_copy(update={field: value} if field else {})
    result = compare(synthetic_record, other)
    assert result["status"] == status
    if field == "average_bits":
        assert any("equal-budget" in w for w in result["warnings"])


def test_domain_rules(synthetic_record):
    rule = ComparisonRules(domain="general", required=["model_name"], hard=["model_name"], soft=[])
    assert compare(synthetic_record, synthetic_record, rule)["status"] == "COMPARABLE"
    with pytest.raises(ValueError):
        compare(synthetic_record, synthetic_record, ComparisonRules(required=["arbitrary_sql"]))


@pytest.mark.parametrize(
    ("raw", "unit", "value"),
    [("79.2%", "unknown", "79.2"), ("0.792", "fraction", "0.792"), ("79.2 ± 0.3", "percent", "79.2")],
)
def test_normalization(raw, unit, value):
    parsed = parse_measurement(raw, unit)
    assert parsed["value"] == Decimal(value)
    assert parsed["original"] == raw


def test_units_not_guessed():
    assert not measurement_equal("0.79", "unknown", "79", "percent")
    assert not measurement_equal("0.79", "score", "79", "percent")
    assert measurement_equal("0.79", "fraction", "79", "percent")
    for value in ("--", "79/80", "101%", "79.2 (best)"):
        with pytest.raises(ValueError):
            parse_measurement(value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_schema(value):
    with pytest.raises(ValidationError):
        ExperimentRecord(metric_value=value)


def test_alignment_and_wrong_column(synthetic_record):
    evidence = {
        "evidence-a": {
            "paper_id": "paper-a",
            "page": 7,
            "section": "Experiments",
            "text": "Method | PIQA\nMethod A | 79.2",
            "locator": {
                "table_id": "table-3",
                "captions": ["TestMoE evaluation, accuracy (%)"],
                "cells": [
                    {"row": 0, "col": 1, "end_col": 2, "text": "PIQA", "column_header": True},
                    {"row": 1, "col": 0, "text": "Method A"},
                    {"row": 1, "col": 1, "text": "79.2"},
                ],
            },
        }
    }
    record = align_record(synthetic_record, evidence)
    assert record.verification_status == "supported"
    assert record.provenance.page_number == 7
    assert record.provenance.location_precision == "cell"
    wrong = synthetic_record.model_copy(deep=True)
    wrong.metric_value = Decimal("80.2")
    assert align_record(wrong, evidence).verification_status == "contradicted"
    wrong = synthetic_record.model_copy(deep=True)
    wrong.provenance.original_value = "80.2"
    wrong.metric_value = Decimal("80.2")
    assert align_record(wrong, evidence).verification_status == "contradicted"
    wrong = synthetic_record.model_copy(deep=True)
    wrong.dataset_name = "ARC"
    assert align_record(wrong, evidence).verification_status == "insufficient"


@pytest.mark.parametrize(
    ("patch", "expected"),
    [
        ({}, "supported"),
        ({"metric_value": "80.1"}, "contradicted"),
        ({"metric_name": "perplexity"}, "contradicted"),
        ({"dataset_name": "ARC"}, "contradicted"),
        ({"model_name": "Other"}, "contradicted"),
        ({"evidence_ids": ["invented-id"]}, "insufficient"),
        ({"average_bits": "4"}, "contradicted"),
    ],
)
def test_claim_validation(synthetic_record, patch, expected):
    synthetic_record.verification_status = "supported"
    claim = AtomicClaim.model_validate(
        {
            "text": "synthetic measurement",
            "experiment_id": "exp-a",
            "metric_value": "79.2",
            "metric_unit": "percent",
            "metric_name": "accuracy",
            "dataset_name": "PIQA",
            "model_name": "TestMoE",
            "evidence_ids": ["evidence-a"],
            **patch,
        }
    )
    from test_evaluation import source_fixture

    result = verify_claim(claim, {"evidence-a": source_fixture()}, {"exp-a": synthetic_record})
    assert result["status"] == expected


def test_unsupported_numerical_claim():
    claim = AtomicClaim(text="unbacked", metric_value="79", metric_unit="percent", evidence_ids=["e"])
    assert verify_claim(claim, {"e": {}}, {})["status"] == "insufficient"


def test_bm25_rrf_and_metrics():
    documents = [
        {"id": "a", "text": "quantization mixed precision expert"},
        {"id": "b", "text": "image classification dense model"},
        {"id": "c", "text": "retrieval evidence scientific paper"},
    ]
    assert bm25("quantization", documents)[0]["id"] == "a"
    assert bm25("nonexistent", documents) == []
    ranking = rrf([[documents[0], documents[1]], [documents[1], documents[2]]])
    assert ranking[0]["id"] == "b"
    assert rrf([[documents[0], documents[0]]])[0]["score"] == pytest.approx(1 / 61)
    metrics = retrieval_metrics(["b", "a"], ["a"])
    assert metrics["mrr"] == 0.5
    assert metrics["recall@5"] == 1
    assert 0 < metrics["ndcg@10"] < 1


def test_chunking_termination():
    text = "experimental conditions " * 500
    chunks = chunk_section(text)
    assert len(chunks) > 1
    assert all(len(c) <= 1800 for c in chunks)
    assert chunks[-1].endswith("conditions")
    with pytest.raises(ValueError):
        chunk_section(text, size=100, overlap=100)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("比较两种量化方法", "comparison"),
        ("PIQA accuracy", "experiment_lookup"),
        ("write a literature survey", "research"),
        ("What is the strategy?", "basic_qa"),
        ("哪张表给出结果？", "section_retrieval"),
        ("它的实验结果主要来自哪张表？", "section_retrieval"),
    ],
)
def test_router(query, expected):
    assert classify(query) == expected
