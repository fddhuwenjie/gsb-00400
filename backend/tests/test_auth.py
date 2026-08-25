import pytest

class TestAuth:
    async def test_init_admin(self, client):
        resp = await client.post("/api/auth/init")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert data["password"] == "admin123"

    async def test_init_admin_duplicate(self, client):
        await client.post("/api/auth/init")
        resp = await client.post("/api/auth/init")
        assert resp.status_code == 200
        assert "already" in resp.json().get("message", "").lower()

    async def test_login_success(self, client):
        await client.post("/api/auth/init")
        resp = await client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client):
        await client.post("/api/auth/init")
        resp = await client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/auth/login", data={"username": "nobody", "password": "test"})
        assert resp.status_code == 401

    async def test_me_with_token(self, auth_client):
        resp = await auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    async def test_me_without_token(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401
