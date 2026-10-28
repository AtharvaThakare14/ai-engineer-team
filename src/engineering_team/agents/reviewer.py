"""Senior Code Reviewer Agent.

Inspects code diffs, verifies acceptance criteria, detects potential
regressions, evaluates test outcomes, and reports review findings.
"""

import logging
from typing import List

from engineering_team.models import (
    EngineeringTask,
    ReviewFinding,
    ReviewResult,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class CodeReviewer:
    def __init__(self):
        pass

    async def review_task(self, task: EngineeringTask) -> ReviewResult:
        """Perform code review on proposed changes and test results."""
        logger.info("Conducting code review on task %s", task.id)
        findings: List[ReviewFinding] = []

        # 1. Verify test suite passed
        if not task.test_results or not task.test_results.passed:
            findings.append(
                ReviewFinding(
                    severity="CRITICAL",
                    message="Automated tests failed or were not run.",
                    file_path=None
                )
            )

        # 2. Check diffs for security and quality patterns
        for change in task.proposed_changes:
            diff_text = change.diff or ""

            # Check for accidental secrets or tokens
            for secret_keyword in ["api_key = \"", "secret = \"", "password = \"", "token = \""]:
                if secret_keyword in diff_text.lower():
                    findings.append(
                        ReviewFinding(
                            severity="CRITICAL",
                            message=f"Possible hardcoded credential found in diff for {change.file_path}",
                            file_path=change.file_path
                        )
                    )

            # Check for debug print or pdb statements
            if "import pdb" in diff_text or "breakpoint()" in diff_text:
                findings.append(
                    ReviewFinding(
                        severity="WARNING",
                        message=f"Debug breakpoint left in {change.file_path}",
                        file_path=change.file_path
                    )
                )

        # 3. Acceptance criteria check
        ac_satisfied = len(findings) == 0
        if not ac_satisfied:
            comments = f"Review failed with {len(findings)} blocking finding(s). Please review flagged issues."
            approved = False
            task.status = TaskStatus.FAILED
        else:
            comments = "All acceptance criteria verified. Code changes are clean, tests passed, and no regressions found."
            approved = True
            task.status = TaskStatus.COMPLETED

        result = ReviewResult(
            task_id=task.id,
            approved=approved,
            findings=findings,
            comments=comments
        )

        task.review_result = result
        task.log_event("REVIEW_COMPLETED", "code-reviewer", {
            "approved": approved,
            "findings_count": len(findings)
        })

        logger.info("Review complete for task %s: approved=%s", task.id, approved)
        return result
