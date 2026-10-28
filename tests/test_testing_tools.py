"""Tests for automated test runner."""

from pathlib import Path
from engineering_team.permissions import PermissionsManager
from engineering_team.tools.testing import TestRunner


def test_test_runner_mock(test_runner: TestRunner):
    """Test mock test runner returns structured TestResult."""
    result = test_runner.run_tests(task_id="TASK-MOCK")
    assert result.passed is True
    assert result.exit_code == 0
    assert "passed" in result.summary


def test_test_runner_real_execution(temp_repo: Path, permissions: PermissionsManager):
    """Test real pytest execution against the temporary project."""
    runner = TestRunner(temp_repo, permissions)
    runner.mock_mode = False

    result = runner.run_tests(task_id="TASK-REAL", test_path="tests/test_app.py")
    assert result.passed is True
    assert result.exit_code == 0
    assert result.duration_seconds >= 0.0


def test_test_runner_detects_failure(temp_repo: Path, permissions: PermissionsManager):
    """Test real pytest execution properly captures test failures."""
    # Write a failing test
    (temp_repo / "tests" / "test_fail.py").write_text("def test_fail():\n    assert 1 == 2\n")

    runner = TestRunner(temp_repo, permissions)
    runner.mock_mode = False

    result = runner.run_tests(task_id="TASK-FAIL", test_path="tests/test_fail.py")
    assert result.passed is False
    assert result.exit_code != 0
