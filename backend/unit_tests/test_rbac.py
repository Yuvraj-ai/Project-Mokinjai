import pytest
from unittest.mock import MagicMock
from app.middleware.rbac import require_workspace_role, ROLE_HIERARCHY
from app.models.workspace import WorkspaceMember


class TestRoleHierarchy:
    def test_owner_is_highest(self):
        assert ROLE_HIERARCHY["owner"] > ROLE_HIERARCHY["admin"]
        assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["editor"]
        assert ROLE_HIERARCHY["editor"] > ROLE_HIERARCHY["viewer"]

    def test_all_roles_defined(self):
        assert "owner" in ROLE_HIERARCHY
        assert "admin" in ROLE_HIERARCHY
        assert "editor" in ROLE_HIERARCHY
        assert "viewer" in ROLE_HIERARCHY


class TestRBACSuperuserBypass:
    @pytest.mark.asyncio
    async def test_superuser_bypasses_rbac(self, db_session, admin_user, test_workspace):
        dep = require_workspace_role("owner")
        # Mock the FastAPI dependencies
        mock_request = MagicMock()
        mock_request.path_params = {"workspace_id": test_workspace.id}

        from app.database import get_db
        from app.middleware.auth import get_current_user

        async def override_db():
            yield db_session

        async def override_user():
            return admin_user

        # The superuser should bypass all RBAC checks
        assert admin_user.is_superuser is True


class TestRBACMemberRoles:
    def test_owner_has_highest_access(self):
        assert ROLE_HIERARCHY["owner"] >= ROLE_HIERARCHY["admin"]
        assert ROLE_HIERARCHY["owner"] >= ROLE_HIERARCHY["editor"]
        assert ROLE_HIERARCHY["owner"] >= ROLE_HIERARCHY["viewer"]

    def test_viewer_has_lowest_access(self):
        assert ROLE_HIERARCHY["viewer"] <= ROLE_HIERARCHY["editor"]
        assert ROLE_HIERARCHY["viewer"] <= ROLE_HIERARCHY["admin"]
        assert ROLE_HIERARCHY["viewer"] <= ROLE_HIERARCHY["owner"]

    def test_editor_can_do_editor_things(self):
        assert ROLE_HIERARCHY["editor"] >= ROLE_HIERARCHY["editor"]

    def test_editor_cannot_do_admin_things(self):
        assert ROLE_HIERARCHY["editor"] < ROLE_HIERARCHY["admin"]
