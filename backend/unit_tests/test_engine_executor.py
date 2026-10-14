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
            workflow_id="nonexistent-wf",
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
