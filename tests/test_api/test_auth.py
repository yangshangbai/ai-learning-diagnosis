"""Tests for authentication endpoints."""
import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    """Should login successfully with correct credentials."""
    resp = await client.post("/api/auth/login", json={
        "phone": "13800001111",
        "password": "demo123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data["data"]
    assert data["data"]["user"]["role"] == "teacher"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """Should reject login with incorrect password."""
    resp = await client.post("/api/auth/login", json={
        "phone": "13800001111",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    """Should reject login for non-existent user."""
    resp = await client.post("/api/auth/login", json={
        "phone": "00000000000",
        "password": "demo123"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client, auth_token):
    """Should return current user info with valid token."""
    resp = await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["phone"] == "13800001111"


@pytest.mark.asyncio
async def test_invalid_token(client):
    """Should reject request with invalid token."""
    resp = await client.get("/api/auth/me", headers={
        "Authorization": "Bearer invalid_token_here"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout(client, auth_token):
    """Should logout successfully."""
    resp = await client.post("/api/auth/logout", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_login(client):
    """Admin should be able to login."""
    resp = await client.post("/api/auth/login", json={
        "phone": "13900001111",
        "password": "demo123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_research_login(client):
    """Research staff should be able to login."""
    resp = await client.post("/api/auth/login", json={
        "phone": "13900002222",
        "password": "demo123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["user"]["role"] == "research"
