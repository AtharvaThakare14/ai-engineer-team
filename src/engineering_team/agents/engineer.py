"""Lead Software Engineer Agent.

Inspects code, formulates fix plan, requests human approval,
creates isolated Git branches, applies modifications, and executes tests.
"""

import logging
from typing import Dict, List, Optional

from engineering_team.integrations.antigravity_adapter import AntigravityAdapter
from engineering_team.models import ApprovalRequest, CodeChange, EngineeringTask, TaskStatus
from engineering_team.permissions import PermissionsManager
from engineering_team.tools.repository import RepoTools
from engineering_team.tools.testing import TestRunner

logger = logging.getLogger(__name__)


class EngineerAgent:
    def __init__(
        self,
        repo_tools: RepoTools,
        test_runner: TestRunner,
        permissions: PermissionsManager,
        antigravity_adapter: AntigravityAdapter
    ):
        self.repo_tools = repo_tools
        self.test_runner = test_runner
        self.permissions = permissions
        self.antigravity = antigravity_adapter

    async def analyze_and_plan(self, task: EngineeringTask) -> ApprovalRequest:
        """Inspect code, formulate plan, and generate human approval request."""
        logger.info("Analyzing codebase for task %s: %s", task.id, task.title)
        task.status = TaskStatus.ANALYZING
        task.log_event("ANALYZING", "lead-engineer", {"target_files": task.target_files})

        # Read target file contents
        file_contents: Dict[str, str] = {}
        for rel_path in task.target_files:
            try:
                file_contents[rel_path] = self.repo_tools.read_file(rel_path)
            except Exception as e:
                logger.warning("Could not read file %s: %s", rel_path, e)

        # Plan the changes via Antigravity Adapter
        execution_plan = await self.antigravity.execute_task(task, file_contents)
        task.proposed_changes = execution_plan.get("proposed_changes", [])

        # Formulate description of changes for approval
        file_names = ", ".join(c.file_path for c in task.proposed_changes) or "No files"
        desc = (
            f"Proposed modification for {len(task.proposed_changes)} file(s): {file_names}.\n"
            f"Fix details: {task.title}\n"
            f"Branch: `fix/{task.id.lower()}`"
        )

        approval_req = self.permissions.request_approval(
            task_id=task.id,
            action_type="MODIFY_FILE",
            description=desc,
            details={"changes_count": len(task.proposed_changes), "files": [c.file_path for c in task.proposed_changes]}
        )

        task.approvals.append(approval_req)
        task.status = TaskStatus.AWAITING_APPROVAL
        task.log_event("AWAITING_APPROVAL", "lead-engineer", {"request_id": approval_req.request_id})

        return approval_req

    async def apply_changes_and_test(self, task: EngineeringTask) -> EngineeringTask:
        """Apply the approved code changes on an isolated Git branch and execute tests."""
        task.status = TaskStatus.APPROVED
        task.log_event("APPROVED", "human_operator")

        task.status = TaskStatus.EXECUTING
        task.log_event("EXECUTING", "lead-engineer")

        # 1. Create or switch to isolated Git branch
        branch_name = f"fix/{task.id.lower()}"
        task.branch_name = branch_name
        try:
            self.repo_tools.git_create_branch(branch_name, approved=True)
            task.log_event("GIT_BRANCH", "lead-engineer", {"branch": branch_name})
        except Exception as e:
            logger.warning("Could not switch git branch (continuing): %s", e)

        # 2. Apply proposed file writes
        for change in task.proposed_changes:
            try:
                orig = self.repo_tools.read_file(change.file_path)
            except Exception:
                orig = ""
            change.original_content = orig

            # Write file
            self.repo_tools.write_file(change.file_path, change.new_content, approved=True)

            # Compute diff
            change.diff = self.repo_tools.compute_diff(orig, change.new_content, change.file_path)

        # 3. Run automated tests
        task.status = TaskStatus.TESTING
        task.log_event("TESTING", "lead-engineer")

        test_result = self.test_runner.run_tests(task_id=task.id)
        task.test_results = test_result

        logger.info("Tests completed for %s: passed=%s", task.id, test_result.passed)
        task.log_event("TESTS_COMPLETED", "test_runner", {
            "passed": test_result.passed,
            "summary": test_result.summary
        })

        task.status = TaskStatus.IN_REVIEW
        return task
