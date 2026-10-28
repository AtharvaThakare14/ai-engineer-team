"""Data models for tasks, permissions, reviews, and Switch protocol events."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    TRIAGED = "TRIAGED"
    ANALYZING = "ANALYZING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    TESTING = "TESTING"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class TaskType(str, Enum):
    BUG = "BUG"
    FEATURE = "FEATURE"
    EXPLORATION = "EXPLORATION"
    TEST = "TEST"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CodeChange(BaseModel):
    file_path: str
    original_content: Optional[str] = None
    new_content: str
    diff: Optional[str] = None
    explanation: str = ""


class ApprovalRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    action_type: str = Field(..., description="Action being requested, e.g. MODIFY_FILE, RUN_COMMAND")
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None


class TestResult(BaseModel):
    task_id: str
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    summary: str
    duration_seconds: float = 0.0


class ReviewFinding(BaseModel):
    severity: str = Field(..., description="INFO, WARNING, or CRITICAL")
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class ReviewResult(BaseModel):
    task_id: str
    approved: bool
    findings: List[ReviewFinding] = Field(default_factory=list)
    comments: str = ""


class EngineeringTask(BaseModel):
    id: str = Field(default_factory=lambda: f"TASK-{uuid.uuid4().hex[:6].upper()}")
    title: str
    description: str
    task_type: TaskType = TaskType.BUG
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_agent: str = "lead-engineer"
    acceptance_criteria: List[str] = Field(default_factory=list)
    target_files: List[str] = Field(default_factory=list)
    branch_name: Optional[str] = None
    proposed_changes: List[CodeChange] = Field(default_factory=list)
    test_results: Optional[TestResult] = None
    review_result: Optional[ReviewResult] = None
    room_id: str = "default_room"
    user_id: str = "developer"
    approvals: List[ApprovalRequest] = Field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)

    def log_event(self, action: str, agent: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Add an event entry to the task audit trail."""
        self.updated_at = datetime.now(timezone.utc)
        self.audit_trail.append({
            "timestamp": self.updated_at.isoformat(),
            "action": action,
            "agent": agent,
            "status": self.status.value,
            "details": details or {}
        })


# --- Switch Agent Protocol Models ---

class SwitchMessagePayload(BaseModel):
    content: str
    sender_id: str
    addressed: bool = False
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: Optional[str] = None


class SwitchEvent(BaseModel):
    event: str
    room_id: str
    payload: SwitchMessagePayload
    cursor: Optional[int] = None


class IntegrationProfile(BaseModel):
    connection_model: str = "always_on"
    message_exchange: bool = True
    pre_invocation_mediation: List[Any] = Field(default_factory=list)
    post_invocation_mediation: List[Any] = Field(default_factory=list)
    event_reporting: List[Any] = Field(default_factory=list)


class SwitchRegistrationRequest(BaseModel):
    name: str
    description: str
    connector_type: str = "custom"
    display_name: Optional[str] = None
    integration_profile: IntegrationProfile = Field(default_factory=IntegrationProfile)
    overwrite: bool = True


class SwitchRegistrationResponse(BaseModel):
    id: str
    api_key: str
