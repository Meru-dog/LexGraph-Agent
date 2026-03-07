"""API integration test — runs against the in-process FastAPI app."""
import sys, asyncio
sys.path.insert(0, "backend")

from httpx import AsyncClient, ASGITransport
from main import app

def ok(condition): return "PASS" if condition else "FAIL"

async def run():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("=== API endpoint tests ===")

        # Health
        r = await client.get("/health")
        print(f"  [{ok(r.status_code == 200)}] GET /health → {r.status_code} {r.json()}")

        # Upload — valid txt
        r = await client.post(
            "/upload",
            files={"file": ("contract.txt", "SERVICES\n1. Services shall be provided.".encode(), "text/plain")},
            data={"document_type": "Contract"},
        )
        j = r.json()
        print(f"  [{ok(r.status_code == 200 and 'document_id' in j)}] POST /upload → {r.status_code}, steps={len(j.get('processing_steps', []))}")

        # Upload — bad type
        r = await client.post(
            "/upload",
            files={"file": ("bad.exe", b"data", "application/octet-stream")},
            data={"document_type": "other"},
        )
        print(f"  [{ok(r.status_code == 400)}] POST /upload (bad type) → {r.status_code} (expected 400)")

        # DD agent start
        r = await client.post("/agent/dd", json={
            "prompt": "Invest ¥2B in TechCorp KK",
            "jurisdiction": "JP",
            "document_ids": [],
            "transaction_type": "investment",
        })
        j = r.json()
        task_id = j.get("task_id", "")
        print(f"  [{ok(r.status_code == 200 and task_id)}] POST /agent/dd → {r.status_code}, task_id={task_id[:8]}...")

        # DD agent poll
        await asyncio.sleep(0.1)
        r = await client.get(f"/agent/dd/{task_id}")
        print(f"  [{ok(r.status_code == 200)}] GET /agent/dd/{{id}} → {r.status_code}, status={r.json().get('status')}")

        # DD 404
        r = await client.get("/agent/dd/nonexistent-id")
        print(f"  [{ok(r.status_code == 404)}] GET /agent/dd/nonexistent → {r.status_code} (expected 404)")

        # Contract review start
        r = await client.post("/agent/review", json={
            "document_id": "doc-001",
            "jurisdiction": "US",
            "contract_type": "MSA",
            "client_position": "buyer",
        })
        j = r.json()
        review_id = j.get("task_id", "")
        print(f"  [{ok(r.status_code == 200 and review_id)}] POST /agent/review → {r.status_code}, task_id={review_id[:8]}...")

        # Review poll
        await asyncio.sleep(0.1)
        r = await client.get(f"/agent/review/{review_id}")
        print(f"  [{ok(r.status_code == 200)}] GET /agent/review/{{id}} → {r.status_code}, status={r.json().get('status')}")

        # Graph search (stub)
        r = await client.get("/graph/search", params={"q": "会社法", "jurisdiction": "JP"})
        print(f"  [{ok(r.status_code == 200)}] GET /graph/search → {r.status_code}, nodes={len(r.json().get('nodes', []))}")

        # Graph node (stub)
        r = await client.get("/graph/node/jp-ca-355")
        print(f"  [{ok(r.status_code == 200)}] GET /graph/node/jp-ca-355 → {r.status_code}")

asyncio.run(run())
