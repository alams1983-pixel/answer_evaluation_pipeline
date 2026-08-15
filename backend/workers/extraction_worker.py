import asyncio
import time
from datetime import datetime, timedelta
from sqlalchemy import select, update
from db.database import AsyncSessionLocal
from db.models import ExtractionTask
from core.config import settings

_extraction_running = False


async def run_poller():
    global _extraction_running
    _extraction_running = True
    print("[OK] Extraction task monitor started")

    while _extraction_running:
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=settings.EXTRACTOR_TASK_TIMEOUT_SEC)
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(ExtractionTask).where(
                        ExtractionTask.status.in_(["rasterizing", "analyzing", "consolidating"]),
                        ExtractionTask.started_at < cutoff,
                    )
                )
                stale_tasks = res.scalars().all()

                for task in stale_tasks:
                    timeout_min = settings.EXTRACTOR_TASK_TIMEOUT_SEC // 60
                    print(f"[Extraction Monitor] Task {task.id} appears stale (running > {timeout_min} min), marking as failed")
                    task.status = "failed"
                    task.error = f"Task timed out after {timeout_min} minutes"
                    task.completed_at = datetime.utcnow()

                await db.commit()

        except Exception as e:
            print(f"[Extraction Monitor] Error: {e}")

        await asyncio.sleep(60)

    print("[OK] Extraction task monitor stopped")


async def stop_poller():
    global _extraction_running
    _extraction_running = False
