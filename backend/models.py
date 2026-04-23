from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


FIELD_NAMES = [
    "consignee_name",
    "hs_code",
    "port_of_loading",
    "port_of_discharge",
    "incoterms",
    "description_of_goods",
    "gross_weight",
    "invoice_number",
]


class FieldExtraction(BaseModel):
    value: str | None
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    consignee_name: FieldExtraction
    hs_code: FieldExtraction
    port_of_loading: FieldExtraction
    port_of_discharge: FieldExtraction
    incoterms: FieldExtraction
    description_of_goods: FieldExtraction
    gross_weight: FieldExtraction
    invoice_number: FieldExtraction
    source: Literal["llm", "heuristic"]
    warnings: list[str] = Field(default_factory=list)
    raw_text_preview: str | None = None


class ValidationFieldResult(BaseModel):
    status: Literal["match", "mismatch", "uncertain"]
    found: str | None
    expected: str | None = None
    expected_prefix: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    note: str | None = None
    action_required: str | None = None
    required: bool = False


class ValidationResult(BaseModel):
    customer_id: str
    overall_status: Literal["match", "mismatch", "uncertain"]
    field_results: dict[str, ValidationFieldResult]
    summary: str


class AmendmentDiscrepancy(BaseModel):
    field: str
    found: str | None
    expected: str | None
    action_required: str


class AmendmentRequest(BaseModel):
    to: str = "supplier"
    subject: str
    discrepancies: list[AmendmentDiscrepancy]


class RouterDecision(BaseModel):
    decision: Literal[
        "auto_approve",
        "flag_for_human_review",
        "draft_amendment_request",
    ]
    reasoning: str
    action_items: list[str] = Field(default_factory=list)
    amendment_request: AmendmentRequest | None = None


class PipelineRunResponse(BaseModel):
    document_id: str
    filename: str
    pipeline_status: str
    current_stage: str
    extraction_result: dict[str, Any] | None = None
    validation_result: dict[str, Any] | None = None
    router_decision: str | None = None
    router_reasoning: str | None = None
    router_payload: dict[str, Any] | None = None
    error_message: str | None = None
    uploaded_at: datetime | None = None
    completed_at: datetime | None = None


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    sql: str
    answer: str
    rows: list[dict[str, Any]]
