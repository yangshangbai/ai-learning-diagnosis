"""Tests for student CRUD endpoints."""
import pytest


@pytest.mark.asyncio
async def test_list_students(client, auth_token):
    """Should list all students."""
    resp = await client.get("/api/students", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_list_students_with_class_filter(client, auth_token):
    """Should filter students by class_id."""
    resp = await client.get("/api/students", headers={
        "Authorization": f"Bearer {auth_token}"
    }, params={"class_id": "c1"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_student(client, auth_token):
    """Should get a specific student by ID."""
    # First get list to find an ID
    list_resp = await client.get("/api/students", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    students = list_resp.json().get("data", [])
    if students:
        student_id = students[0]["id"]
        resp = await client.get(f"/api/students/{student_id}", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["id"] == student_id


@pytest.mark.asyncio
async def test_get_nonexistent_student(client, auth_token):
    """Should return 404 for non-existent student."""
    resp = await client.get("/api/students/nonexistent_id", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_student(client, admin_token):
    """Admin should be able to create a student."""
    resp = await client.post("/api/students", headers={
        "Authorization": f"Bearer {admin_token}"
    }, json={
        "name": "测试学生",
        "class_id": "c1",
        "phone": "13800000001"
    })
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert data["data"]["name"] == "测试学生"


@pytest.mark.asyncio
async def test_update_student(client, admin_token):
    """Admin should be able to update a student."""
    # Create first
    create_resp = await client.post("/api/students", headers={
        "Authorization": f"Bearer {admin_token}"
    }, json={
        "name": "更新测试学生",
        "class_id": "c1"
    })
    student_id = create_resp.json()["data"]["id"]

    # Then update
    resp = await client.put(f"/api/students/{student_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    }, json={
        "name": "已更新学生",
        "class_id": "c1"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["name"] == "已更新学生"


@pytest.mark.asyncio
async def test_delete_student(client, admin_token):
    """Admin should be able to delete a student."""
    # Create first
    create_resp = await client.post("/api/students", headers={
        "Authorization": f"Bearer {admin_token}"
    }, json={
        "name": "待删除学生",
        "class_id": "c1"
    })
    student_id = create_resp.json()["data"]["id"]

    # Then delete
    resp = await client.delete(f"/api/students/{student_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200

    # Verify deleted
    get_resp = await client.get(f"/api/students/{student_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_teacher_cannot_create_student(client, auth_token):
    """Teacher should not be able to create students."""
    resp = await client.post("/api/students", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "name": "测试学生",
        "class_id": "c1"
    })
    # Should be forbidden or unauthorized
    assert resp.status_code in [403, 401]
