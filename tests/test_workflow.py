"""Tests for end-to-end engineering workflow state machine."""

import pytest
from engineering_team.models import TaskStatus, TaskType
from engineering_team.workflow import EngineeringWorkflow


@pytest.mark.asyncio
async def test_full_successful_engineering_workflow(workflow: EngineeringWorkflow):
    """Test full cycle: user request -> triage -> approval -> execute -> test -> review -> completed."""
    # 1. User submits request
    task = await workflow.handle_user_request(
        content="Fix division by zero bug in app.py",
        user_id="developer_alice",
        room_id="room_engineering"
    )

    assert task.status == TaskStatus.AWAITING_APPROVAL
    assert task.task_type == TaskType.BUG
    assert "app.py" in task.target_files
    assert len(task.approvals) == 1

    approval_req = task.approvals[0]
    assert approval_req.action_type == "MODIFY_FILE"

    # 2. Human approves request
    completed_task = await workflow.process_approval_decision(
        request_id=approval_req.request_id,
        approved=True,
        decided_by="developer_alice"
    )

    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.branch_name is not None
    assert completed_task.test_results is not None
    assert completed_task.test_results.passed is True
    assert completed_task.review_result is not None
    assert completed_task.review_result.approved is True


@pytest.mark.asyncio
async def test_workflow_rejection(workflow: EngineeringWorkflow):
    """Test that human rejection halts the workflow and sets status to REJECTED."""
    task = await workflow.handle_user_request(
        content="Delete all files in app.py",
        user_id="developer_bob",
        room_id="room_engineering"
    )

    assert task.status == TaskStatus.AWAITING_APPROVAL
    approval_req = task.approvals[0]

    # Human rejects request
    rejected_task = await workflow.process_approval_decision(
        request_id=approval_req.request_id,
        approved=False,
        decided_by="lead_dev"
    )

    assert rejected_task.status == TaskStatus.REJECTED


@pytest.mark.asyncio
async def test_workflow_review_failure(workflow: EngineeringWorkflow):
    """Test that if tests fail during execution, the reviewer marks task as FAILED."""
    # Set test runner to simulate failure
    workflow.engineer.test_runner.mock_mode = True
    # Patch test_runner to return passed=False
    from engineering_team.models import TestResult
    workflow.engineer.test_runner.run_tests = lambda task_id: TestResult(
        task_id=task_id,
        passed=False,
        exit_code=1,
        stdout="FAIL: test_app.py",
        stderr="AssertionError",
        summary="1 failed"
    )

    task = await workflow.handle_user_request(
        content="Fix bug in app.py",
        user_id="alice",
        room_id="room_engineering"
    )

    approval_req = task.approvals[0]
    failed_task = await workflow.process_approval_decision(
        request_id=approval_req.request_id,
        approved=True,
        decided_by="alice"
    )

    assert failed_task.status == TaskStatus.FAILED
    assert failed_task.review_result.approved is False
    assert len(failed_task.review_result.findings) > 0
