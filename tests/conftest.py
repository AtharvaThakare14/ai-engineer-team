"""Pytest fixtures for AI Engineering Team test suite."""

import sys
from pathlib import Path
import pytest

# Ensure src/ is on sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from engineering_team.agents.engineer import EngineerAgent
from engineering_team.agents.reviewer import CodeReviewer
from engineering_team.agents.triager import IssueTriager
from engineering_team.config import Settings
from engineering_team.integrations.antigravity_adapter import AntigravityAdapter
from engineering_team.integrations.mattermost import MattermostClient
from engineering_team.integrations.switch_client import SwitchClient
from engineering_team.permissions import PermissionsManager
from engineering_team.tools.repository import RepoTools
from engineering_team.tools.testing import TestRunner
from engineering_team.workflow import EngineeringWorkflow


@pytest.fixture
def temp_repo(tmp_path: Path):
    """Create a temporary repository directory with dummy code and test files."""
    repo = tmp_path / "mock_project"
    repo.mkdir()

    # Create dummy app.py
    (repo / "app.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    return a / b\n",
        encoding="utf-8"
    )

    # Create tests/test_app.py
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text(
        "from app import add, divide\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n\n"
        "def test_divide():\n    assert divide(4, 2) == 2\n",
        encoding="utf-8"
    )

    return repo


@pytest.fixture
def settings(temp_repo: Path, tmp_path: Path):
    """Instantiate test Settings pointing to the temporary repo."""
    return Settings(
        switch_server_url="http://localhost:8000",
        switch_api_key="mock_key",
        switch_agent_id="mock_agent_id",
        switch_registration_token="mock_bootstrap_token",
        switch_default_room_id="test_room",
        target_repo_path=temp_repo,
        allowed_repo_paths=[temp_repo, tmp_path],
        human_approval_required=True,
        auto_run_tests=True
    )


@pytest.fixture
def permissions(settings: Settings, tmp_path: Path):
    """Instantiate PermissionsManager with an isolated audit log."""
    audit_file = tmp_path / "test_audit.log"
    return PermissionsManager(settings, audit_log_path=audit_file)


@pytest.fixture
def repo_tools(temp_repo: Path, permissions: PermissionsManager):
    """Instantiate RepoTools for the test repository."""
    return RepoTools(temp_repo, permissions)


@pytest.fixture
def test_runner(temp_repo: Path, permissions: PermissionsManager):
    """Instantiate TestRunner with mock mode enabled by default for speed."""
    runner = TestRunner(temp_repo, permissions)
    runner.mock_mode = True
    return runner


@pytest.fixture
def antigravity_adapter():
    """Instantiate AntigravityAdapter."""
    return AntigravityAdapter()


@pytest.fixture
def switch_client(settings: Settings):
    """Instantiate SwitchClient in mock mode."""
    client = SwitchClient(settings)
    client.mock_mode = True
    return client


@pytest.fixture
def mattermost_client(settings: Settings):
    """Instantiate MattermostClient in mock mode."""
    client = MattermostClient(settings)
    client.mock_mode = True
    return client


@pytest.fixture
def workflow(
    settings: Settings,
    repo_tools: RepoTools,
    test_runner: TestRunner,
    permissions: PermissionsManager,
    antigravity_adapter: AntigravityAdapter,
    switch_client: SwitchClient,
    mattermost_client: MattermostClient
):
    """Instantiate full EngineeringWorkflow."""
    triager = IssueTriager(repo_tools)
    engineer = EngineerAgent(repo_tools, test_runner, permissions, antigravity_adapter)
    reviewer = CodeReviewer()

    return EngineeringWorkflow(
        settings=settings,
        triager=triager,
        engineer=engineer,
        reviewer=reviewer,
        permissions=permissions,
        switch_client=switch_client,
        mattermost_client=mattermost_client
    )
