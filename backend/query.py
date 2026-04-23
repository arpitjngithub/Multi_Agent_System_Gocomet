from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from backend.database import get_schema_description, run_sql
from backend.llm import LLMClient


def answer_query(question: str) -> tuple[str, list[dict[str, Any]], str]:
    llm_client = LLMClient()
    sql = ""
    rows: list[dict[str, Any]] = []

    if llm_client.enabled:
        try:
            sql = llm_client.text_to_sql(question, get_schema_description())
            guard_sql(sql)
            rows = run_sql(sql)
            return sql, rows, summarize_rows(question, rows)
        except Exception:
            pass

    sql, rows = heuristic_query(question)
    return sql, rows, summarize_rows(question, rows)


# def heuristic_query(question: str) -> tuple[str, list[dict[str, Any]]]:
#     lower = question.lower()
#     if "auto-approved" in lower or "auto approved" in lower:
#         sql = (
#             "SELECT document_id, filename, router_decision, uploaded_at "
#             "FROM pipeline_runs WHERE router_decision = 'auto_approve' ORDER BY uploaded_at DESC"
#         )
#         return sql, run_sql(sql)

#     if "flagged" in lower:
#         sql = (
#             "SELECT COUNT(*) AS flagged_count FROM pipeline_runs "
#             "WHERE router_decision = 'flag_for_human_review' "
#             "AND uploaded_at >= datetime('now', '-7 day')"
#         )
#         return sql, run_sql(sql)

#     if "mismatch field" in lower or "validation failure" in lower:
#         sql = "SELECT document_id, validation_result FROM pipeline_runs WHERE validation_result IS NOT NULL"
#         rows = run_sql(sql)
#         counter: Counter[str] = Counter()
#         for row in rows:
#             validation = json.loads(row["validation_result"]) if isinstance(row["validation_result"], str) else row["validation_result"]
#             for field, result in validation["field_results"].items():
#                 if result["status"] == "mismatch":
#                     counter[field] += 1
#         most_common = counter.most_common()
#         return "HEURISTIC_MISMATCH_COUNT", [
#             {"field": field, "count": count} for field, count in most_common
#         ]

#     sql = "SELECT document_id, filename, router_decision, pipeline_status, uploaded_at FROM pipeline_runs ORDER BY uploaded_at DESC LIMIT 10"
#     return sql, run_sql(sql)

def heuristic_query(question: str) -> tuple[str, list[dict[str, Any]]]:
    lower = question.lower()

    # ✅ Approved shipments (FIXED)
    if "approved" in lower:
        sql = (
            "SELECT document_id, filename, router_decision, uploaded_at "
            "FROM pipeline_runs "
            "WHERE router_decision = 'auto_approve' "
            "ORDER BY uploaded_at DESC"
        )
        return sql, run_sql(sql)

    # ✅ Flagged shipments
    if "flagged" in lower:
        sql = (
            "SELECT document_id, filename, router_decision, uploaded_at "
            "FROM pipeline_runs "
            "WHERE router_decision = 'flag_for_human_review' "
            "ORDER BY uploaded_at DESC"
        )
        return sql, run_sql(sql)

    # ✅ Amendment requests
    if "amendment" in lower:
        sql = (
            "SELECT document_id, filename, router_decision, uploaded_at "
            "FROM pipeline_runs "
            "WHERE router_decision = 'draft_amendment_request' "
            "ORDER BY uploaded_at DESC"
        )
        return sql, run_sql(sql)

    # ✅ Count queries
    if "how many" in lower and "flagged" in lower:
        sql = (
            "SELECT COUNT(*) AS flagged_count FROM pipeline_runs "
            "WHERE router_decision = 'flag_for_human_review' "
            "AND uploaded_at >= datetime('now', '-7 day')"
        )
        return sql, run_sql(sql)

    # ✅ Mismatch logic (unchanged)
    if "mismatch field" in lower or "validation failure" in lower:
        sql = "SELECT document_id, validation_result FROM pipeline_runs WHERE validation_result IS NOT NULL"
        rows = run_sql(sql)
        counter: Counter[str] = Counter()
        for row in rows:
            validation = json.loads(row["validation_result"]) if isinstance(row["validation_result"], str) else row["validation_result"]
            for field, result in validation["field_results"].items():
                if result["status"] == "mismatch":
                    counter[field] += 1
        most_common = counter.most_common()
        return "HEURISTIC_MISMATCH_COUNT", [
            {"field": field, "count": count} for field, count in most_common
        ]

    # ❗ Default fallback
    sql = "SELECT document_id, filename, router_decision, pipeline_status, uploaded_at FROM pipeline_runs ORDER BY uploaded_at DESC LIMIT 10"
    return sql, run_sql(sql)

def summarize_rows(question: str, rows: list[dict[str, Any]]) -> str:
    lower = question.lower()
    if not rows:
        return "No matching pipeline runs were found."
    if "flagged" in lower and "flagged_count" in rows[0]:
        return f"{rows[0]['flagged_count']} shipments were flagged in the last 7 days."
    if "mismatch" in lower or "validation failure" in lower:
        top = rows[0]
        return f"The most common mismatch field is {top['field']} with {top['count']} occurrences."
    if "auto-approved" in lower or "auto approved" in lower:
        return f"Found {len(rows)} auto-approved shipments."
    return f"Returned {len(rows)} matching pipeline runs."


def guard_sql(sql: str) -> None:
    if not re.match(r"^\s*select\b", sql, flags=re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed.")
    blocked = ["insert ", "update ", "delete ", "drop ", "alter ", "pragma "]
    lowered = sql.lower()
    if any(token in lowered for token in blocked):
        raise ValueError("Unsafe SQL generated.")
