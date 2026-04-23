from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any


class LLMClient:
    def __init__(self) -> None:
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.openai_api_key or self.anthropic_api_key)

    def read_file_base64(self, path: Path) -> tuple[str, str]:
        raw = path.read_bytes()
        encoded = base64.b64encode(raw).decode("utf-8")
        suffix = path.suffix.lower()
        mime = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "application/octet-stream")
        return encoded, mime

    def extract_document(self, path: Path) -> dict[str, Any]:
        if self.openai_api_key:
            return self._extract_openai(path)
        if self.anthropic_api_key:
            return self._extract_anthropic(path)
        raise RuntimeError("No LLM API key configured.")

    def validate_rules(self, extraction_json: dict[str, Any], rules_json: dict[str, Any]) -> dict[str, Any]:
        if self.openai_api_key:
            return self._json_completion_openai(
                model=os.getenv("OPENAI_MODEL_VALIDATOR", "gpt-4.1-mini"),
                prompt=(
                    "You are a trade document validator. Compare the extracted field JSON "
                    "against the customer rule set. Return only valid JSON with "
                    "customer_id, overall_status, field_results, and summary. "
                    "Statuses must be match, mismatch, or uncertain. "
                    "Any confidence below 0.7 or missing value must be uncertain."
                ),
                payload={"extraction": extraction_json, "ruleset": rules_json},
            )
        if self.anthropic_api_key:
            return self._json_completion_anthropic(
                model=os.getenv("ANTHROPIC_MODEL_VALIDATOR", "claude-3-5-sonnet-latest"),
                prompt=(
                    "Compare the extracted trade document fields against the customer rule set. "
                    "Return JSON with customer_id, overall_status, field_results, and summary. "
                    "Statuses: match, mismatch, uncertain. Missing or low confidence fields are uncertain."
                ),
                payload={"extraction": extraction_json, "ruleset": rules_json},
            )
        raise RuntimeError("No LLM API key configured.")

    def route_decision(self, validation_json: dict[str, Any], invoice_number: str | None) -> dict[str, Any]:
        if self.openai_api_key:
            return self._json_completion_openai(
                model=os.getenv("OPENAI_MODEL_ROUTER", "gpt-4.1-mini"),
                prompt=(
                    "You are a routing agent for trade document validation. "
                    "Choose one decision: auto_approve, flag_for_human_review, draft_amendment_request. "
                    "Always return JSON with decision, reasoning, action_items, and amendment_request if needed."
                ),
                payload={"validation": validation_json, "invoice_number": invoice_number},
            )
        if self.anthropic_api_key:
            return self._json_completion_anthropic(
                model=os.getenv("ANTHROPIC_MODEL_ROUTER", "claude-3-5-haiku-latest"),
                prompt=(
                    "Choose one decision for the validated trade document. "
                    "Return JSON with decision, reasoning, action_items, and optional amendment_request."
                ),
                payload={"validation": validation_json, "invoice_number": invoice_number},
            )
        raise RuntimeError("No LLM API key configured.")

    def text_to_sql(self, question: str, schema: str) -> str:
        if self.openai_api_key:
            result = self._json_completion_openai(
                model=os.getenv("OPENAI_MODEL_ROUTER", "gpt-4.1-mini"),
                prompt=(
                    "You convert natural language to safe SQLite SQL. "
                    "Return JSON with one key sql. Only generate a SELECT query on pipeline_runs."
                ),
                payload={"question": question, "schema": schema},
            )
            return result["sql"]
        if self.anthropic_api_key:
            result = self._json_completion_anthropic(
                model=os.getenv("ANTHROPIC_MODEL_ROUTER", "claude-3-5-haiku-latest"),
                prompt=(
                    "Convert the user's question into a safe SQLite SELECT query against pipeline_runs. "
                    "Return JSON with a single key sql."
                ),
                payload={"question": question, "schema": schema},
            )
            return result["sql"]
        raise RuntimeError("No LLM API key configured.")

    def _extract_openai(self, path: Path) -> dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_api_key)
        file_b64, mime = self.read_file_base64(path)
        prompt = """
You are a trade document extraction expert. Extract the following fields from the trade document.

For each field, provide:
- "value": the extracted value as a string (null if not found)
- "confidence": a float between 0.0 and 1.0 indicating your confidence

Fields to extract: consignee_name, hs_code, port_of_loading, port_of_discharge,
incoterms, description_of_goods, gross_weight, invoice_number

IMPORTANT: If a field is not clearly visible or readable, return null with a confidence of 0.0.
Do NOT guess or hallucinate values. Return ONLY valid JSON.
"""
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL_EXTRACTOR", "gpt-4o"),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_file",
                            "filename": path.name,
                            "file_data": f"data:{mime};base64,{file_b64}",
                        },
                    ],
                }
            ],
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text)

    def _extract_anthropic(self, path: Path) -> dict[str, Any]:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.anthropic_api_key)
        file_b64, mime = self.read_file_base64(path)
        response = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL_EXTRACTOR", "claude-3-7-sonnet-latest"),
            max_tokens=1400,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document" if mime == "application/pdf" else "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": file_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract consignee_name, hs_code, port_of_loading, "
                                "port_of_discharge, incoterms, description_of_goods, "
                                "gross_weight, invoice_number. Return JSON only. "
                                "Missing or unreadable fields must be null with confidence 0.0."
                            ),
                        },
                    ],
                }
            ],
        )
        return json.loads(response.content[0].text)

    def _json_completion_openai(self, model: str, prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_api_key)
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_text", "text": json.dumps(payload)},
                    ],
                }
            ],
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text)

    def _json_completion_anthropic(self, model: str, prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.anthropic_api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1600,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\nReturn JSON only.\n\nPayload:\n"
                        f"{json.dumps(payload)}"
                    ),
                }
            ],
        )
        return json.loads(response.content[0].text)
