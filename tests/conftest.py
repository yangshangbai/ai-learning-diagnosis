"""
Pytest configuration with fixtures for API testing.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app
from database import init_db, async_session_factory


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client with test database."""
    await init_db()
    from seed_data import seed_all
    await seed_all()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_token(client):
    """Login as teacher (李老师) and return access token."""
    resp = await client.post("/api/auth/login", json={
        "phone": "13800001111",
        "password": "demo123"
    })
    data = resp.json()
    return data["data"]["access_token"]


@pytest_asyncio.fixture
async def admin_token(client):
    """Login as admin (王校长) and return access token."""
    resp = await client.post("/api/auth/login", json={
        "phone": "13900001111",
        "password": "demo123"
    })
    data = resp.json()
    return data["data"]["access_token"]


@pytest_asyncio.fixture
async def research_token(client):
    """Login as research (赵教研) and return access token."""
    resp = await client.post("/api/auth/login", json={
        "phone": "13900002222",
        "password": "demo123"
    })
    data = resp.json()
    return data["data"]["access_token"]
