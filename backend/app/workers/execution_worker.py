import asyncio
from app.workers.celery_app import celery_app
from app.database import async_session
from app.engine.executor import WorkflowExecutor


@celery_app.task(name="run_workflow", bind=True, max_retries=3)
def run_workflow_task(self, execution_id: str):
    """Celery task to execute a workflow asynchronously."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute(execution_id))
    finally:
        loop.close()


async def _execute(execution_id: str):
    async with async_session() as db:
        executor = WorkflowExecutor(db)
        await executor.execute(execution_id)
