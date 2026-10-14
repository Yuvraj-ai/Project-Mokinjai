import pytest


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client, test_user):
        response = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, test_user):
        response = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpass",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        response = await client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "pass",
        })
        assert response.status_code == 401


class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_success(self, client, test_user):
        from app.utils.security import create_refresh_token
        refresh = create_refresh_token({"sub": test_user.id, "email": test_user.email})
        response = await client.post("/api/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client):
        response = await client.post("/api/auth/refresh", json={
            "refresh_token": "invalid.token.here",
        })
        assert response.status_code == 401


class TestGetMe:
    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, client, auth_headers):
        response = await client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client):
        response = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401


class TestAdminOTP:
    @pytest.mark.asyncio
    async def test_correct_otp_returns_tokens(self, client, admin_user):
        from app.services.otp_store import otp_store

        session_token, code = otp_store.generate()
        response = await client.post("/api/auth/admin/otp/validate", json={
            "session_token": session_token,
            "code": code,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]

    @pytest.mark.asyncio
    async def test_correct_otp_with_two_superusers(self, client, admin_user, db_session):
        from app.models.user import User
        from app.services.otp_store import otp_store
        from app.utils.security import hash_password

        db_session.add(User(
            email="admin2@example.com",
            hashed_password=hash_password("adminpass123"),
            name="Second Admin",
            is_superuser=True,
        ))
        await db_session.commit()
        session_token, code = otp_store.generate()
        response = await client.post("/api/auth/admin/otp/validate", json={
            "session_token": session_token,
            "code": code,
        })
        assert response.status_code == 200
        assert response.json()["access_token"]
