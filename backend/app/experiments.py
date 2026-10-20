import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import Field

from app.schemas import AtomicClaim, ExperimentRecord, StrictModel

ALIASES = {
    "acc": "accuracy",
    "acc.": "accuracy",
    "ppl": "perplexity",
    "piqa": "piqa",
    "physical interaction qa": "piqa",
    "wikitext-2": "wikitext2",
    "wiki text 2": "wikitext2",
}


def canonical(value):
    if value is None:
        return None
    if isinstance(value, list):
        return sorted(canonical(v) for v in value)
    if isinstance(value, (Decimal, int, float)):
        return Decimal(str(value))
    if isinstance(value, dict):
        return value
    text = str(value).strip().casefold()
    return ALIASES.get(text, text)


def parse_measurement(raw: str, unit: str = "unknown") -> dict:
    """Explicit units only: 0.79 is NOT inferred to mean 79%."""
    raw = raw.strip().replace("−", "-")
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(%)?(?:\s*(?:±|\+/-)\s*(\d+(?:\.\d+)?)\s*(%)?)?", raw)
    if not match:
        raise ValueError("Ambiguous measurement; preserve raw text and request review")
    value = Decimal(match[1])
    resolved_unit = "percent" if match[2] else unit
    if match[4] and resolved_unit != "percent":
        raise ValueError("Mean and variance have different units")
    if resolved_unit == "percent" and not Decimal(0) <= value <= Decimal(100):
        raise ValueError("Percentage outside [0,100]")
    if resolved_unit == "fraction" and not Decimal(0) <= value <= Decimal(1):
        raise ValueError("Fraction outside [0,1]")
    return {"value": value, "unit": resolved_unit, "variance": match[3], "original": raw}


def measurement_equal(av, au, bv, bu) -> bool:
    if av is None or bv is None or au in (None, "unknown") or bu in (None, "unknown"):
        return False
    a, b = Decimal(str(av)), Decimal(str(bv))
    if au == "percent" and bu == "fraction":
        a /= 100
    elif au == "fraction" and bu == "percent":
        b /= 100
    elif au != bu:
        return False
    return a == b


def entity_matches(value: str | None, context: str) -> bool:
    """Match complete scientific names, including explicit aliases and version suffixes."""
    if not value:
        return False
    normalized = unicodedata.normalize("NFKC", context).casefold()
    target = canonical(unicodedata.normalize("NFKC", value))
    variants = {target, *(k for k, v in ALIASES.items() if v == target)}
    return any(
        re.search(
            r"(?<![\w.+/\-])" + r"\s+".join(re.escape(p) for p in name.split()) + r"(?![\w+/\-]|\.\w)",
            normalized,
        )
        for name in variants
    )


def metric_labels(context: str) -> set[str]:
    return {
        name
        for name in ("accuracy", "perplexity", "precision", "recall", "f1", "latency", "throughput")
        if entity_matches(name, context)
    }


def context_units(context: str) -> set[str]:
    context = context.casefold()
    units = set()
    for pattern, unit in (
        (r"%|\bpercent(?:age)?\b", "percent"),
        (r"\bfraction\b", "fraction"),
        (r"\b(?:perplexity|ppl|score)\b", "score"),
        (r"\bmilliseconds\b|\(\s*ms\s*\)", "ms"),
        (r"\bseconds\b|\(\s*s\s*\)", "seconds"),
        (r"\bcount\b", "count"),
    ):
        if re.search(pattern, context):
            units.add(unit)
    return units


def source_unit(raw: str, headers: str, captions: str = "") -> str:
    """Column-specific units take precedence; ambiguous shared captions stay unknown."""
    if "%" in raw:
        return "percent"
    units = context_units(headers)
    if not units:
        units = context_units(captions)
    return next(iter(units)) if len(units) == 1 else "unknown"


def verified_field(record: ExperimentRecord, key: str) -> bool:
    return record.field_verification.get(key) in ("supported", "reviewed")


class ComparisonRules(StrictModel):
    domain: str = "quantization"
    required: list[str] = Field(
        default=[
            "model_name",
            "model_version",
            "dataset_name",
            "dataset_split",
            "metric_name",
            "metric_definition",
            "metric_unit",
            "average_bits",
            "quantized_components",
            "evaluation_protocol",
        ]
    )
    hard: list[str] = Field(
        default=[
            "model_name",
            "model_version",
            "model_checkpoint",
            "dataset_name",
            "dataset_version",
            "dataset_split",
            "metric_name",
            "metric_definition",
            "metric_direction",
            "metric_unit",
            "evaluation_protocol",
        ]
    )
    soft: list[str] = Field(
        default=[
            "average_bits",
            "bit_width",
            "precision_type",
            "quantized_components",
            "quantization_scheme",
            "calibration_method",
            "calibration_samples",
            "seed_count",
            "reported_variance",
            "inference_settings",
            "hardware",
        ]
    )


