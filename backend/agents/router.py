from __future__ import annotations

from backend.llm import LLMClient
from backend.models import AmendmentDiscrepancy, AmendmentRequest, RouterDecision, ValidationResult


def route_validation(
    validation: ValidationResult,
    invoice_number: str | None,
    llm_client: LLMClient,
) -> RouterDecision:
    if llm_client.enabled:
        try:
            payload = llm_client.route_decision(
                validation.model_dump(),
                invoice_number,
            )
            return RouterDecision.model_validate(payload)
        except Exception:
            pass
    return heuristic_route(validation, invoice_number)


def heuristic_route(validation: ValidationResult, invoice_number: str | None) -> RouterDecision:
    required_fields = [item for item in validation.field_results.values() if item.required]
    required_uncertain = [item for item in required_fields if item.status == "uncertain"]
    required_mismatch = [item for item in required_fields if item.status == "mismatch"]
    low_confidence_required = [
        item
        for item in required_fields
        if item.status == "match" and 0.7 <= item.confidence < 0.85
    ]

    if required_mismatch:
        discrepancies = []
        action_items = []
        reasoning_parts = []
        for field_name, item in validation.field_results.items():
            if item.required and item.status == "mismatch":
                expected = item.expected or item.expected_prefix or "rule set expectation"
                discrepancies.append(
                    AmendmentDiscrepancy(
                        field=field_name,
                        found=item.found,
                        expected=expected,
                        action_required=item.action_required or f"Please correct {field_name}",
                    )
                )
                action_items.append(item.action_required or f"Correct {field_name}")
                reasoning_parts.append(
                    f"{field_name.replace('_', ' ')} mismatch (found: {item.found}, expected: {expected})"
                )
            elif item.required and item.status == "uncertain":
                reasoning_parts.append(
                    f"{field_name.replace('_', ' ')} uncertain (confidence: {item.confidence})"
                )
                action_items.append(f"Review {field_name.replace('_', ' ')} against the source document")
        subject_suffix = invoice_number or "Trade Document"
        return RouterDecision(
            decision="draft_amendment_request",
            reasoning="; ".join(reasoning_parts) + ". Amendment draft prepared for supplier.",
            action_items=action_items,
            amendment_request=AmendmentRequest(
                subject=f"Amendment Required - Invoice {subject_suffix}",
                discrepancies=discrepancies,
            ),
        )

    if required_uncertain or low_confidence_required:
        reasoning_parts = []
        action_items = []
        for field_name, item in validation.field_results.items():
            if item.required and item.status == "uncertain":
                reasoning_parts.append(
                    f"{field_name.replace('_', ' ')} is uncertain (confidence: {item.confidence})"
                )
                action_items.append(f"Review {field_name.replace('_', ' ')} against the source document")
            elif item.required and item.status == "match" and 0.7 <= item.confidence < 0.85:
                reasoning_parts.append(
                    f"{field_name.replace('_', ' ')} matched but confidence is only {item.confidence}"
                )
                action_items.append(f"Confirm {field_name.replace('_', ' ')} before approving")
        return RouterDecision(
            decision="flag_for_human_review",
            reasoning="; ".join(reasoning_parts) + ". Auto-approval is not safe.",
            action_items=action_items,
        )

    return RouterDecision(
        decision="auto_approve",
        reasoning="All required fields matched the customer rules with strong confidence and no uncertain values.",
        action_items=["Store the result and continue shipment processing"],
    )
