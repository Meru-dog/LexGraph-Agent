"""DD Agent endpoints: POST /agent/dd, GET /agent/dd/{task_id}, POST review."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel

from api.auth.dependencies import get_current_user, require_attorney, User
from api.audit.logger import log_dd_start, log_dd_approve, log_export

router = APIRouter(prefix="/agent/dd", tags=["dd-agent"])

# In-memory task store (replace with Redis/PostgreSQL in Phase 6)
_tasks: dict[str, dict] = {}


class DDRequest(BaseModel):
    prompt: str
    jurisdiction: str = "JP+US"
    document_ids: list[str] = []
    transaction_type: str = "investment"


class ReviewRequest(BaseModel):
    notes: str = ""
    approved: bool = True
    targets: list[str] = []


def _run_dd_agent(task_id: str, request: DDRequest) -> None:
    """Background task — runs DD agent and updates task store."""
    import time

    _tasks[task_id]["status"] = "running"

    try:
        from agents.dd_agent import dd_graph

        config = {"configurable": {"thread_id": task_id}}
        initial_state = {
            "prompt": request.prompt,
            "jurisdiction": request.jurisdiction,
            "transaction_type": request.transaction_type,
            "documents": [{"id": d} for d in request.document_ids],
            "dd_checklist": [],
            "corporate_findings": [],
            "contract_findings": [],
            "regulatory_findings": [],
            "risk_matrix": {"critical": [], "high": [], "medium": [], "low": []},
            "attorney_notes": "",
            "approved": False,
            "reinvestigation_targets": [],
            "dd_report": None,
            "messages": [],
        }

        for step_output in dd_graph.stream(initial_state, config=config):
            node_name = list(step_output.keys())[0]
            _tasks[task_id]["current_step"] = _get_step_number(node_name)
            _tasks[task_id]["step_label"] = node_name.replace("_", " ").title()

        state = dd_graph.get_state(config)
        _tasks[task_id]["report"] = state.values.get("dd_report")
        _tasks[task_id]["status"] = "complete"
        _notify_ws(task_id, "complete")

    except Exception as e:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["error"] = str(e)


def _get_step_number(node_name: str) -> int:
    step_map = {
        "scope_planner": 1,
        "corporate_reviewer": 2,
        "contract_reviewer": 3,
        "regulatory_checker": 4,
        "risk_synthesizer": 5,
        "human_checkpoint": 6,
        "re_investigate": 7,
        "report_generator": 8,
    }
    return step_map.get(node_name, 0)


@router.get("")
async def list_dd_tasks(_user: User = Depends(get_current_user)):
    """List all DD agent tasks (newest first)."""
    return sorted(_tasks.values(), key=lambda t: t.get("created_at", ""), reverse=True)


@router.post("")
async def start_dd_agent(
    request: DDRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "current_step": 0,
        "step_label": "Initializing",
        "partial_findings": [],
        "report": None,
        "created_at": datetime.utcnow().isoformat(),
        "request": request.model_dump(),
    }
    log_dd_start(current_user.username, task_id, request.prompt)
    background_tasks.add_task(_run_dd_agent, task_id, request)
    return {"task_id": task_id, "status": "running", "estimated_seconds": 90}


@router.get("/{task_id}")
async def get_dd_status(task_id: str, _user: User = Depends(get_current_user)):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "status": task["status"],
        "current_step": task["current_step"],
        "step_label": task["step_label"],
        "partial_findings": task["partial_findings"],
        "report": task["report"],
    }


@router.post("/{task_id}/review")
async def submit_review(
    task_id: str,
    review: ReviewRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_attorney),
):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "awaiting_review":
        raise HTTPException(status_code=409, detail="Task is not awaiting review")

    log_dd_approve(current_user.username, task_id, review.approved, review.notes)
    # Resume graph with attorney feedback
    task["status"] = "running"

    from agents.dd_agent import dd_graph
    config = {"configurable": {"thread_id": task_id}}
    dd_graph.update_state(
        config,
        {"attorney_notes": review.notes, "approved": review.approved, "reinvestigation_targets": review.targets},
        as_node="human_checkpoint",
    )
    background_tasks.add_task(_resume_dd_agent, task_id)

    return {"task_id": task_id, "status": "running"}


def _resume_dd_agent(task_id: str) -> None:
    from agents.dd_agent import dd_graph
    config = {"configurable": {"thread_id": task_id}}
    try:
        for step_output in dd_graph.stream(None, config=config):
            node_name = list(step_output.keys())[0]
            _tasks[task_id]["current_step"] = _get_step_number(node_name)
        state = dd_graph.get_state(config)
        _tasks[task_id]["report"] = state.values.get("dd_report")
        _tasks[task_id]["status"] = "complete"
        _notify_ws(task_id, "complete")
    except Exception as e:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["error"] = str(e)


def _notify_ws(task_id: str, status: str) -> None:
    """Fire-and-forget WebSocket broadcast (sync-safe)."""
    try:
        import asyncio
        from api.routers.ws import ws_manager
        coro = ws_manager.broadcast({"type": "status_update", "task_id": task_id, "status": status})
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, loop)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)
    except Exception:
        pass


@router.get("/{task_id}/export")
async def export_dd_report(task_id: str, current_user: User = Depends(get_current_user)):
    """Download the DD report as a formatted PDF."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] not in ("complete", "awaiting_review"):
        raise HTTPException(status_code=409, detail="Report not ready")
    try:
        log_export(current_user.username, task_id, "pdf")
        from api.export.pdf_export import build_dd_pdf
        pdf_bytes = build_dd_pdf(task)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="dd_report_{task_id[:8]}.pdf"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