def compare(a: ExperimentRecord, b: ExperimentRecord, rules: ComparisonRules | None = None) -> dict:
    rules = rules or ComparisonRules()
    matched, mismatched, missing, fields = [], [], [], []
    for key in dict.fromkeys(rules.required + rules.hard + rules.soft):
        if key not in ExperimentRecord.model_fields:
            raise ValueError(f"Unknown comparison field: {key}")
        av, bv = getattr(a, key), getattr(b, key)
        if av is None or bv is None or av == "unknown" or bv == "unknown":
            state = "missing"
            if key in rules.required or av != bv:
                missing.append(key)
        elif not verified_field(a, key) or not verified_field(b, key):
            state = "unverified"
            missing.append(key)
        elif key == "metric_unit" and {av, bv} <= {"percent", "fraction"}:
            state = "matched"
            matched.append(key)
        elif canonical(av) == canonical(bv):
            state = "matched"
            matched.append(key)
        else:
            state = "mismatched"
            mismatched.append(key)
        fields.append(
            {
                "field": key,
                "left": av,
                "right": bv,
                "status": state,
                "severity": "hard" if key in rules.hard else "soft",
                "left_evidence": a.provenance.field_sources.get(key, []) if verified_field(a, key) else [],
                "right_evidence": b.provenance.field_sources.get(key, []) if verified_field(b, key) else [],
            }
        )
    if a.verification_status != "supported" or b.verification_status != "supported":
        missing.append("measurement_evidence")
    hard_mismatch = set(mismatched) & set(rules.hard)
    if hard_mismatch:
        status = "NOT_COMPARABLE"
    elif missing:
        status = "INSUFFICIENT_INFORMATION"
    elif mismatched:
        status = "PARTIALLY_COMPARABLE"
    else:
        status = "COMPARABLE"
    warnings = []
    if "average_bits" in mismatched:
        warnings.append("Average precision differs: these results are not an equal-budget comparison.")
    if "calibration_samples" in mismatched:
        warnings.append(
            "Calibration sample counts differ; a higher reported score does not establish a controlled advantage."
        )
    if missing:
        warnings.append("Unknown conditions are not assumed equal: " + ", ".join(missing))
    warnings.append("Comparability does not establish statistical significance or causal superiority.")
    return {
        "status": status,
        "domain": rules.domain,
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
        "conditions": fields,
        "warnings": warnings,
        "evidence_ids": sorted(set(a.provenance.evidence_ids + b.provenance.evidence_ids)),
        "explanation": f"{status}: {len(matched)} matched conditions, {len(mismatched)} differences, {len(missing)} unresolved conditions.",
    }


