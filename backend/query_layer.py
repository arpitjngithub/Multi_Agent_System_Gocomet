from __future__ import annotations

import os
import re

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from backend.database import get_schema_description, run_sql_query
from backend.models import QueryResponse


SYSTEM_PROMPT = """
You translate plain-English analytics questions into SQLite SQL.
Return only SQL.
Only query the pipeline_runs table.
Prefer JSON extraction with json_extract when needed.
""".strip()


class QueryLayer:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL_QUERY", "gpt-4.1-mini")
        self.client = OpenAI(api_key=self.api_key) if self.api_key and OpenAI else None

    def answer(self, question: str) -> QueryResponse:
        sql = self._generate_sql(question)
        rows = run_sql_query(sql)
        explanation = self._explain(question, rows)
        return QueryResponse(question=question, sql=sql, explanation=explanation, rows=rows)

    def _generate_sql(self, question: str) -> str:
        if self.client:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Schema: {get_schema_description()}\nQuestion: {question}",
                    },
                ],
            )
            return response.output_text.strip().strip("`")
        return self._fallback_sql(question)

    # def _fallback_sql(self, question: str) -> str:
    #     q = question.lower()
    #     if "flagged" in q and "week" in q:
    #         return (
    #             "SELECT COUNT(*) AS flagged_shipments FROM pipeline_runs "
    #             "WHERE router_decision = 'flag_for_human_review' "
    #             "AND uploaded_at >= datetime('now', '-7 days')"
    #         )
    #     if "auto-approved" in q or "auto approved" in q:
    #         return (
    #             "SELECT document_id, filename, uploaded_at FROM pipeline_runs "
    #             "WHERE router_decision = 'auto_approve' ORDER BY uploaded_at DESC"
    #         )
    #     if "most common mismatch field" in q or "most common validation failure" in q:
    #         return (
    #             "SELECT "
    #             "CASE "
    #             "WHEN json_extract(validation_result, '$.field_results.incoterms.status') = 'mismatch' THEN 'incoterms' "
    #             "WHEN json_extract(validation_result, '$.field_results.port_of_discharge.status') = 'mismatch' THEN 'port_of_discharge' "
    #             "WHEN json_extract(validation_result, '$.field_results.hs_code.status') = 'mismatch' THEN 'hs_code' "
    #             "WHEN json_extract(validation_result, '$.field_results.gross_weight.status') = 'mismatch' THEN 'gross_weight' "
    #             "END AS mismatch_field, COUNT(*) AS total "
    #             "FROM pipeline_runs "
    #             "WHERE validation_result IS NOT NULL "
    #             "GROUP BY mismatch_field "
    #             "HAVING mismatch_field IS NOT NULL "
    #             "ORDER BY total DESC LIMIT 1"
    #         )
    #     if re.search(r"\bhow many\b", q):
    #         return "SELECT COUNT(*) AS total_runs FROM pipeline_runs"
    #     return "SELECT document_id, filename, router_decision, uploaded_at FROM pipeline_runs ORDER BY uploaded_at DESC LIMIT 10"

    def _fallback_sql(self, question: str) -> str:
        q = question.lower()

        # ✅ Approved shipments (FIXED)
        if "approved" in q:
            return (
                "SELECT document_id, filename, router_decision, pipeline_status, uploaded_at "
                "FROM pipeline_runs "
                "WHERE router_decision = 'auto_approve' "
                "ORDER BY uploaded_at DESC LIMIT 10"
            )

        # ✅ Flagged shipments
        if "flagged" in q:
            return (
                "SELECT document_id, filename, router_decision, pipeline_status, uploaded_at "
                "FROM pipeline_runs "
                "WHERE router_decision = 'flag_for_human_review' "
                "ORDER BY uploaded_at DESC LIMIT 10"
            )

        # ✅ Amendment requests
        if "amendment" in q:
            return (
                "SELECT document_id, filename, router_decision, pipeline_status, uploaded_at "
                "FROM pipeline_runs "
                "WHERE router_decision = 'draft_amendment_request' "
                "ORDER BY uploaded_at DESC LIMIT 10"
            )

        # ✅ Weekly flagged count
        if "flagged" in q and "week" in q:
            return (
                "SELECT COUNT(*) AS flagged_shipments FROM pipeline_runs "
                "WHERE router_decision = 'flag_for_human_review' "
                "AND uploaded_at >= datetime('now', '-7 days')"
            )

        # ✅ Mismatch field
        if "most common mismatch field" in q or "most common validation failure" in q:
            return (
                "SELECT "
                "CASE "
                "WHEN json_extract(validation_result, '$.field_results.incoterms.status') = 'mismatch' THEN 'incoterms' "
                "WHEN json_extract(validation_result, '$.field_results.port_of_discharge.status') = 'mismatch' THEN 'port_of_discharge' "
                "WHEN json_extract(validation_result, '$.field_results.hs_code.status') = 'mismatch' THEN 'hs_code' "
                "WHEN json_extract(validation_result, '$.field_results.gross_weight.status') = 'mismatch' THEN 'gross_weight' "
                "END AS mismatch_field, COUNT(*) AS total "
                "FROM pipeline_runs "
                "WHERE validation_result IS NOT NULL "
                "GROUP BY mismatch_field "
                "HAVING mismatch_field IS NOT NULL "
                "ORDER BY total DESC LIMIT 1"
            )

        # ✅ Generic count
        if re.search(r"\bhow many\b", q):
            return "SELECT COUNT(*) AS total_runs FROM pipeline_runs"

    # ❗ Default fallback (unchanged)
        return "SELECT document_id, filename, router_decision, uploaded_at FROM pipeline_runs ORDER BY uploaded_at DESC LIMIT 10"

    def _explain(self, question: str, rows: list[dict]) -> str:
        if not rows:
            return f"No records matched: {question}"
        if len(rows) == 1 and len(rows[0]) == 1:
            value = next(iter(rows[0].values()))
            return f"Answer: {value}"
        return f"Returned {len(rows)} row(s) for: {question}"
