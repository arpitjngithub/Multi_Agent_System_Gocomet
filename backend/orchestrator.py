from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.agents.extractor import extract_document
from backend.agents.router import route_validation
from backend.agents.validator import validate_extraction
from backend.database import update_run
from backend.llm import LLMClient


class PipelineOrchestrator:
    def __init__(self, rules_path: Path) -> None:
        self.rules = json.loads(rules_path.read_text(encoding="utf-8"))
        self.llm_client = LLMClient()

    def run(self, document_id: str, file_path: Path) -> dict[str, Any]:
        try:
            update_run(document_id, current_stage="extracting", pipeline_status="running")

            extract_start = perf_counter()
            extraction = extract_document(file_path, self.llm_client)
            update_run(
                document_id,
                extraction_result=extraction.model_dump(),
                current_stage="validating",
            )

            validation = validate_extraction(extraction, self.rules, self.llm_client)
            update_run(
                document_id,
                validation_result=validation.model_dump(),
                current_stage="routing",
            )

            invoice_number = extraction.invoice_number.value if extraction.invoice_number else None
            router = route_validation(validation, invoice_number, self.llm_client)
            duration = round(perf_counter() - extract_start, 2)
            router_payload = router.model_dump()
            router_payload["latency_seconds"] = duration

            update_run(
                document_id,
                router_decision=router.decision,
                router_reasoning=router.reasoning,
                router_payload=router_payload,
                pipeline_status="completed",
                current_stage="done",
                completed_at=datetime.utcnow(),
            )
            return router_payload
        except Exception as exc:
            update_run(
                document_id,
                pipeline_status="failed",
                current_stage="done",
                error_message=str(exc),
                completed_at=datetime.utcnow(),
            )
            raise
