import pytest


class TestExecuteWorkflow:
    @pytest.mark.asyncio
    async def test_execute_workflow_sync(self, client, auth_headers, test_workspace, test_workflow):
        response = await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}/execute",
            json={"input_data": {"message": "hello"}, "async_execution": False},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["execution_trace"] is not None
        assert data["execution_time_ms"] is not None

    @pytest.mark.asyncio
    async def test_execute_workflow_no_auth(self, client, test_workspace, test_workflow):
        response = await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}/execute",
            json={"input_data": {}},
        )
        assert response.status_code in (401, 403)


class TestListExecutions:
    @pytest.mark.asyncio
    async def test_list_executions(self, client, auth_headers, test_workspace, test_workflow):
        await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}/execute",
            json={"input_data": {"msg": "test"}, "async_execution": False},
            headers=auth_headers,
        )
        response = await client.get(
            f"/api/workspaces/{test_workspace.id}/executions",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_executions_by_status(self, client, auth_headers, test_workspace, test_workflow):
        await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}/execute",
            json={"input_data": {}, "async_execution": False},
            headers=auth_headers,
        )
        response = await client.get(
            f"/api/workspaces/{test_workspace.id}/executions?status=completed",
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestGetExecution:
    @pytest.mark.asyncio
    async def test_get_execution(self, client, auth_headers, test_workspace, test_workflow):
        exec_resp = await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}/execute",
            json={"input_data": {}, "async_execution": False},
            headers=auth_headers,
        )
        exec_id = exec_resp.json()["id"]
        response = await client.get(
            f"/api/workspaces/{test_workspace.id}/executions/{exec_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == exec_id

    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, client, auth_headers, test_workspace):
        response = await client.get(
            f"/api/workspaces/{test_workspace.id}/executions/nonexistent",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestCancelExecution:
    @pytest.mark.asyncio
    async def test_cancel_execution(self, client, auth_headers, test_workspace, test_workflow):
        exec_resp = await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}/execute",
            json={"input_data": {}, "async_execution": False},
            headers=auth_headers,
        )
        exec_id = exec_resp.json()["id"]
        response = await client.post(
            f"/api/workspaces/{test_workspace.id}/executions/{exec_id}/cancel",
            headers=auth_headers,
        )
        assert response.status_code in (200, 400)
