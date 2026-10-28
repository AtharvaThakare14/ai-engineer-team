"""Mattermost integration for rich formatting, card attachments, and button interactions."""

import logging
from typing import Any, Dict, List, Optional
import httpx

from engineering_team.config import Settings
from engineering_team.models import ApprovalRequest, EngineeringTask, TaskStatus

logger = logging.getLogger(__name__)


class MattermostClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.mattermost_url.rstrip("/")
        self.bot_token = settings.mattermost_bot_token
        self.team = settings.mattermost_team
        self.mock_mode: bool = False
        self.sent_posts: List[Dict[str, Any]] = []

    def format_status_badge(self, status: TaskStatus) -> str:
        """Format a status emoji badge for Mattermost."""
        badges = {
            TaskStatus.CREATED: "🆕 `CREATED`",
            TaskStatus.TRIAGED: "📋 `TRIAGED`",
            TaskStatus.ANALYZING: "🔍 `ANALYZING`",
            TaskStatus.AWAITING_APPROVAL: "⏳ `AWAITING APPROVAL`",
            TaskStatus.APPROVED: "✅ `APPROVED`",
            TaskStatus.EXECUTING: "⚙️ `EXECUTING`",
            TaskStatus.TESTING: "🧪 `TESTING`",
            TaskStatus.IN_REVIEW: "👀 `IN REVIEW`",
            TaskStatus.COMPLETED: "🎉 `COMPLETED`",
            TaskStatus.REJECTED: "🛑 `REJECTED`",
            TaskStatus.FAILED: "❌ `FAILED`",
        }
        return badges.get(status, f"`{status.value}`")

    def format_task_card(self, task: EngineeringTask) -> str:
        """Format an EngineeringTask into a clean, professional Mattermost message."""
        badge = self.format_status_badge(task.status)
        lines = [
            f"### {badge} Task: **{task.title}** ({task.id})",
            f"**Type:** `{task.task_type.value}` | **Assigned To:** `{task.assigned_agent}`",
            "",
            f"**Description:** {task.description}",
        ]

        if task.acceptance_criteria:
            lines.append("")
            lines.append("**Acceptance Criteria:**")
            for ac in task.acceptance_criteria:
                lines.append(f"- [ ] {ac}")

        if task.target_files:
            lines.append("")
            lines.append(f"**Target Files:** {', '.join(f'`{f}`' for f in task.target_files)}")

        if task.branch_name:
            lines.append(f"**Branch:** `{task.branch_name}`")

        if task.test_results:
            tr = task.test_results
            t_badge = "✅ Passed" if tr.passed else "❌ Failed"
            lines.append("")
            lines.append(f"**Test Results ({t_badge}):**")
            lines.append(f"```text\n{tr.summary}\n```")

        if task.review_result:
            rr = task.review_result
            r_badge = "✅ Approved" if rr.approved else "⚠️ Changes Requested"
            lines.append("")
            lines.append(f"**Code Review ({r_badge}):** {rr.comments}")
            for f in rr.findings:
                lines.append(f"- **[{f.severity}]** {f.message} (`{f.file_path or 'all'}`)")

        return "\n".join(lines)

    def format_approval_request(self, approval: ApprovalRequest, callback_base_url: str) -> Dict[str, Any]:
        """Format an ApprovalRequest with interactive action buttons for Mattermost."""
        message = (
            f"### 🛡️ **Human Approval Required**\n"
            f"**Task ID:** `{approval.task_id}` | **Action:** `{approval.action_type}`\n\n"
            f"{approval.description}\n\n"
            f"Please review the proposed change and select an action below:"
        )

        attachments = [
            {
                "fallback": f"Approval needed for {approval.action_type}: {approval.description}",
                "color": "#FFA500",
                "actions": [
                    {
                        "id": "approve",
                        "name": "Approve Change",
                        "integration": {
                            "url": f"{callback_base_url.rstrip('/')}/api/approvals/{approval.request_id}/approve",
                            "context": {"task_id": approval.task_id, "action": "approve"}
                        }
                    },
                    {
                        "id": "reject",
                        "name": "Reject",
                        "integration": {
                            "url": f"{callback_base_url.rstrip('/')}/api/approvals/{approval.request_id}/reject",
                            "context": {"task_id": approval.task_id, "action": "reject"}
                        }
                    }
                ]
            }
        ]

        return {"message": message, "props": {"attachments": attachments}}

    async def post_to_channel(self, channel_id: str, message: str, props: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Directly post a message to Mattermost channel (if direct credentials are used)."""
        payload = {"channel_id": channel_id, "message": message, "props": props or {}}
        self.sent_posts.append(payload)

        if self.mock_mode or not self.bot_token:
            logger.info("[Mock Mattermost] Posted to channel %s: %s", channel_id, message[:60])
            return {"id": "mock_post_id", "status": "ok"}

        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/v4/posts",
                json=payload,
                headers=headers
            )
            resp.raise_for_status()
            return resp.json()
