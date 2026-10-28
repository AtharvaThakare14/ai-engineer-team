"""Tests for integrations: Mattermost, Antigravity Adapter, and FastAPI endpoints."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from engineering_team.integrations.antigravity_adapter import AntigravityAdapter
from engineering_team.integrations.mattermost import MattermostClient
from engineering_team.main import app
from engineering_team.models import ApprovalRequest, EngineeringTask, TaskStatus, TaskType


def test_mattermost_card_formatting(mattermost_client: MattermostClient):
    """Test generating a markdown card for Mattermost."""
    task = EngineeringTask(
        title="Fix Null Pointer",
        description="Null pointer in app.py",
        task_type=TaskType.BUG,
        status=TaskStatus.COMPLETED,
        acceptance_criteria=["Must not throw NPE"],
        target_files=["app.py"]
    )
    card = mattermost_client.format_task_card(task)
    assert "Fix Null Pointer" in card
    assert "COMPLETED" in card
    assert "app.py" in card


def test_mattermost_approval_buttons(mattermost_client: MattermostClient):
    """Test generating interactive button card for Mattermost."""
    req = ApprovalRequest(
        task_id="TASK-123",
        action_type="MODIFY_FILE",
        description="Modify app.py"
    )
    payload = mattermost_client.format_approval_request(req, callback_base_url="http://localhost:8082")
    assert "attachments" in payload["props"]
    actions = payload["props"]["attachments"][0]["actions"]
    assert len(actions) == 2
    assert actions[0]["id"] == "approve"
    assert actions[1]["id"] == "reject"


def test_antigravity_adapter_health_and_prompt(antigravity_adapter: AntigravityAdapter):
    """Test AntigravityAdapter health check and prompt exporter."""
    health = antigravity_adapter.check_health()
    assert health["name"] == "AntigravityAdapter"
    assert "limitation_documented" in health

    task = EngineeringTask(
        title="Add feature",
        description="Implement user greeting",
        task_type=TaskType.FEATURE,
        acceptance_criteria=["Say hello"]
    )
    prompt = antigravity_adapter.format_manual_prompt(task, {"app.py": "print('hi')"})
    assert "Add feature" in prompt
    assert "Say hello" in prompt


@pytest.mark.asyncio
async def test_fastapi_endpoints():
    """Test FastAPI health, ready, and task endpoints."""
    from engineering_team.main import switch_client, test_runner, workflow
    switch_client.mock_mode = True
    test_runner.mock_mode = True
    workflow.engineer.test_runner.mock_mode = True

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 0. Frontend UI
        res_ui = await ac.get("/")
        assert res_ui.status_code == 200
        assert "Switch AI" in res_ui.text

        # 1. Health
        res_h = await ac.get("/health")
        assert res_h.status_code == 200
        assert res_h.json()["status"] == "ok"

        # 2. Ready
        res_r = await ac.get("/ready")
        assert res_r.status_code == 200
        assert res_r.json()["status"] == "ready"

        # 3. Create task via API
        res_t = await ac.post("/api/tasks", json={
            "content": "Fix calculation in app.py",
            "user_id": "test_dev",
            "room_id": "test_room"
        })
        assert res_t.status_code == 200
        data = res_t.json()
        assert data["status"] == "AWAITING_APPROVAL"
        task_id = data["id"]
        approval_id = data["approvals"][0]["request_id"]

        # 4. Approve via API
        res_appr = await ac.post(f"/api/approvals/{approval_id}/approve")
        assert res_appr.status_code == 200
        assert res_appr.json()["status"] == "approved"

        # 5. Get task detail
        res_det = await ac.get(f"/api/tasks/{task_id}")
        assert res_det.status_code == 200
        assert res_det.json()["status"] == "COMPLETED"
