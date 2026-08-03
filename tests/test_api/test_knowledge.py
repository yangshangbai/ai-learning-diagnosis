"""Tests for knowledge tree endpoints."""
import pytest


@pytest.mark.asyncio
async def test_get_tree(client, research_token):
    """Should get the full knowledge tree."""
    resp = await client.get("/api/knowledge/tree", headers={
        "Authorization": f"Bearer {research_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    tree = data["data"]
    assert isinstance(tree, list)


@pytest.mark.asyncio
async def test_get_tree_with_subject_filter(client, research_token):
    """Should filter tree by subject."""
    resp = await client.get("/api/knowledge/tree", headers={
        "Authorization": f"Bearer {research_token}"
    }, params={"subject": "数学"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_node(client, research_token):
    """Should create a new knowledge node."""
    resp = await client.post("/api/knowledge", headers={
        "Authorization": f"Bearer {research_token}"
    }, json={
        "name": "测试知识点",
        "subject": "数学",
        "grade": "五年级",
        "parent_id": None
    })
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert data["data"]["name"] == "测试知识点"


@pytest.mark.asyncio
async def test_update_node(client, research_token):
    """Should update a knowledge node."""
    # Create first
    create_resp = await client.post("/api/knowledge", headers={
        "Authorization": f"Bearer {research_token}"
    }, json={
        "name": "更新测试节点",
        "subject": "数学",
        "grade": "五年级"
    })
    node_id = create_resp.json()["data"]["id"]

    resp = await client.put(f"/api/knowledge/{node_id}", headers={
        "Authorization": f"Bearer {research_token}"
    }, json={
        "name": "已更新节点",
        "subject": "数学",
        "grade": "五年级"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["name"] == "已更新节点"


@pytest.mark.asyncio
async def test_delete_node(client, research_token):
    """Should delete a knowledge node."""
    # Create first
    create_resp = await client.post("/api/knowledge", headers={
        "Authorization": f"Bearer {research_token}"
    }, json={
        "name": "待删除节点",
        "subject": "数学",
        "grade": "五年级"
    })
    node_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/knowledge/{node_id}", headers={
        "Authorization": f"Bearer {research_token}"
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_teacher_cannot_modify_knowledge(client, auth_token):
    """Teacher should not be able to modify knowledge tree."""
    resp = await client.post("/api/knowledge", headers={
        "Authorization": f"Bearer {auth_token}"
    }, json={
        "name": "测试节点",
        "subject": "数学",
        "grade": "五年级"
    })
    assert resp.status_code in [403, 401]
