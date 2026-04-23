from __future__ import annotations

import re
from typing import Any

from backend.llm import LLMClient
from backend.models import ExtractionResult, ValidationFieldResult, ValidationResult


def validate_extraction(
    extraction: ExtractionResult,
    ruleset: dict[str, Any],
    llm_client: LLMClient,
) -> ValidationResult:
    if llm_client.enabled:
        try:
            payload = llm_client.validate_rules(
                extraction.model_dump(),
                ruleset,
            )
            return ValidationResult.model_validate(payload)
        except Exception:
            pass
    return heuristic_validate(extraction, ruleset)


def heuristic_validate(extraction: ExtractionResult, ruleset: dict[str, Any]) -> ValidationResult:
    rules = ruleset["rules"]
    field_results: dict[str, ValidationFieldResult] = {}

    for field_name, rule in rules.items():
        extracted_field = getattr(extraction, field_name, None)
        found = extracted_field.value if extracted_field else None
        confidence = extracted_field.confidence if extracted_field else 0.0
        required = bool(rule.get("required", False))

        if found is None or confidence < 0.7:
            field_results[field_name] = ValidationFieldResult(
                status="uncertain",
                found=found,
                expected=rule.get("expected"),
                expected_prefix=rule.get("expected_prefix"),
                confidence=confidence,
                note="Field missing or below confidence threshold.",
                required=required,
            )
            continue

        if "expected" in rule:
            if normalize(found) == normalize(rule["expected"]):
                status = "match"
                note = None
            else:
                status = "mismatch"
                note = f"Expected {rule['expected']} but found {found}."
            field_results[field_name] = ValidationFieldResult(
                status=status,
                found=found,
                expected=rule["expected"],
                confidence=confidence,
                note=note,
                action_required=(
                    None
                    if status == "match"
                    else f"Please update {field_name.replace('_', ' ')} to {rule['expected']}"
                ),
                required=required,
            )
            continue

        if "expected_prefix" in rule:
            if normalize(found).startswith(normalize(rule["expected_prefix"])):
                status = "match"
                note = None
            else:
                status = "mismatch"
                note = f"Expected prefix {rule['expected_prefix']} but found {found}."
            field_results[field_name] = ValidationFieldResult(
                status=status,
                found=found,
                expected_prefix=rule["expected_prefix"],
                confidence=confidence,
                note=note,
                action_required=(
                    None
                    if status == "match"
                    else f"Please update {field_name.replace('_', ' ')} to start with {rule['expected_prefix']}"
                ),
                required=required,
            )
            continue

        if "max_kg" in rule:
            weight_value = parse_weight_kg(found)
            if weight_value is None:
                status = "uncertain"
                note = "Could not parse gross weight."
            elif weight_value <= float(rule["max_kg"]):
                status = "match"
                note = None
            else:
                status = "mismatch"
                note = f"Weight {weight_value} KG exceeds max {rule['max_kg']} KG."
            field_results[field_name] = ValidationFieldResult(
                status=status,
                found=found,
                expected=f"<= {rule['max_kg']} KG",
                confidence=confidence,
                note=note,
                action_required=(
                    None if status == "match" else f"Please reduce or correct gross weight to <= {rule['max_kg']} KG"
                ),
                required=required,
            )

    statuses = {item.status for item in field_results.values()}
    if "mismatch" in statuses:
        overall_status = "mismatch"
    elif "uncertain" in statuses:
        overall_status = "uncertain"
    else:
        overall_status = "match"

    summary = build_summary(field_results)
    return ValidationResult(
        customer_id=ruleset["customer_id"],
        overall_status=overall_status,
        field_results=field_results,
        summary=summary,
    )


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def parse_weight_kg(value: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    if not match:
        return None
    number = float(match.group(1))
    if "ton" in value.lower():
        return number * 1000
    return number


def build_summary(field_results: dict[str, ValidationFieldResult]) -> str:
    match_count = sum(1 for item in field_results.values() if item.status == "match")
    mismatch_count = sum(1 for item in field_results.values() if item.status == "mismatch")
    uncertain_count = sum(1 for item in field_results.values() if item.status == "uncertain")
    return (
        f"{match_count} fields matched, {mismatch_count} mismatched, "
        f"and {uncertain_count} were uncertain."
    )
