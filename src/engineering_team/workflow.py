"""Engineering Workflow State Machine & Multi-Agent Orchestrator."""

import logging
from typing import Dict, Optional

from engineering_team.agents.engineer import EngineerAgent
from engineering_team.agents.reviewer import CodeReviewer
from engineering_team.agents.triager import IssueTriager
from engineering_team.config import Settings
from engineering_team.integrations.mattermost import MattermostClient
from engineering_team.integrations.switch_client import SwitchClient
from engineering_team.models import ApprovalStatus, EngineeringTask, TaskStatus
from engineering_team.permissions import PermissionsManager

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """Raised on invalid workflow state transitions."""
    pass


class EngineeringWorkflow:
    def __init__(
        self,
        settings: Settings,
        triager: IssueTriager,
        engineer: EngineerAgent,
        reviewer: CodeReviewer,
        permissions: PermissionsManager,
        switch_client: SwitchClient,
        mattermost_client: MattermostClient
    ):
        self.settings = settings
        self.triager = triager
        self.engineer = engineer
        self.reviewer = reviewer
        self.permissions = permissions
        self.switch_client = switch_client
        self.mattermost_client = mattermost_client

        self.tasks: Dict[str, EngineeringTask] = {}

    def get_task(self, task_id: str) -> EngineeringTask:
        """Retrieve task by ID or raise KeyError."""
        if task_id not in self.tasks:
            raise KeyError(f"Task with ID '{task_id}' not found.")
        return self.tasks[task_id]

    async def handle_user_request(self, content: str, user_id: str, room_id: str) -> EngineeringTask:
        """Handle incoming chat message: Triage -> Plan -> Request Approval."""
        logger.info("Processing user request from %s in room %s", user_id, room_id)

        # 1. Triage the issue
        task = await self.triager.triage(content, user_id=user_id, room_id=room_id)
        self.tasks[task.id] = task

        # Notify room of triage
        triage_msg = (
            f"📋 **Task Created:** `{task.title}` ({task.id})\n"
            f"Type: `{task.task_type.value}` | Assigned to: `lead-engineer`\n"
            f"Target files: {', '.join(task.target_files) if task.target_files else 'None detected yet'}"
        )
        await self.switch_client.post_message(room_id, triage_msg)

        # 2. Lead Engineer analyzes and formulates plan
        approval_req = await self.engineer.analyze_and_plan(task)

        # 3. Post approval request to room / Mattermost
        approval_msg = (
            f"⏳ **Human Approval Required for Task {task.id}**\n\n"
            f"{approval_req.description}\n\n"
            f"To approve, reply with: `!approve {approval_req.request_id}`\n"
            f"To reject, reply with: `!reject {approval_req.request_id}`"
        )
        await self.switch_client.post_message(room_id, approval_msg)

        return task

    async def process_approval_decision(
        self,
        request_id: str,
        approved: bool,
        decided_by: str = "human_operator"
    ) -> EngineeringTask:
        """Process human decision on a pending approval."""
        approval = self.permissions.decide_approval(request_id, approved, decided_by=decided_by)
        task = self.get_task(approval.task_id)

        if not approved:
            task.status = TaskStatus.REJECTED
            task.log_event("REJECTED", decided_by, {"request_id": request_id})
            rejection_msg = f"🛑 **Task {task.id} Rejected** by {decided_by}."
            await self.switch_client.post_message(task.room_id, rejection_msg)
            return task

        # 1. Engineer applies changes and runs tests
        await self.switch_client.post_message(
            task.room_id,
            f"⚙️ **Approval received!** Implementing fixes and running test suite..."
        )
        task = await self.engineer.apply_changes_and_test(task)

        # 2. Code Reviewer evaluates results
        await self.switch_client.post_message(
            task.room_id,
            f"👀 **Executing Code Review** for {task.id}..."
        )
        review_result = await self.reviewer.review_task(task)

        # 3. Post final report card
        final_card = self.mattermost_client.format_task_card(task)
        await self.switch_client.post_message(task.room_id, final_card)

        return task
