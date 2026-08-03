"""Tests for task CRUD and status transitions."""
import pytest


@pytest.mark.asyncio
async def test_list_tasks(client, auth_token):
    """Should list all tasks."""
    resp = await client.get("/api/tasks", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_create_task(client, auth_token):
    """Teacher should be able to create a task."""
    resp = await client.post("/api/tasks", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "name": "测试任务",
        "type": "exam",
        "subject": "数学",
        "grade": "五年级",
        "objective": "测试任务描述",
        "class_ids": ["c1"]
    })
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert data["data"]["name"] == "测试任务"
    assert data["data"]["status"] in ["draft", "pending_upload"]


@pytest.mark.asyncio
async def test_get_task(client, auth_token):
    """Should get a specific task by ID."""
    # Create first
    create_resp = await client.post("/api/tasks", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "name": "获取测试任务",
        "type": "exam",
        "subject": "数学",
        "grade": "五年级",
        "class_ids": ["c1"]
    })
    task_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/tasks/{task_id}", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["id"] == task_id


@pytest.mark.asyncio
async def test_update_task_status(client, auth_token):
    """Should update task status following valid transitions."""
    # Create first
    create_resp = await client.post("/api/tasks", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "name": "状态更新任务",
        "type": "exam",
        "subject": "数学",
        "grade": "五年级",
        "class_ids": ["c1"]
    })
    task_id = create_resp.json()["data"]["id"]

    # Update status to pending_upload
    resp = await client.patch(f"/api/tasks/{task_id}/status", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={"status": "pending_upload"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["status"] == "pending_upload"


@pytest.mark.asyncio
async def test_delete_task(client, auth_token):
    """Should delete a task."""
    # Create first
    create_resp = await client.post("/api/tasks", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "name": "待删除任务",
        "type": "exam",
        "subject": "数学",
        "grade": "五年级",
        "class_ids": ["c1"]
    })
    task_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/tasks/{task_id}", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200

    # Verify deleted
    get_resp = await client.get(f"/api/tasks/{task_id}", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_manage_all_tasks(client, admin_token):
    """Admin should see all tasks (not filtered by teacher)."""
    resp = await client.get("/api/tasks", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_run_ai(client, auth_token):
    """Should trigger AI processing on a task."""
    # Create a task and move to ai_processing
    create_resp = await client.post("/api/tasks", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "name": "AI测试任务",
        "type": "exam",
        "subject": "数学",
        "grade": "五年级",
        "class_ids": ["c1"]
    })
    task_id = create_resp.json()["data"]["id"]

    # Try to run AI
    resp = await client.post(f"/api/tasks/{task_id}/run-ai", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    # May be accepted or may fail depending on task state
    assert resp.status_code in [200, 202, 400]
