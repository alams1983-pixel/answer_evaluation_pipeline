import asyncio
import time
from db.database import extraction_tasks_collection, question_papers_collection
from core.config import settings


_extraction_running = False


async def run_poller():
    """
    Background poller that monitors extraction tasks.
    Since extraction is handled via asyncio.create_task in the service,
    this poller mainly handles stale/failed tasks and cleanup.
    """
    global _extraction_running
    _extraction_running = True
    print("[OK] Extraction task monitor started")

    while _extraction_running:
        try:
            stale_tasks = await extraction_tasks_collection.find({
                "status": {"$in": ["rasterizing", "analyzing", "consolidating"]},
                "started_at": {"$lt": time.time() - settings.EXTRACTOR_TASK_TIMEOUT_SEC},
            }).to_list(length=None)

            for task in stale_tasks:
                task_id = str(task["_id"])
                timeout_min = settings.EXTRACTOR_TASK_TIMEOUT_SEC // 60
                print(f"[Extraction Monitor] Task {task_id} appears stale (running > {timeout_min} min), marking as failed")
                await extraction_tasks_collection.update_one(
                    {"_id": task["_id"]},
                    {"$set": {
                        "status": "failed",
                        "error": f"Task timed out after {timeout_min} minutes",
                        "completed_at": time.time(),
                    }},
                )

        except Exception as e:
            print(f"[Extraction Monitor] Error: {e}")

        await asyncio.sleep(60)

    print("[OK] Extraction task monitor stopped")


async def stop_poller():
    global _extraction_running
    _extraction_running = False
