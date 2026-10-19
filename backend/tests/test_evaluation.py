import pytest

from app.evaluation import claim_metrics, classification_metrics, extraction_metrics
from app.experiments import align_record


def test_evaluation_does_not_invent_labels(synthetic_record):
    score = classification_metrics(["COMPARABLE", "INSUFFICIENT_INFORMATION"], ["COMPARABLE", "COMPARABLE"])
    assert score["accuracy"] == 0.5
    assert score["unknown_detection_accuracy"] == 0
    assert extraction_metrics([synthetic_record], [synthetic_record])["record_exact_match"] == 1
    altered = synthetic_record.model_copy(update={"dataset_name": "ARC"})
    assert extraction_metrics([synthetic_record], [altered])["field_f1"] < 1
    assert (
        claim_metrics([True, False], [True, True], [True, False], [True, False])["unsupported_claim_rate"]
        == 0.5
    )
    with pytest.raises(ValueError):
        extraction_metrics([synthetic_record], [])


def source_fixture():
    return {
        "paper_id": "p",
        "page": 7,
        "section": "Experiments",
        "text": "test table",
        "locator": {
            "captions": ["TestMoE accuracy (%)"],
            "cells": [
                {"row": 0, "col": 1, "end_col": 2, "column_header": True, "text": "PIQA"},
                {"row": 1, "col": 0, "text": "Method A"},
                {"row": 1, "col": 1, "text": "79.2"},
            ],
        },
    }


def test_unique_cell_location_and_ambiguous_duplicates(synthetic_record):
    synthetic_record.provenance.row_identifier = "Method A"
    synthetic_record.provenance.column_identifier = "PIQA"
    source = source_fixture()
    aligned = align_record(synthetic_record, {"evidence-a": source})
    assert aligned.verification_status == "supported"
    assert aligned.provenance.row_index == 1
    source["locator"]["cells"].append({"row": 2, "col": 1, "text": "79.2"})
    assert align_record(synthetic_record, {"evidence-a": source}).verification_status == "insufficient"


def test_public_chat_cannot_disable_verification():
    from pydantic import ValidationError

    from app.schemas import ChatInput

    with pytest.raises(ValidationError):
        ChatInput(library_id="x", query="x", verification=False)


def test_model_context_keeps_measurements_without_repeated_source(synthetic_record):
    from app.agents.research import model_experiments

    synthetic_record.provenance.original_text = "private source text" * 1000
    compact = model_experiments([synthetic_record.model_dump(mode="json")])[0]
    assert compact["metric_value"] == "79.2"
    assert compact["evidence_ids"] == ["evidence-a"]
    assert "provenance" not in compact
