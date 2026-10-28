"""Automated test execution tool running pytest with timeouts and structured output."""

import logging
from pathlib import Path
import subprocess
import time
from typing import List, Optional

from engineering_team.models import TestResult
from engineering_team.permissions import PermissionsManager

logger = logging.getLogger(__name__)


class TestRunner:
    __test__ = False

    def __init__(self, repo_root: Path, permissions: PermissionsManager, default_timeout: float = 60.0):
        self.repo_root = repo_root.resolve()
        self.permissions = permissions
        self.default_timeout = default_timeout
        self.mock_mode: bool = False

    def run_tests(
        self,
        task_id: str,
        test_path: Optional[str] = None,
        filter_expr: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> TestResult:
        """Run pytest on the target repository and capture structured results."""
        if self.mock_mode:
            logger.info("[Mock TestRunner] Simulating pytest execution for task %s", task_id)
            return TestResult(
                task_id=task_id,
                passed=True,
                exit_code=0,
                stdout="==== 5 passed in 0.42s ====",
                stderr="",
                summary="5 passed, 0 failed",
                duration_seconds=0.42
            )

        cmd = ["python", "-m", "pytest"]

        if test_path:
            full_test_path = self.permissions.validate_path(self.repo_root / test_path)
            rel_test_path = str(full_test_path.relative_to(self.repo_root)).replace("\\", "/")
            cmd.append(rel_test_path)

        if filter_expr:
            cmd.extend(["-k", filter_expr])

        # Add flags for concise summary
        cmd.extend(["-q", "--no-header"])

        start_time = time.perf_counter()
        timeout_val = timeout or self.default_timeout

        logger.info("Executing tests: %s in %s", " ".join(cmd), self.repo_root)
        try:
            res = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=timeout_val,
                check=False
            )
            duration = round(time.perf_counter() - start_time, 2)
            passed = (res.returncode == 0)

            # Extract last line or summary
            stdout_lines = res.stdout.strip().splitlines()
            summary = stdout_lines[-1] if stdout_lines else ("Passed" if passed else "Failed")

            result = TestResult(
                task_id=task_id,
                passed=passed,
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                summary=summary,
                duration_seconds=duration
            )

            self.permissions.log_audit(
                "TEST_RUN_COMPLETED",
                "test_runner",
                {"task_id": task_id, "passed": passed, "exit_code": res.returncode, "duration": duration}
            )
            return result

        except subprocess.TimeoutExpired as exc:
            duration = round(time.perf_counter() - start_time, 2)
            logger.error("Tests timed out after %ds for task %s", timeout_val, task_id)
            return TestResult(
                task_id=task_id,
                passed=False,
                exit_code=-1,
                stdout=exc.stdout or "",
                stderr=f"Test run timed out after {timeout_val} seconds.",
                summary=f"Timed out ({timeout_val}s)",
                duration_seconds=duration
            )
        except Exception as e:
            duration = round(time.perf_counter() - start_time, 2)
            logger.exception("Failed to execute test command: %s", e)
            return TestResult(
                task_id=task_id,
                passed=False,
                exit_code=-2,
                stdout="",
                stderr=str(e),
                summary=f"Execution error: {str(e)}",
                duration_seconds=duration
            )
