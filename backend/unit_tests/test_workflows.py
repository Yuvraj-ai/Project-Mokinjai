import pytest


class TestCreateWorkflow:
    @pytest.mark.asyncio
    async def test_create_workflow(self, client, auth_headers, test_workspace):
        response = await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows",
            json={"name": "New Workflow", "flow_definition": {"nodes": [], "edges": []}},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Workflow"
        assert data["version"] == 1
        assert data["status"] == "draft"

    @pytest.mark.asyncio
    async def test_create_workflow_no_auth(self, client, test_workspace):
        response = await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows",
            json={"name": "No Auth"},
        )
        assert response.status_code in (401, 403)


class TestListWorkflows:
    @pytest.mark.asyncio
    async def test_list_workflows(self, client, auth_headers, test_workspace, test_workflow):
        response = await client.get(
            f"/api/workspaces/{test_workspace.id}/workflows",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1


class TestGetWorkflow:
    @pytest.mark.asyncio
    async def test_get_workflow(self, client, auth_headers, test_workspace, test_workflow):
        response = await client.get(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Test Workflow"

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, client, auth_headers, test_workspace):
        response = await client.get(
            f"/api/workspaces/{test_workspace.id}/workflows/nonexistent",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestUpdateWorkflow:
    @pytest.mark.asyncio
    async def test_update_workflow(self, client, auth_headers, test_workspace, test_workflow):
        response = await client.put(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}",
            json={"name": "Updated WF"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated WF"

    @pytest.mark.asyncio
    async def test_update_flow_definition_increments_version(self, client, auth_headers, test_workspace, test_workflow):
        response = await client.put(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}",
            json={"flow_definition": {"nodes": [{"id": "n1", "type": "input", "position": {"x": 0, "y": 0}, "data": {}}], "edges": []}},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["version"] == 2


class TestPublishWorkflow:
    @pytest.mark.asyncio
    async def test_publish_workflow(self, client, auth_headers, test_workspace, test_workflow):
        response = await client.post(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}/publish",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "published"
        assert response.json()["published_at"] is not None


class TestDeleteWorkflow:
    @pytest.mark.asyncio
    async def test_delete_workflow(self, client, auth_headers, test_workspace, test_workflow):
        response = await client.delete(
            f"/api/workspaces/{test_workspace.id}/workflows/{test_workflow.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_workflow_not_found(self, client, auth_headers, test_workspace):
        response = await client.delete(
            f"/api/workspaces/{test_workspace.id}/workflows/nonexistent",
            headers=auth_headers,
        )
        assert response.status_code == 404
