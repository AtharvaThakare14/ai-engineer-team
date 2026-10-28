"""Permissions and Security Engine.

Enforces:
1. Approved repository directory whitelisting (prevents directory traversal attacks)
2. Human-in-the-loop approval gates before file modification or risky operations
3. Comprehensive audit logging
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import uuid

from engineering_team.config import Settings
from engineering_team.models import ApprovalRequest, ApprovalStatus

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    """Raised when an operation violates security policy."""
    pass


class PermissionsManager:
    def __init__(self, settings: Settings, audit_log_path: Optional[Path] = None):
        self.settings = settings
        self.allowed_paths: List[Path] = [p.resolve() for p in settings.allowed_repo_paths]
        self.audit_log_path = audit_log_path or Path("audit.log")
        self.pending_approvals: Dict[str, ApprovalRequest] = {}

    def is_path_allowed(self, target_path: Path) -> bool:
        """Verify that target_path resolves strictly within one of the allowed directories."""
        try:
            resolved = target_path.resolve()
            for allowed in self.allowed_paths:
                try:
                    resolved.relative_to(allowed)
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False

    def validate_path(self, target_path: Path) -> Path:
        """Validate path or raise PermissionDeniedError."""
        resolved = target_path.resolve()
        if not self.is_path_allowed(resolved):
            msg = f"Access denied: Path '{target_path}' is outside approved directories."
            self.log_audit("ACCESS_DENIED", "security", {"path": str(target_path), "reason": "Path traversal attempt"})
            logger.warning(msg)
            raise PermissionDeniedError(msg)
        return resolved

    def requires_approval(self, action_type: str) -> bool:
        """Check if an action requires explicit human approval."""
        if not self.settings.human_approval_required:
            return False
        # Actions requiring human consent:
        risky_actions = {"MODIFY_FILE", "DELETE_FILE", "RUN_COMMAND", "GIT_BRANCH", "GIT_COMMIT"}
        return action_type in risky_actions

    def request_approval(self, task_id: str, action_type: str, description: str, details: Optional[dict] = None) -> ApprovalRequest:
        """Create a pending approval request."""
        req = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            task_id=task_id,
            action_type=action_type,
            description=description,
            details=details or {},
            status=ApprovalStatus.PENDING
        )
        self.pending_approvals[req.request_id] = req
        self.log_audit("APPROVAL_REQUESTED", "permissions", {
            "request_id": req.request_id,
            "task_id": task_id,
            "action": action_type,
            "description": description
        })
        logger.info("Approval requested: %s for task %s (%s)", req.request_id, task_id, action_type)
        return req

    def decide_approval(self, request_id: str, approved: bool, decided_by: str = "human_operator") -> ApprovalRequest:
        """Approve or reject a pending request."""
        if request_id not in self.pending_approvals:
            raise KeyError(f"No pending approval found with ID '{request_id}'")

        req = self.pending_approvals[request_id]
        req.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        req.decided_at = datetime.now(timezone.utc)
        req.decided_by = decided_by

        self.log_audit(
            "APPROVAL_DECIDED",
            decided_by,
            {
                "request_id": request_id,
                "task_id": req.task_id,
                "decision": req.status.value,
                "action": req.action_type
            }
        )
        logger.info("Approval %s decided: %s by %s", request_id, req.status.value, decided_by)
        return req

    def log_audit(self, action: str, actor: str, details: dict) -> None:
        """Append an entry to the audit log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "details": details
        }
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error("Failed to write to audit log: %s", e)
