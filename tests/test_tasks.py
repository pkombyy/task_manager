import uuid

import pytest

from models.task import TaskPriority, TaskStatus


@pytest.mark.asyncio
async def test_create_task(test_client, monkeypatch):
    async def fake_publish(_task_id: uuid.UUID, _priority: TaskPriority):
        return None

    monkeypatch.setattr("api.v1.tasks.publish_task", fake_publish)

    payload = {"title": "demo", "description": "desc", "priority": "HIGH"}
    response = await test_client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["priority"] == "HIGH"
    assert data["status"] == TaskStatus.NEW.value


@pytest.mark.asyncio
async def test_list_and_status(test_client, monkeypatch):
    async def fake_publish(*_args, **_kwargs):
        return None

    monkeypatch.setattr("api.v1.tasks.publish_task", fake_publish)
    payload = {"title": "demo-2", "priority": "LOW"}
    resp = await test_client.post("/api/v1/tasks", json=payload)
    task_id = resp.json()["id"]

    list_resp = await test_client.get("/api/v1/tasks")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    status_resp = await test_client.get(f"/api/v1/tasks/{task_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] in {
        TaskStatus.NEW.value,
        TaskStatus.PENDING.value,
        TaskStatus.IN_PROGRESS.value,
        TaskStatus.COMPLETED.value,
        TaskStatus.FAILED.value,
    }


@pytest.mark.asyncio
async def test_cancel_task(test_client, monkeypatch):
    async def fake_publish(*_args, **_kwargs):
        return None

    monkeypatch.setattr("api.v1.tasks.publish_task", fake_publish)
    payload = {"title": "cancel-me", "priority": "MEDIUM"}
    resp = await test_client.post("/api/v1/tasks", json=payload)
    task_id = resp.json()["id"]

    delete_resp = await test_client.delete(f"/api/v1/tasks/{task_id}")
    assert delete_resp.status_code == 204

    status_resp = await test_client.get(f"/api/v1/tasks/{task_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == TaskStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_list_filter_priority(test_client, monkeypatch):
    async def fake_publish(*_args, **_kwargs):
        return None

    monkeypatch.setattr("api.v1.tasks.publish_task", fake_publish)
    await test_client.post("/api/v1/tasks", json={"title": "low-one", "priority": "LOW"})
    await test_client.post("/api/v1/tasks", json={"title": "high-one", "priority": "HIGH"})

    resp = await test_client.get("/api/v1/tasks", params={"priority": "LOW"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert all(item["priority"] == "LOW" for item in data["items"])


@pytest.mark.asyncio
async def test_list_filter_status(test_client, monkeypatch):
    async def fake_publish(*_args, **_kwargs):
        return None

    monkeypatch.setattr("api.v1.tasks.publish_task", fake_publish)
    # создаём и сразу отменяем задачу, чтобы получить CANCELLED
    resp = await test_client.post(
        "/api/v1/tasks",
        json={"title": "to-cancel", "priority": "MEDIUM"},
    )
    task_id = resp.json()["id"]
    await test_client.delete(f"/api/v1/tasks/{task_id}")

    resp_cancelled = await test_client.get("/api/v1/tasks", params={"status": "CANCELLED"})
    assert resp_cancelled.status_code == 200
    data = resp_cancelled.json()
    assert data["total"] >= 1
    assert all(item["status"] == "CANCELLED" for item in data["items"])


@pytest.mark.asyncio
async def test_pagination(test_client, monkeypatch):
    async def fake_publish(*_args, **_kwargs):
        return None

    monkeypatch.setattr("api.v1.tasks.publish_task", fake_publish)
    # создаём несколько задач
    for i in range(5):
        await test_client.post("/api/v1/tasks", json={"title": f"page-{i}", "priority": "LOW"})

    resp = await test_client.get("/api/v1/tasks", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2

    resp_next = await test_client.get("/api/v1/tasks", params={"limit": 2, "offset": 2})
    assert resp_next.status_code == 200
    data_next = resp_next.json()
    assert len(data_next["items"]) == 2


@pytest.mark.asyncio
async def test_health(test_client):
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

