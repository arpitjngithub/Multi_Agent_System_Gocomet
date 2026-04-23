from __future__ import annotations

import re
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from backend.llm import LLMClient
from backend.models import ExtractionResult, FIELD_NAMES


FIELD_PATTERNS = {
    "consignee_name": [
        r"consignee(?: name)?[:\-][ \t]*([^\n\r]+)",
        r"buyer[:\-][ \t]*([^\n\r]+)",
    ],
    "hs_code": [
        r"hs(?: code)?[:\-][ \t]*([A-Z0-9\.\-\/]+)",
        r"harmonized(?: system)? code[:\-][ \t]*([A-Z0-9\.\-\/]+)",
    ],
    "port_of_loading": [
        r"port of loading[:\-][ \t]*([^\n\r]+)",
        r"loading port[:\-][ \t]*([^\n\r]+)",
        r"\bpol[:\-][ \t]*([^\n\r]+)",
    ],
    "port_of_discharge": [
        r"port of discharge[:\-][ \t]*([^\n\r]+)",
        r"discharge port[:\-][ \t]*([^\n\r]+)",
        r"final destination[:\-][ \t]*([^\n\r]+)",
        r"\bpod[:\-][ \t]*([^\n\r]+)",
    ],
    "incoterms": [
        r"incoterms?[:\-][ \t]*([A-Z]{3})",
        r"terms of delivery[:\-][ \t]*([A-Z]{3})",
    ],
    "description_of_goods": [
        r"description of goods[:\-][ \t]*([^\n\r]+)",
        r"goods description[:\-][ \t]*([^\n\r]+)",
    ],
    "gross_weight": [
        r"gross weight[:\-][ \t]*([A-Z0-9\.\s]+(?:KG|KGS|TONNES?))",
        r"weight[:\-][ \t]*([A-Z0-9\.\s]+(?:KG|KGS|TONNES?))",
    ],
    "invoice_number": [
        r"invoice (?:no\.?|number)[:\-][ \t]*([A-Z0-9\-\/]+)",
        r"inv(?:oice)?[:\-][ \t]*([A-Z0-9\-\/]+)",
    ],
}


def extract_document(file_path: Path, llm_client: LLMClient) -> ExtractionResult:
    if llm_client.enabled:
        try:
            payload = llm_client.extract_document(file_path)
            payload["source"] = "llm"
            payload.setdefault("warnings", [])
            payload.setdefault("raw_text_preview", None)
            return ExtractionResult.model_validate(payload)
        except Exception as exc:
            result = heuristic_extract(file_path)
            result.warnings.append(f"LLM extraction failed, used heuristic fallback: {exc}")
            return result
    return heuristic_extract(file_path)


def heuristic_extract(file_path: Path) -> ExtractionResult:
    raw_text = _read_document_text(file_path)
    normalized = normalize_text(raw_text)
    payload: dict[str, dict[str, str | float | None] | str | list[str] | None] = {}
    warnings: list[str] = []

    for field in FIELD_NAMES:
        value = None
        confidence = 0.0
        for pattern in FIELD_PATTERNS[field]:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                candidate = clean_value(match.group(1))
                value = candidate if candidate else None
                confidence = score_confidence(candidate, normalized)
                break
        if field == "incoterms" and value:
            value = value.upper()[:3]
        payload[field] = {"value": value, "confidence": confidence}

    if any(
        isinstance(payload[field], dict) and payload[field]["confidence"] < 0.5
        for field in FIELD_NAMES
    ):
        warnings.append("One or more fields scored below 0.5 confidence; manual review recommended.")

    payload["source"] = "heuristic"
    payload["warnings"] = warnings
    payload["raw_text_preview"] = raw_text[:1000] if raw_text else None
    return ExtractionResult.model_validate(payload)


# def _read_document_text(file_path: Path) -> str:
#     sidecar_candidates = [
#         file_path.with_suffix(file_path.suffix + ".ocr.txt"),
#         file_path.with_suffix(file_path.suffix + ".txt"),
#     ]
#     sidecar_candidates.extend(_sample_sidecar_candidates(file_path))

#     if file_path.suffix.lower() == ".pdf":
#         extracted = _read_pdf_with_pypdf(file_path)
#         if extracted:
#             return extracted

#     for sidecar in sidecar_candidates:
#         if sidecar.exists():
#             return sidecar.read_text(encoding="utf-8")

#     try:
#         with Image.open(file_path) as image:
#             return image.info.get("description", "") or image.info.get("comment", "")
#     except Exception:
#         return ""
def _read_document_text(file_path: Path) -> str:
    sidecar_candidates = [
        file_path.with_suffix(file_path.suffix + ".ocr.txt"),
        file_path.with_suffix(file_path.suffix + ".txt"),
    ]
    sidecar_candidates.extend(_sample_sidecar_candidates(file_path))

    # ✅ 1. Try PDF text extraction first
    if file_path.suffix.lower() == ".pdf":
        extracted = _read_pdf_with_pypdf(file_path)
        if extracted:
            return extracted

    # ✅ 2. Try sidecar files (.txt / .ocr.txt)
    for sidecar in sidecar_candidates:
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8")

    # ✅ 3. Fallback to OCR for images
    try:
        with Image.open(file_path) as image:
            image = image.convert("L")  # grayscale improves OCR
            text = pytesseract.image_to_string(image)

            # Optional debug (you can remove later)
            print("OCR TEXT PREVIEW:", text[:200])

            return text.strip()
    except Exception as e:
        print("OCR ERROR:", e)
        return ""

def _read_pdf_with_pypdf(file_path: Path) -> str:
    try:
        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        return ""
def _sample_sidecar_candidates(file_path: Path) -> list[Path]:
    sample_dir = Path(__file__).resolve().parents[2] / "sample_docs"
    original_name = file_path.name
    if "_" in original_name:
        original_name = original_name.split("_", 1)[1]
    return [
        sample_dir / f"{original_name}.ocr.txt",
        sample_dir / f"{original_name}.txt",
    ]


def normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r", "\n"))


def clean_value(value: str) -> str:
    value = value.strip().split("\n")[0]
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" .;")


def score_confidence(value: str | None, normalized_text: str) -> float:
    if not value:
        return 0.0
    score = 0.92
    if len(value) < 4 and not re.fullmatch(r"[A-Z]{3}", value.strip()):
        score -= 0.12
    if "??" in normalized_text or "illegible" in normalized_text.lower():
        score -= 0.22
    if any(token in value.lower() for token in ("maybe", "unclear", "n/a")):
        score -= 0.3
    return max(0.2, min(0.99, round(score, 2)))
