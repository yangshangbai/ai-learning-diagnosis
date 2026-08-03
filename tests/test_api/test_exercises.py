"""Tests for exercise plan endpoints."""
import pytest


@pytest.mark.asyncio
async def test_list_plans(client, auth_token):
    """Should list exercise plans."""
    resp = await client.get("/api/exercises", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_create_plan(client, auth_token):
    """Should create a new exercise plan."""
    resp = await client.post("/api/exercises", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "student_id": "s1",
        "name": "测试练习计划",
        "knowledge_points": ["分数通分"],
        "question_count": 15
    })
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_get_plan(client, auth_token):
    """Should get a specific exercise plan."""
    # Create first
    create_resp = await client.post("/api/exercises", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "student_id": "s1",
        "name": "获取测试计划",
        "knowledge_points": ["分数应用"],
        "question_count": 10
    })
    plan_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/exercises/{plan_id}", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["id"] == plan_id


@pytest.mark.asyncio
async def test_delete_plan(client, auth_token):
    """Should delete an exercise plan."""
    # Create first
    create_resp = await client.post("/api/exercises", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "student_id": "s1",
        "name": "待删除计划",
        "knowledge_points": ["方程"],
        "question_count": 5
    })
    plan_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/exercises/{plan_id}", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_plan_with_invalid_student(client, auth_token):
    """Should reject exercise plan with non-existent student_id."""
    resp = await client.post("/api/exercises", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "student_id": "nonexistent_student",
        "name": "无效计划",
        "knowledge_points": ["测试"],
        "question_count": 5
    })
    assert resp.status_code in [400, 404, 422]
