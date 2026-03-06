"""Sync API — trigger and monitor tender sync jobs."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from backend.services.uk_sync import run_sync

logger = logging.getLogger(__name__)
router = APIRouter()

# Track sync state
_sync_state = {
    "running": False,
    "last_result": None,
    "last_run": None,
}


@router.get("/status")
async def sync_status():
    """Get current sync status and last run result."""
    return {
        "running": _sync_state["running"],
        "last_run": _sync_state["last_run"],
        "last_result": _sync_state["last_result"],
    }


@router.post("/uk/run")
async def trigger_uk_sync(background_tasks: BackgroundTasks):
    """Trigger Uttarakhand tender sync (runs in background)."""
    if _sync_state["running"]:
        return {"status": "already_running", "started_at": _sync_state["last_run"]}

    _sync_state["running"] = True
    _sync_state["last_run"] = datetime.now().isoformat()

    async def do_sync():
        try:
            result = await run_sync()
            _sync_state["last_result"] = result
        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            _sync_state["last_result"] = {"success": False, "error": str(e)}
        finally:
            _sync_state["running"] = False

    background_tasks.add_task(do_sync)
    return {"status": "started", "message": "Uttarakhand sync started..."}


@router.get("/uk/run-sync")
async def trigger_uk_sync_blocking():
    """Trigger sync and wait for result (blocking, for testing)."""
    if _sync_state["running"]:
        return {"status": "already_running"}

    _sync_state["running"] = True
    _sync_state["last_run"] = datetime.now().isoformat()

    try:
        result = await run_sync()
        _sync_state["last_result"] = result
        return result
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        _sync_state["running"] = False
