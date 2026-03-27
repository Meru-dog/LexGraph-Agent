"""POST /evaluate/ragas — run RAGAS evaluation against the current pipeline."""

import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/evaluate", tags=["evaluation"])

# In-memory store for async evaluation jobs
_jobs: dict[str, dict] = {}


class EvalRequest(BaseModel):
    pipeline_version: str = "dev"
    use_local_llm: bool = True      # False only for public test data
    use_wandb: bool = True
    subset: list[str] = []          # filter by jurisdiction: ["JP"] / ["US"] / []


class EvalResponse(BaseModel):
    job_id: str
    status: str
    message: str


@router.post("/ragas", response_model=EvalResponse, status_code=202)
async def run_ragas(request: EvalRequest, background_tasks: BackgroundTasks):
    """Trigger RAGAS evaluation as a background job.

    Returns a job_id immediately. Poll GET /evaluate/ragas/{job_id} for results.
    Evaluation runs locally (Ollama) to maintain confidentiality compliance.
    """
    import uuid
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "result": None, "error": None}
    background_tasks.add_task(_run_eval, job_id, request)
    return EvalResponse(
        job_id=job_id,
        status="running",
        message=f"Evaluation started with {request.pipeline_version}. Poll GET /evaluate/ragas/{job_id}",
    )


@router.get("/ragas/{job_id}")
async def get_eval_result(job_id: str):
    """Poll evaluation job status and results."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id":  job_id,
        "status":  job["status"],
        "result":  job["result"],
        "error":   job["error"],
    }


@router.get("/ragas/history/latest")
async def get_latest_scores():
    """Return the most recent RAGAS scores from Supabase."""
    try:
        import os
        from supabase import create_client
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            return {"error": "Supabase not configured"}
        client = create_client(url, key)
        rows = (
            client.table("ragas_scores")
            .select("*")
            .order("evaluated_at", desc=True)
            .limit(10)
            .execute()
        )
        return {"scores": rows.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Background task ──────────────────────────────────────────────────────────

async def _run_eval(job_id: str, request: EvalRequest) -> None:
    try:
        from evaluation.ragas_evaluator import LexGraphEvaluator
        from evaluation.test_cases import TEST_CASES

        # Optional jurisdiction filter
        cases = TEST_CASES
        if request.subset:
            cases = [c for c in TEST_CASES if c.get("jurisdiction") in request.subset]
        if not cases:
            _jobs[job_id] = {
                "status": "error",
                "result": None,
                "error": "No test cases match the requested subset",
            }
            return

        evaluator = LexGraphEvaluator(
            use_local_llm=request.use_local_llm,
            pipeline_version=request.pipeline_version,
            use_wandb=request.use_wandb,
        )

        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, evaluator.run, cases)

        _jobs[job_id] = {"status": "complete", "result": scores, "error": None}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "result": None, "error": str(e)}
        print(f"[evaluate] job {job_id} failed: {e}")
