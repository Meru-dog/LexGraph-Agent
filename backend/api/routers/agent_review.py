"""Contract Review Agent endpoints: POST /agent/review, GET /{task_id}, POST approve."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel

from api.auth.dependencies import get_current_user, require_attorney, User
from api.audit.logger import log_review_start, log_export

router = APIRouter(prefix="/agent/review", tags=["review-agent"])

_tasks: dict[str, dict] = {}


class ReviewRequest(BaseModel):
    document_id: str
    jurisdiction: str = "US"
    contract_type: str = "other"
    client_position: str = "buyer"


class ApproveRequest(BaseModel):
    redlines: dict[str, str] = {}
    approved: list[str] = []


def _run_review_agent(task_id: str, raw_contract: str, request: ReviewRequest) -> None:
    _tasks[task_id]["status"] = "running"
    try:
        from agents.review_agent import review_graph

        config = {"configurable": {"thread_id": task_id}}
        initial_state = {
            "raw_contract": raw_contract,
            "jurisdiction": request.jurisdiction,
            "contract_type": request.contract_type,
            "client_position": request.client_position,
            "clauses": [],
            "clause_reviews": [],
            "inconsistencies": [],
            "compliance_flags": [],
            "attorney_redlines": {},
            "approved_clauses": [],
            "redlined_contract": "",
            "review_report": {},
            "messages": [],
        }

        for step_output in review_graph.stream(initial_state, config=config):
            node_name = list(step_output.keys())[0]
            _tasks[task_id]["current_node"] = node_name
            if node_name == "human_checkpoint":
                _tasks[task_id]["status"] = "awaiting_review"
                return

        state = review_graph.get_state(config)
        _tasks[task_id]["status"] = "complete"
        _tasks[task_id]["original_text"] = raw_contract
        _tasks[task_id]["reviewed_text"] = state.values.get("redlined_contract", "")
        _tasks[task_id]["clause_reviews"] = state.values.get("clause_reviews", [])
        _tasks[task_id]["compliance_flags"] = state.values.get("compliance_flags", [])

    except Exception as e:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["error"] = str(e)


@router.get("")
async def list_review_tasks(_user: User = Depends(get_current_user)):
    """List all contract review tasks (newest first)."""
    return sorted(_tasks.values(), key=lambda t: t.get("created_at", ""), reverse=True)


@router.post("")
async def start_review(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    task_id = str(uuid.uuid4())
    # Fetch raw contract text from in-memory document store (populated by /upload)
    from api.routers.upload import get_document_bytes
    doc_bytes = get_document_bytes(request.document_id)
    if doc_bytes:
        from ingestion.pipeline import _extract_text
        raw_contract = _extract_text(doc_bytes, request.document_id)
    else:
        raw_contract = f"[Contract document {request.document_id} — not found in store]"
    _tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "original_text": raw_contract,
        "reviewed_text": "",
        "diff": [],
        "clause_reviews": [],
        "compliance_flags": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    log_review_start(current_user.username, task_id, request.document_id)
    background_tasks.add_task(_run_review_agent, task_id, raw_contract, request)
    return {"task_id": task_id, "status": "running", "estimated_seconds": 60}


@router.get("/{task_id}")
async def get_review_status(task_id: str, _user: User = Depends(get_current_user)):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/approve")
async def approve_clauses(
    task_id: str,
    payload: ApproveRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_attorney),
):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "awaiting_review":
        raise HTTPException(status_code=409, detail="Task is not awaiting review")

    task["status"] = "running"

    from agents.review_agent import review_graph
    config = {"configurable": {"thread_id": task_id}}
    review_graph.update_state(
        config,
        {"attorney_redlines": payload.redlines, "approved_clauses": payload.approved},
        as_node="human_checkpoint",
    )
    background_tasks.add_task(_resume_review_agent, task_id)
    return {"task_id": task_id, "status": "running"}


def _resume_review_agent(task_id: str) -> None:
    from agents.review_agent import review_graph
    config = {"configurable": {"thread_id": task_id}}
    try:
        for _ in review_graph.stream(None, config=config):
            pass
        state = review_graph.get_state(config)
        _tasks[task_id]["status"] = "complete"
        _tasks[task_id]["reviewed_text"] = state.values.get("redlined_contract", "")
    except Exception as e:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["error"] = str(e)


@router.get("/{task_id}/export")
async def export_review_docx(task_id: str, current_user: User = Depends(get_current_user)):
    """Download the redlined contract as a DOCX file."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] not in ("complete", "awaiting_review"):
        raise HTTPException(status_code=409, detail="Review not ready")
    try:
        log_export(current_user.username, task_id, "docx")
        from api.export.docx_export import build_redlined_docx
        docx_bytes = build_redlined_docx(task)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="redlined_{task_id[:8]}.docx"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
