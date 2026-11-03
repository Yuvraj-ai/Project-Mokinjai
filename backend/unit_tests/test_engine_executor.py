import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.engine.executor import WorkflowExecutor
from app.engine.context import ExecutionContext
from app.models.execution import Execution
from app.models.workflow import Workflow


class TestWorkflowExecutor:
    @pytest.mark.asyncio
    async def test_execute_missing_execution_raises(self, db_session):
        executor = WorkflowExecutor(db_session)
        with pytest.raises(ValueError, match="not found"):
            await executor.execute("nonexistent-id")

    @pytest.mark.asyncio
    async def test_execute_workflow_not_found(self, db_session, test_workspace, test_user):
        execution = Execution(
            workflow_id=None,
            workspace_id=test_workspace.id,
            status="pending",
            trigger_type="manual",
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)

        executor = WorkflowExecutor(db_session)
        result = await executor.execute(execution.id)
        assert result.status == "failed"
        assert "Workflow not found" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_simple_input_output(self, db_session, test_workspace, test_user):
        workflow = Workflow(
            workspace_id=test_workspace.id,
            name="Simple WF",
            flow_definition={
                "nodes": [
                    {"id": "n1", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                    {"id": "n2", "type": "output", "position": {"x": 200, "y": 0}, "data": {"format": "text"}},
                ],
                "edges": [
                    {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": None, "targetHandle": None},
                ],
            },
            status="draft",
            version=1,
            created_by=test_user.id,
        )
        db_session.add(workflow)
        await db_session.commit()
        await db_session.refresh(workflow)

        execution = Execution(
            workflow_id=workflow.id,
            workspace_id=test_workspace.id,
            status="pending",
            trigger_type="manual",
            input_data={"message": "hello"},
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)

        executor = WorkflowExecutor(db_session)
        result = await executor.execute(execution.id)

        assert result.status == "completed"
        assert result.execution_trace is not None
        assert len(result.execution_trace["nodes"]) == 2
        assert result.execution_time_ms is not None

    @pytest.mark.asyncio
    async def test_execute_conditional_branching(self, db_session, test_workspace, test_user):
        workflow = Workflow(
            workspace_id=test_workspace.id,
            name="Conditional WF",
            flow_definition={
                "nodes": [
                    {"id": "n1", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                    {"id": "n2", "type": "conditional", "position": {"x": 200, "y": 0}, "data": {"conditionType": "contains", "conditionValue": "yes"}},
                    {"id": "n3", "type": "output", "position": {"x": 400, "y": 0}, "data": {"format": "text"}},
                    {"id": "n4", "type": "output", "position": {"x": 400, "y": 200}, "data": {"format": "text"}},
                ],
                "edges": [
                    {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": None, "targetHandle": None},
                    {"id": "e2", "source": "n2", "target": "n3", "sourceHandle": "true", "targetHandle": None},
                    {"id": "e3", "source": "n2", "target": "n4", "sourceHandle": "false", "targetHandle": None},
                ],
            },
            status="draft",
            version=1,
            created_by=test_user.id,
        )
        db_session.add(workflow)
        await db_session.commit()
        await db_session.refresh(workflow)

        execution = Execution(
            workflow_id=workflow.id,
            workspace_id=test_workspace.id,
            status="pending",
            trigger_type="manual",
            input_data={"message": "yes please"},
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)

        executor = WorkflowExecutor(db_session)
        result = await executor.execute(execution.id)

        assert result.status == "completed"
        trace = result.execution_trace["nodes"]
        n4_trace = [t for t in trace if t["node_id"] == "n4"]
        assert n4_trace[0]["status"] == "skipped"


class TestCancellation:
    """The cancel endpoint writes status="cancelled", so the runner must respect it
    instead of overwriting it with "completed" (or running past it)."""

    async def _make_workflow_and_execution(self, db_session, test_workspace, test_user, nodes, edges):
        workflow = Workflow(
            workspace_id=test_workspace.id,
            name="Cancellable WF",
            flow_definition={"nodes": nodes, "edges": edges},
            status="draft",
            version=1,
            created_by=test_user.id,
        )
        db_session.add(workflow)
        await db_session.commit()
        await db_session.refresh(workflow)

        execution = Execution(
            workflow_id=workflow.id,
            workspace_id=test_workspace.id,
            status="pending",
            trigger_type="manual",
            input_data={"message": "hello"},
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)
        return workflow, execution

    @staticmethod
    def _linear_flow(middle_type):
        return (
            [
                {"id": "n1", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "n2", "type": middle_type, "position": {"x": 200, "y": 0}, "data": {}},
                {"id": "n3", "type": "output", "position": {"x": 400, "y": 0}, "data": {"format": "text"}},
            ],
            [
                {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": None, "targetHandle": None},
                {"id": "e2", "source": "n2", "target": "n3", "sourceHandle": None, "targetHandle": None},
            ],
        )

    @pytest.mark.asyncio
    async def test_a_cancelled_execution_is_never_started(self, db_session, test_workspace, test_user):
        _, execution = await self._make_workflow_and_execution(
            db_session, test_workspace, test_user, *self._linear_flow("output")
        )
        execution.status = "cancelled"
        await db_session.commit()

        executor = WorkflowExecutor(db_session)
        result = await executor.execute(execution.id)

        assert result.status == "cancelled", "a cancelled run must not be overwritten"
        assert result.started_at is None, "the run must never be marked started"
        assert result.completed_at is None
        assert result.execution_trace is None

    @pytest.mark.asyncio
    async def test_a_cancelled_mid_run_execution_stops_and_stays_cancelled(
        self, db_session, test_workspace, test_user, monkeypatch
    ):
        from sqlalchemy import text

        from app.engine.modules.base import BaseModule
        from app.engine.modules.registry import ModuleRegistry

        class CancellingModule(BaseModule):
            """Simulates the cancel endpoint committing status='cancelled' while
            node n2 is in flight."""

            module_type = "cancel_test"
            db = None
            execution_id = None

            async def execute(self, config, inputs, context):
                await self.db.execute(
                    text("UPDATE executions SET status = 'cancelled' WHERE id = :id"),
                    {"id": self.execution_id},
                )
                return {"output": "node done"}

        monkeypatch.setitem(ModuleRegistry._modules, "cancel_test", CancellingModule)

        _, execution = await self._make_workflow_and_execution(
            db_session, test_workspace, test_user, *self._linear_flow("cancel_test")
        )
        CancellingModule.db = db_session
        CancellingModule.execution_id = execution.id

        executor = WorkflowExecutor(db_session)
        result = await executor.execute(execution.id)

        assert result.status == "cancelled", "the runner must not overwrite a mid-run cancel"
        assert result.completed_at is not None
        node_ids = [entry["node_id"] for entry in result.execution_trace["nodes"]]
        assert node_ids == ["n1", "n2"], "no node after the cancellation may run"