def align_record(record: ExperimentRecord, evidence: dict[str, dict]) -> ExperimentRecord:
    """Validate model-supplied pointers against server-owned PDF locations."""
    record = record.model_copy(deep=True)
    # This map is server-owned. Model/client declarations cannot certify their own fields.
    record.field_verification = {}
    record.extraction_status = "needs_review"
    p = record.provenance
    valid = [i for i in p.evidence_ids if i in evidence]
    if not valid or len(valid) != len(p.evidence_ids):
        record.verification_status = "insufficient"
        record.warnings.append("Missing or unauthorized evidence ID")
        p.evidence_ids = valid
        return record
    source = evidence[valid[0]]
    p.paper_id = source["paper_id"]
    record.paper_id = source["paper_id"]
    p.page_number = source.get("page")
    p.section_name = source.get("section")
    p.table_id = source.get("locator", {}).get("table_id")
    p.original_text = source["text"][:12000]
    p.field_sources = {}
    p.location_precision = "snippet"
    record.verification_status = "insufficient"
    if record.metric_value is None or not p.original_value:
        record.warnings.append("No unambiguous original measurement")
        return record
    try:
        # Cell/header unit validation is performed once its source context is available below.
        parsed = parse_measurement(p.original_value)
        # Exact cell association is required to certify a table value. A number elsewhere is insufficient.
        cells = source.get("locator", {}).get("cells", [])
        row, col = p.row_index, p.column_index
        if row is None or col is None:
            try:
                row = int(p.row_identifier) if p.row_identifier is not None else None
                col = int(p.column_identifier) if p.column_identifier is not None else None
            except ValueError:
                row, col = None, None
        if row is None or col is None:
            candidates = [c for c in cells if c["text"].strip() == p.original_value.strip()]
            if len(candidates) == 1:
                row, col = candidates[0]["row"], candidates[0]["col"]
                record.warnings.append(
                    "Cell offsets resolved by unique exact literal; entity/header checks still applied"
                )
        p.row_index, p.column_index = row, col
        cell = next((c for c in cells if c["row"] == row and c["col"] == col), None)
        if cell and cell["text"].strip() == p.original_value.strip():
            headers = " ".join(
                c["text"]
                for c in cells
                if c.get("column_header") and c["col"] <= col < c.get("end_col", c["col"] + 1)
            )
            row_labels = " ".join(c["text"] for c in cells if c["row"] == row and c["col"] < col)
            captions = " ".join(source.get("locator", {}).get("captions", []))
            all_headers = " ".join(c["text"] for c in cells if c.get("column_header") and c["col"] == 0)
            context = headers + " " + row_labels + " " + captions + " " + all_headers
            dataset_matches = entity_matches(record.dataset_name, context)
            model_matches = entity_matches(record.model_name, context)
            # Some tables put methods in columns and models in rows; preserve both orientations.
            # Multi-level headers can place the method and budget on different rows.
            header_context = " ".join(
                c["text"]
                for c in cells
                if c.get("column_header") and c["col"] <= col < c.get("end_col", c["col"] + 1)
            )
            method_matches = entity_matches(record.method_name, header_context + " " + row_labels)
            column_metrics = metric_labels(headers)
            caption_metrics = metric_labels(captions)
            metric_matches = (
                canonical(record.metric_name) in column_metrics
                if column_metrics
                else len(caption_metrics) <= 1 and entity_matches(record.metric_name, context)
            )
            unit = source_unit(cell["text"], headers, captions)
            if unit == "unknown":
                record.warnings.append("Source unit could not be independently established")
                return record
            parsed = parse_measurement(cell["text"], unit)
            if not measurement_equal(parsed["value"], unit, record.metric_value, record.metric_unit):
                record.verification_status = "contradicted"
                record.warnings.append("Metric unit/value conflicts with the original cell or metric label")
                return record
            if (
                dataset_matches
                and method_matches
                and metric_matches
                and (model_matches or not record.model_name)
            ):
                p.location_precision = "cell"
                record.verification_status = "supported"
                for key in (
                    "method_name",
                    "model_name",
                    "dataset_name",
                    "metric_name",
                    "metric_value",
                    "metric_unit",
                ):
                    if getattr(record, key) is not None:
                        record.field_verification[key] = "supported"
                        p.field_sources[key] = valid
            else:
                record.warnings.append(
                    "Dataset, model, method or metric could not be aligned with headers/caption"
                )
        elif cell:
            record.verification_status = "contradicted"
            record.warnings.append("Measurement does not match addressed table cell")
        else:
            record.warnings.append(
                "Snippet-only location: manual review or independent semantic verification required"
            )
        record.normalization = {
            "original_value": p.original_value,
            "value": str(parsed["value"]),
            "unit": parsed["unit"],
            "variance": parsed["variance"],
        }
        if parsed["variance"]:
            record.reported_variance = parsed["variance"]
    except (ValueError, TypeError, InvalidOperation):
        record.warnings.append("Measurement or cell address is ambiguous")
    record.extraction_status = "extracted" if record.verification_status == "supported" else "needs_review"
    return record


class SemanticVerdict(StrictModel):
    status: Literal["supported", "contradicted", "insufficient"]
    rationale: str


def verify_claim(
    claim: AtomicClaim, evidence: dict[str, dict], experiments: dict[str, ExperimentRecord]
) -> dict:
    reasons = []
    if not claim.evidence_ids or any(i not in evidence for i in claim.evidence_ids):
        return {"status": "insufficient", "reasons": ["Invalid, absent or unauthorized citation"]}
    record = experiments.get(claim.experiment_id)
    if claim.metric_value is not None and record is None:
        return {"status": "insufficient", "reasons": ["Numerical claims require a structured experiment"]}
    if record:
        verified_average_bits = verified_field(record, "average_bits")
        # Recheck persisted records as well, including those extracted before stricter validation.
        record = align_record(record, evidence)
        if not set(record.provenance.evidence_ids) & set(claim.evidence_ids):
            reasons.append("Citation does not support the selected experiment")
        for key in ("method_name", "model_name", "dataset_name", "metric_name", "average_bits"):
            value = getattr(claim, key)
            if value is not None and canonical(value) != canonical(getattr(record, key)):
                reasons.append(f"{key} mismatch")
        if claim.metric_value is not None and not measurement_equal(
            claim.metric_value, claim.metric_unit, record.metric_value, record.metric_unit
        ):
            reasons.append("Metric value or unit mismatch")
        if reasons:
            return {"status": "contradicted", "reasons": reasons}
        if record.verification_status != "supported":
            return {
                "status": "insufficient",
                "reasons": ["Experiment has not been aligned to its original evidence"],
            }
        if claim.average_bits is not None and not verified_average_bits:
            return {"status": "insufficient", "reasons": ["Average bits lacks verified source conditions"]}
        if claim.metric_value is not None:
            # Render numerical prose on the server, so arbitrary model text cannot smuggle in other numbers.
            return {"status": "supported", "reasons": ["Structured fields, unit and source cell match"]}
    return {
        "status": "needs_semantic_check",
        "reasons": ["Textual entailment needs independent verification"],
    }


def render_numeric_claim(claim: AtomicClaim, record: ExperimentRecord) -> str:
    unit = "%" if claim.metric_unit == "percent" else f" {claim.metric_unit}"
    return f"{record.method_name or 'Reported method'} — {record.model_name or 'unknown model'} / {record.dataset_name or 'unknown dataset'}: {claim.metric_value}{unit} {record.metric_name or 'unknown metric'}."
