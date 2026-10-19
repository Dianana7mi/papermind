from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(StrictModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=10, max_length=128)


class LibraryInput(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)


class Provenance(StrictModel):
    paper_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    section_name: str | None = None
    table_id: str | None = None
    row_identifier: str | None = None
    column_identifier: str | None = None
    row_index: int | None = Field(default=None, ge=0)
    column_index: int | None = Field(default=None, ge=0)
    original_value: str | None = None
    original_text: str | None = None
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    field_sources: dict[str, list[str]] = Field(default_factory=dict)
    location_precision: Literal["cell", "snippet", "unknown"] = "unknown"


class ExperimentRecord(StrictModel):
    experiment_id: str | None = None
    paper_id: str | None = None
    method_name: str | None = None
    experiment_group: str | None = None
    source_type: Literal["table", "paragraph", "manual"] = "paragraph"
    extraction_version: str = "1.0"
    extraction_model: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    model_size: str | None = None
    model_architecture: str | None = None
    model_checkpoint: str | None = None
    dataset_name: str | None = None
    dataset_version: str | None = None
    dataset_split: str | None = None
    evaluation_protocol: str | None = None
    metric_name: str | None = None
    metric_value: Decimal | None = None
    metric_unit: Literal["percent", "fraction", "count", "seconds", "ms", "score", "unknown"] = "unknown"
    metric_direction: Literal["higher", "lower", "unknown"] = "unknown"
    metric_definition: str | None = None
    quantization_method: str | None = None
    precision_type: str | None = None
    bit_width: Decimal | None = Field(default=None, gt=0, le=64)
    average_bits: Decimal | None = Field(default=None, gt=0, le=64)
    quantized_components: list[str] | None = None
    quantization_scheme: str | None = None
    calibration_method: str | None = None
    calibration_samples: int | None = Field(default=None, ge=0)
    seed_count: int | None = Field(default=None, ge=1)
    reported_variance: str | None = None
    inference_settings: dict | None = None
    hardware: str | None = None
    baseline_name: str | None = None
    additional_conditions: dict = Field(default_factory=dict)
    provenance: Provenance = Field(default_factory=Provenance)
    extraction_status: Literal["extracted", "needs_review", "manual"] = "needs_review"
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    verification_status: Literal["supported", "contradicted", "insufficient"] = "insufficient"
    review_status: Literal["unreviewed", "reviewed", "corrected"] = "unreviewed"
    warnings: list[str] = Field(default_factory=list)
    normalization: dict = Field(default_factory=dict)
    field_verification: dict[str, Literal["supported", "reviewed"]] = Field(default_factory=dict)

    @field_validator("metric_value", "average_bits", "bit_width")
    @classmethod
    def finite_number(cls, value):
        if value is not None and not value.is_finite():
            raise ValueError("Numbers must be finite")
        return value


class ExtractionBatch(StrictModel):
    experiments: list[ExperimentRecord] = Field(default_factory=list, max_length=150)


class ExperimentFilters(StrictModel):
    library_id: str
    paper_id: str | None = None
    model_name: str | None = None
    model_architecture: str | None = None
    dataset_name: str | None = None
    metric_name: str | None = None
    method_name: str | None = None
    average_bits: Decimal | None = None
    bit_width: Decimal | None = None
    quantized_components: list[str] | None = None


class SearchInput(StrictModel):
    library_id: str
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["dense", "bm25", "hybrid", "rerank"] = "hybrid"
    top_k: int = Field(default=8, ge=1, le=30)
    paper_id: str | None = None
    level: Literal["paper", "evidence", "experiment"] = "evidence"


class ComparisonInput(StrictModel):
    experiment_ids: list[str] = Field(min_length=2, max_length=20)


class RevisionInput(StrictModel):
    record: ExperimentRecord
    reason: str = Field(min_length=3, max_length=1000)
    version: int = Field(ge=1)
    confirmed_fields: list[str] = Field(default_factory=list, max_length=40)


class AtomicClaim(StrictModel):
    text: str = Field(max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    experiment_id: str | None = None
    method_name: str | None = None
    model_name: str | None = None
    dataset_name: str | None = None
    metric_name: str | None = None
    metric_value: Decimal | None = None
    metric_unit: str | None = None
    average_bits: Decimal | None = None
    semantic: bool = False


class AnswerDraft(StrictModel):
    claims: list[AtomicClaim] = Field(default_factory=list, max_length=25)


class Plan(StrictModel):
    task_type: Literal[
        "basic_qa", "paper_lookup", "section_retrieval", "experiment_lookup", "comparison", "research"
    ]
    queries: list[str] = Field(min_length=1, max_length=4)
    filters: dict[str, str | float | None] = Field(default_factory=dict)


class ChatInput(SearchInput):
    conversation_id: str | None = None
    report: bool = False


class EvaluationQuestion(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    relevant_ids: list[str] = Field(min_length=1, max_length=100)


class PublicImport(StrictModel):
    library_id: str
    openalex_id: str = Field(pattern=r"^(https://openalex\.org/)?W\d{1,20}$", max_length=100)


class ExtractionRequest(StrictModel):
    offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=5, ge=1, le=20)


class EvaluationInput(StrictModel):
    library_id: str
    questions: list[EvaluationQuestion] = Field(min_length=1, max_length=100)
    modes: list[Literal["dense", "bm25", "hybrid", "rerank"]] = Field(
        default=["bm25", "hybrid"], min_length=1, max_length=4
    )
