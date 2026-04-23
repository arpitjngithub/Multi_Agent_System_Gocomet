from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from backend.database import UPLOADS_DIR, create_run, ensure_directories, get_run, init_db, list_runs
from backend.models import PipelineRunResponse, QueryRequest, QueryResponse
from backend.orchestrator import PipelineOrchestrator
from backend.query import answer_query


BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
SAMPLE_DOCS_DIR = BASE_DIR / "sample_docs"
RULES_PATH = BASE_DIR / "backend" / "rules" / "customer_rules.json"

load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="GoComet Nova Trade Pipeline", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
app.mount("/sample_docs", StaticFiles(directory=SAMPLE_DOCS_DIR), name="sample_docs")
orchestrator = PipelineOrchestrator(RULES_PATH)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/pipeline/run", response_model=PipelineRunResponse)
async def create_pipeline_run(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> PipelineRunResponse:
    ensure_directories()
    init_db()
    document_id = str(uuid.uuid4())
    target_path = UPLOADS_DIR / f"{document_id}_{file.filename}"
    with target_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    for suffix in (".ocr.txt", ".txt"):
        sample_sidecar = SAMPLE_DOCS_DIR / f"{file.filename}{suffix}"
        if sample_sidecar.exists():
            shutil.copyfile(sample_sidecar, target_path.with_suffix(target_path.suffix + suffix))

    create_run(document_id, file.filename)
    background_tasks.add_task(orchestrator.run, document_id, target_path)

    payload = get_run(document_id)
    if not payload:
        raise HTTPException(status_code=500, detail="Failed to create pipeline run.")
    return PipelineRunResponse.model_validate(payload)


@app.get("/api/pipeline/run/{document_id}", response_model=PipelineRunResponse)
def fetch_pipeline_run(document_id: str) -> PipelineRunResponse:
    payload = get_run(document_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Pipeline run not found.")
    return PipelineRunResponse.model_validate(payload)


@app.get("/api/pipeline/runs")
def fetch_runs() -> list[PipelineRunResponse]:
    return [PipelineRunResponse.model_validate(row) for row in list_runs()]


@app.post("/api/query", response_model=QueryResponse)
def run_query(request: QueryRequest) -> QueryResponse:
    sql, rows, answer = answer_query(request.question)
    return QueryResponse(question=request.question, sql=sql, answer=answer, rows=rows)
