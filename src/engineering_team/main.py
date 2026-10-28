"""Main application entrypoint and FastAPI operational service."""

import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import re
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from engineering_team.agents.engineer import EngineerAgent
from engineering_team.agents.reviewer import CodeReviewer
from engineering_team.agents.triager import IssueTriager
from engineering_team.config import get_settings
from engineering_team.integrations.antigravity_adapter import AntigravityAdapter
from engineering_team.integrations.mattermost import MattermostClient
from engineering_team.integrations.switch_client import SwitchClient
from engineering_team.models import EngineeringTask, SwitchEvent
from engineering_team.permissions import PermissionsManager
from engineering_team.tools.repository import RepoTools
from engineering_team.tools.testing import TestRunner
from engineering_team.workflow import EngineeringWorkflow

# Configure Logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("engineering_team")

# Initialize Core Services
permissions = PermissionsManager(settings)
repo_tools = RepoTools(settings.target_repo_path, permissions)
test_runner = TestRunner(settings.target_repo_path, permissions)
antigravity_adapter = AntigravityAdapter()

triager = IssueTriager(repo_tools)
engineer = EngineerAgent(repo_tools, test_runner, permissions, antigravity_adapter)
reviewer = CodeReviewer()

switch_client = SwitchClient(settings)
mattermost_client = MattermostClient(settings)

workflow = EngineeringWorkflow(
    settings=settings,
    triager=triager,
    engineer=engineer,
    reviewer=reviewer,
    permissions=permissions,
    switch_client=switch_client,
    mattermost_client=mattermost_client
)


async def on_switch_message(event: SwitchEvent) -> None:
    """Dispatches incoming addressed Switch messages to the engineering workflow."""
    content = event.payload.content.strip()
    user_id = event.payload.sender_id
    room_id = event.room_id

    # Check for approval commands: !approve <request_id> or !reject <request_id>
    approve_match = re.search(r"^!approve\s+([a-f0-9\-]+)", content, re.IGNORECASE)
    reject_match = re.search(r"^!reject\s+([a-f0-9\-]+)", content, re.IGNORECASE)

    if approve_match:
        req_id = approve_match.group(1)
        try:
            await workflow.process_approval_decision(req_id, approved=True, decided_by=user_id)
        except Exception as e:
            await switch_client.post_message(room_id, f"❌ Failed to approve `{req_id}`: {e}")
        return

    if reject_match:
        req_id = reject_match.group(1)
        try:
            await workflow.process_approval_decision(req_id, approved=False, decided_by=user_id)
        except Exception as e:
            await switch_client.post_message(room_id, f"❌ Failed to reject `{req_id}`: {e}")
        return

    # Normal engineering assignment
    try:
        await workflow.handle_user_request(content, user_id=user_id, room_id=room_id)
    except Exception as e:
        logger.exception("Error handling user request: %s", e)
        await switch_client.post_message(room_id, f"❌ An error occurred processing task: {e}")


switch_client.add_message_handler(on_switch_message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager to start and stop the Switch background listener."""
    logger.info("Starting AI Engineering Team Service...")
    listener_task = asyncio.create_task(switch_client.connect_and_listen())
    try:
        yield
    finally:
        logger.info("Shutting down AI Engineering Team Service...")
        switch_client.stop()
        listener_task.cancel()
        try:
            await listener_task
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(
    title="AI Engineering Team",
    description="Multi-agent software engineering team integrated with Switch and Mattermost",
    version="0.1.0",
    lifespan=lifespan
)

STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve the complete interactive frontend dashboard."""
    if not STATIC_INDEX.exists():
        return HTMLResponse("<h1>Frontend dashboard not found</h1>", status_code=404)
    return HTMLResponse(STATIC_INDEX.read_text(encoding="utf-8"))


class CreateTaskRequest(BaseModel):
    content: str
    user_id: str = "developer"
    room_id: str = "default_room"


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Liveness probe."""
    return {"status": "ok", "service": "ai-engineering-team"}


@app.get("/ready")
def readiness_check() -> Dict[str, Any]:
    """Readiness probe reporting integration statuses."""
    return {
        "status": "ready",
        "antigravity": antigravity_adapter.check_health(),
        "switch": {
            "server": settings.switch_server_url,
            "agent_id": switch_client.agent_id or "not_registered",
            "connection_id": switch_client.connection_id
        },
        "target_repo": str(settings.target_repo_path)
    }


@app.get("/api/tasks")
def list_tasks() -> List[Dict[str, Any]]:
    """List all tracked engineering tasks."""
    return [task.model_dump() for task in workflow.tasks.values()]


@app.get("/api/tasks/{task_id}")
def get_task_detail(task_id: str) -> Dict[str, Any]:
    """Retrieve full details of a specific task."""
    try:
        return workflow.get_task(task_id).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")


@app.post("/api/tasks")
async def create_task(req: CreateTaskRequest) -> Dict[str, Any]:
    """Manually assign an engineering task via REST API."""
    task = await workflow.handle_user_request(req.content, user_id=req.user_id, room_id=req.room_id)
    return task.model_dump()


@app.post("/api/approvals/{request_id}/approve")
async def approve_request(request_id: str, request: Request) -> Dict[str, Any]:
    """Interactive button endpoint to approve a change."""
    try:
        task = await workflow.process_approval_decision(request_id, approved=True, decided_by="mattermost_user")
        return {"status": "approved", "task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/approvals/{request_id}/reject")
async def reject_request(request_id: str, request: Request) -> Dict[str, Any]:
    """Interactive button endpoint to reject a change."""
    try:
        task = await workflow.process_approval_decision(request_id, approved=False, decided_by="mattermost_user")
        return {"status": "rejected", "task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/audit")
def get_audit_trail() -> List[Dict[str, Any]]:
    """Return recent entries from the audit log."""
    log_file = permissions.audit_log_path
    if not log_file.exists():
        return []
    import json
    entries = []
    for line in log_file.read_text(encoding="utf-8").splitlines()[-100:]:
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries
