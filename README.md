# GoComet Nova – Multi-Agent Trade Document Pipeline

## Overview

This project implements a multi-agent system to automate trade document processing. It extracts structured data from PDFs and images, validates them against rules, and decides the next action — reducing manual effort in global trade workflows.

The system consists of three agents:
- Extractor Agent – Extracts structured fields using OCR + heuristics / LLM
- Validator Agent – Validates extracted data against rules
- Router Agent – Decides whether to auto-approve, flag for review, or request amendments

Additional features:
- SQLite database for storing pipeline runs
- Natural language query interface over stored data
- Minimal frontend UI for visualization

---

## Architecture

Document → Extractor → Validator → Router → Database → Query Layer

- OCR (Tesseract) enables extraction from images
- Confidence scores ensure reliability
- Low-confidence fields are never silently approved

---

## Setup Instructions

### 1. Clone the repository
git clone <your-repo-url>  
cd gocomet

### 2. Create virtual environment
python -m venv venv  
venv\Scripts\activate

### 3. Install dependencies
pip install -r requirements.txt

### 4. Install Tesseract OCR (IMPORTANT)

Download from:  
https://github.com/tesseract-ocr/tesseract  

After installation, ensure this path is set in code:

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

### 5. Setup environment variables
copy .env.example .env  

Add API key (optional):

OPENAI_API_KEY=your_key_here  
OR  
ANTHROPIC_API_KEY=your_key_here  

Note: The system works without API keys using heuristic fallback.

---

## Running the Application

uvicorn backend.main:app --reload  

Open in browser:  
http://localhost:8000

---

## How to Use

1. Upload a document (PDF or image)
2. Run the pipeline
3. View:
   - Extracted fields with confidence scores
   - Validation results
   - Final decision and reasoning
4. Use the query box to ask questions

---

## Sample Documents

- sample_docs/clean_invoice.pdf → expected auto-approve
- sample_docs/messy_bol.jpg → expected flagged or amendment

---

## Sample Queries

- show approved shipments  
- how many shipments were flagged  
- most common mismatch field  

---

## Demo Video

(Add your demo video link here)

---

## Project Structure

gocomet/  
├── backend/  
│   ├── agents/  
│   ├── orchestrator.py  
│   ├── query.py  
│   ├── database.py  
│   └── rules/  
├── frontend/  
├── sample_docs/  
├── prd/  
├── technical_writeup/  
└── README.md  

---

## Design Decisions

- Three-agent architecture avoids hallucination coupling
- Confidence scoring ensures reliability
- OCR fallback enables image processing
- SQLite enables traceability and auditability

---

## Failure Handling

- Low-confidence fields are flagged, not auto-approved
- OCR failures handled gracefully
- Query layer prevents unsafe SQL execution

---

## Future Improvements

- Vision-based LLM extraction (GPT-4V / Claude Vision)
- Human-in-the-loop feedback system
- LangGraph-based orchestration
- Advanced rule engine
- Scalable deployment (Docker + cloud)

---

## Notes

- Each pipeline run has a unique document_id
- Full pipeline state is stored for debugging and replay
- System prioritizes trust over blind automation