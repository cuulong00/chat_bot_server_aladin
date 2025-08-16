import os
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

@router.delete("/admin/delete_all_threads", tags=["Admin"])
def delete_all_threads():
    base_url = os.getenv("THREAD_API_BASE_URL", "http://127.0.0.1:2024")
    try:
        resp = requests.post(f"{base_url}/threads/search", json={})
        resp.raise_for_status()
        data = resp.json()
        thread_ids = [t["thread_id"] for t in data if "thread_id" in t]
        deleted = []
        failed = []
        for tid in thread_ids:
            r = requests.delete(f"{base_url}/threads/{tid}")
            if r.status_code == 204:
                deleted.append(tid)
            else:
                failed.append({"thread_id": tid, "status": r.status_code, "msg": r.text})
        return JSONResponse({"deleted": deleted, "failed": failed, "total": len(thread_ids)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
