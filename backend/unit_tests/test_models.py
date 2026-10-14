import pytest
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.workflow import Workflow, WorkflowVersion
from app.models.execution import Execution
from app.utils.security import hash_password


class TestUserModel:
    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        user = User(
            email="model@test.com",
            hashed_password=hash_password("pass"),
            name="Model Test",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.id is not None
        assert user.email == "model@test.com"
        assert user.is_superuser is False

    @pytest.mark.asyncio
    async def test_user_default_is_superuser_false(self, db_session):
        user = User(
            email="nosuper@test.com",
            hashed_password=hash_password("pass"),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.is_superuser is False


class TestWorkspaceModel:
    @pytest.mark.asyncio
    async def test_create_workspace(self, db_session, test_user):
        workspace = Workspace(name="My Workspace", owner_id=test_user.id)
        db_session.add(workspace)
        await db_session.commit()
        await db_session.refresh(workspace)
        assert workspace.id is not None
        assert workspace.name == "My Workspace"
        assert workspace.owner_id == test_user.id

    @pytest.mark.asyncio
    async def test_workspace_member(self, db_session, test_workspace, test_user):
        from app.models.user import User
        other_user = User(
            email="other@test.com",
            hashed_password=hash_password("pass"),
            name="Other User",
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        member = WorkspaceMember(
            workspace_id=test_workspace.id,
            user_id=other_user.id,
            role="editor",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)
        assert member.workspace_id == test_workspace.id
        assert member.user_id == other_user.id
        assert member.role == "editor"


class TestWorkflowModel:
    @pytest.mark.asyncio
    async def test_create_workflow(self, db_session, test_workspace, test_user):
        workflow = Workflow(
            workspace_id=test_workspace.id,
            name="Test WF",
            flow_definition={"nodes": [], "edges": []},
            status="draft",
            version=1,
            created_by=test_user.id,
        )
        db_session.add(workflow)
        await db_session.commit()
        await db_session.refresh(workflow)
        assert workflow.id is not None
        assert workflow.name == "Test WF"
        assert workflow.version == 1
        assert workflow.status == "draft"

    @pytest.mark.asyncio
    async def test_workflow_version_model(self, db_session, test_workflow, test_user):
        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version=1,
            flow_definition=test_workflow.flow_definition,
            created_by=test_user.id,
        )
        db_session.add(version)
        await db_session.commit()
        await db_session.refresh(version)
        assert version.id is not None
        assert version.version == 1


class TestExecutionModel:
    @pytest.mark.asyncio
    async def test_create_execution(self, db_session, test_workspace, test_workflow):
        execution = Execution(
            workflow_id=test_workflow.id,
            workspace_id=test_workspace.id,
            status="pending",
            trigger_type="manual",
            input_data={"message": "hello"},
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)
        assert execution.id is not None
        assert execution.status == "pending"
        assert execution.input_data == {"message": "hello"}

    @pytest.mark.asyncio
    async def test_execution_with_trace(self, db_session, test_workspace, test_workflow):
        trace = {"nodes": [{"node_id": "n1", "status": "completed"}]}
        execution = Execution(
            workflow_id=test_workflow.id,
            workspace_id=test_workspace.id,
            status="completed",
            execution_trace=trace,
            execution_time_ms=150,
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)
        assert execution.execution_trace == trace
        assert execution.execution_time_ms == 150
