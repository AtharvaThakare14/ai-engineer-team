"""Tests for Permissions and Security Engine."""

from pathlib import Path
import pytest
from engineering_team.models import ApprovalStatus
from engineering_team.permissions import PermissionDeniedError, PermissionsManager


def test_allowed_path_resolution(permissions: PermissionsManager, temp_repo: Path):
    """Test that files within the allowed root pass validation."""
    valid_file = temp_repo / "app.py"
    resolved = permissions.validate_path(valid_file)
    assert resolved == valid_file.resolve()


def test_path_traversal_prevention(permissions: PermissionsManager, temp_repo: Path):
    """Test that directory traversal attempts outside approved roots are blocked."""
    forbidden = temp_repo.parent.parent / "sensitive.txt"
    with pytest.raises(PermissionDeniedError) as exc_info:
        permissions.validate_path(forbidden)
    assert "Access denied" in str(exc_info.value)


def test_approval_requirement_check(permissions: PermissionsManager):
    """Test checking risky actions against approval policy."""
    assert permissions.requires_approval("MODIFY_FILE") is True
    assert permissions.requires_approval("RUN_COMMAND") is True
    assert permissions.requires_approval("READ_FILE") is False


def test_request_and_decide_approval(permissions: PermissionsManager):
    """Test full approval lifecycle: request -> decide (approved & rejected)."""
    # 1. Request approval
    req = permissions.request_approval(
        task_id="TASK-TEST1",
        action_type="MODIFY_FILE",
        description="Edit app.py to fix bug",
        details={"file": "app.py"}
    )
    assert req.status == ApprovalStatus.PENDING
    assert req.request_id in permissions.pending_approvals

    # 2. Decide approval - approve
    decided = permissions.decide_approval(req.request_id, approved=True, decided_by="alice")
    assert decided.status == ApprovalStatus.APPROVED
    assert decided.decided_by == "alice"
    assert decided.decided_at is not None

    # 3. Request another and reject
    req2 = permissions.request_approval(
        task_id="TASK-TEST2",
        action_type="RUN_COMMAND",
        description="Run arbitrary command"
    )
    decided2 = permissions.decide_approval(req2.request_id, approved=False, decided_by="bob")
    assert decided2.status == ApprovalStatus.REJECTED


def test_audit_log_written(permissions: PermissionsManager):
    """Verify that audit entries are appended to the log file."""
    permissions.log_audit("TEST_ACTION", "test_user", {"key": "value"})
    assert permissions.audit_log_path.exists()
    content = permissions.audit_log_path.read_text(encoding="utf-8")
    assert "TEST_ACTION" in content
    assert "test_user" in content
