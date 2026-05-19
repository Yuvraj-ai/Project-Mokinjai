import asyncio
import logging
import uuid as uuid_mod
from app.workers.celery_app import celery_app
from app.database import async_session
from app.engine.executor import WorkflowExecutor

logger = logging.getLogger(__name__)
TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OSError)

@celery_app.task(name="run_workflow", bind=True, max_retries=3, default_retry_delay=10)
def run_workflow_task(self, execution_id: str):
    """Celery task to execute a workflow asynchronously."""
    try:
        uuid_mod.UUID(execution_id)
    except (ValueError, AttributeError):
        logger.error("Invalid execution_id received", extra={"execution_id": execution_id})
        return

    logger.info("Starting workflow execution", extra={"execution_id": execution_id, "attempt": self.request.retries + 1})
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_execute(execution_id))
        logger.info("Workflow execution completed", extra={"execution_id": execution_id})
    except TRANSIENT_ERRORS as exc:
        logger.warning("Workflow execution transient failure", extra={"execution_id": execution_id, "error": str(exc)})
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error("Workflow execution failed", extra={"execution_id": execution_id, "error": str(exc)}, exc_info=True)
    finally:
        loop.close()

async def _execute(execution_id: str):
    async with async_session() as db:
        try:
            executor = WorkflowExecutor(db)
            await executor.execute(execution_id)
        except Exception:
            await db.rollback()
            from sqlalchemy import update
            from app.models.execution import Execution
            from datetime import datetime, timezone
            await db.execute(
                update(Execution)
                .where(Execution.id == execution_id, Execution.status == "running")
                .values(
                    status="failed",
                    error_message="Worker crashed during execution",
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            raise
