"""Transparent reference metrics. No LLM judge is silently substituted for labels."""

from collections import Counter

from app.experiments import canonical, measurement_equal
from app.schemas import ExperimentRecord


def classification_metrics(expected: list[str], predicted: list[str]) -> dict:
    if len(expected) != len(predicted) or not expected:
        raise ValueError("Nonempty aligned predictions and labels are required")
    labels = sorted(set(expected) | set(predicted))
    per_class = {}
    for label in labels:
        tp = sum(a == b == label for a, b in zip(expected, predicted, strict=True))
        fp = sum(a != label and b == label for a, b in zip(expected, predicted, strict=True))
        fn = sum(a == label and b != label for a, b in zip(expected, predicted, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "support": expected.count(label),
        }
    unknown = [i for i, v in enumerate(expected) if v == "INSUFFICIENT_INFORMATION"]
    return {
        "accuracy": sum(a == b for a, b in zip(expected, predicted, strict=True)) / len(expected),
        "macro_f1": sum(v["f1"] for v in per_class.values()) / len(per_class),
        "per_class": per_class,
        "unknown_detection_accuracy": sum(predicted[i] == expected[i] for i in unknown) / len(unknown)
        if unknown
        else None,
        "label_counts": dict(Counter(expected)),
    }


def extraction_metrics(expected: list[ExperimentRecord], predicted: list[ExperimentRecord]) -> dict:
    """Aligned record pairs only. Callers must adjudicate matching, omissions and extra records."""
    if len(expected) != len(predicted) or not expected:
        raise ValueError("Align record pairs explicitly; extra/missing records need separate adjudication")
    fields = [
        "method_name",
        "model_name",
        "model_version",
        "dataset_name",
        "dataset_split",
        "metric_name",
        "metric_unit",
        "metric_value",
        "average_bits",
        "bit_width",
        "calibration_samples",
        "quantized_components",
        "evaluation_protocol",
    ]
    tp = fp = fn = exact = numeric = unit = alignment = 0
    for gold, output in zip(expected, predicted, strict=True):
        all_match = True
        for field in fields:
            a, b = getattr(gold, field), getattr(output, field)
            equal = canonical(a) == canonical(b)
            if a is not None and b is not None and equal:
                tp += 1
            else:
                fp += int(b is not None)
                fn += int(a is not None)
            all_match &= equal
        exact += all_match
        numeric += measurement_equal(
            gold.metric_value, gold.metric_unit, output.metric_value, output.metric_unit
        )
        unit += gold.metric_unit == output.metric_unit
        alignment += (
            gold.provenance.page_number == output.provenance.page_number
            and gold.provenance.evidence_ids == output.provenance.evidence_ids
            and gold.provenance.row_index == output.provenance.row_index
            and gold.provenance.column_index == output.provenance.column_index
        )
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    return {
        "field_precision": precision,
        "field_recall": recall,
        "field_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
        "record_exact_match": exact / len(expected),
        "numeric_exact_match": numeric / len(expected),
        "unit_normalization_accuracy": unit / len(expected),
        "evidence_alignment_accuracy": alignment / len(expected),
        "record_pairs": len(expected),
    }


def claim_metrics(
    expected_supported: list[bool],
    predicted_supported: list[bool],
    citations_valid: list[bool],
    numeric_correct: list[bool],
) -> dict:
    if len(expected_supported) != len(predicted_supported) or not expected_supported:
        raise ValueError("Aligned nonempty claim judgments are required")
    supported = sum(predicted_supported)
    correct = sum(a and b for a, b in zip(expected_supported, predicted_supported, strict=True))
    return {
        "evidence_support_precision": correct / supported if supported else None,
        "unsupported_claim_rate": (supported - correct) / supported if supported else 0,
        "citation_validity": sum(citations_valid) / len(citations_valid) if citations_valid else None,
        "numerical_claim_accuracy": sum(numeric_correct) / len(numeric_correct) if numeric_correct else None,
    }
