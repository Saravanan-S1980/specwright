"""FastAPI entry point.

Week 1: upload a ticket CSV, get Evidence back, then synthesize it into a
ranked problem list. Storage is an in-memory dict until Postgres arrives in
week 3.
"""

from fastapi import FastAPI, HTTPException, UploadFile

from app.config import settings
from app.ingest.tickets import TicketParseError, parse_tickets_csv
from app.llm import StructuredOutputError
from app.schemas import Evidence, ProblemList
from app.stages.synthesize import synthesize

app = FastAPI(title="Specwright", version="0.1.0")

# project_id -> evidence list. Lost on restart; fine for week 1.
EVIDENCE: dict[str, list[Evidence]] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/projects/{project_id}/tickets")
async def upload_tickets(project_id: str, file: UploadFile) -> dict:
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, "File too large for the demo (5 MB max)")
    try:
        evidence = parse_tickets_csv(raw.decode("utf-8-sig"))
    except (TicketParseError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc

    EVIDENCE.setdefault(project_id, []).extend(evidence)
    return {
        "project_id": project_id,
        "added": len(evidence),
        "total": len(EVIDENCE[project_id]),
        "preview": [e.model_dump() for e in evidence[:3]],
    }


@app.get("/projects/{project_id}/evidence")
def list_evidence(project_id: str) -> list[Evidence]:
    return EVIDENCE.get(project_id, [])


@app.post("/projects/{project_id}/synthesize")
def synthesize_project(project_id: str) -> ProblemList:
    evidence = EVIDENCE.get(project_id)
    if not evidence:
        raise HTTPException(404, "No evidence for this project. Upload tickets first.")
    try:
        return synthesize(evidence)
    except StructuredOutputError as exc:
        # 502: an upstream service (the model) gave us something unusable.
        raise HTTPException(502, f"The model didn't return a valid problem list: {exc}") from exc
