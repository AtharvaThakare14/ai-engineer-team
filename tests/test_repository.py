"""Tests for repository tools."""

import pytest
from engineering_team.permissions import PermissionDeniedError
from engineering_team.tools.repository import RepoTools


def test_read_file(repo_tools: RepoTools):
    """Test reading existing file."""
    content = repo_tools.read_file("app.py")
    assert "def add(a, b):" in content


def test_read_missing_file_raises(repo_tools: RepoTools):
    """Test reading nonexistent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        repo_tools.read_file("nonexistent.py")


def test_write_file_without_approval_raises(repo_tools: RepoTools):
    """Test that modifying a file without approved=True raises PermissionDeniedError."""
    with pytest.raises(PermissionDeniedError):
        repo_tools.write_file("app.py", "# New code", approved=False)


def test_write_file_with_approval_succeeds(repo_tools: RepoTools):
    """Test writing a file when approved=True."""
    res = repo_tools.write_file("app.py", "def add(a, b):\n    return a + b + 0\n", approved=True)
    assert "updated" in res.lower()
    updated = repo_tools.read_file("app.py")
    assert "a + b + 0" in updated


def test_list_files(repo_tools: RepoTools):
    """Test recursive listing of repository files."""
    files = repo_tools.list_files()
    assert "app.py" in files
    assert "tests/test_app.py" in files


def test_search_code(repo_tools: RepoTools):
    """Test grepping for functions in repository."""
    matches = repo_tools.search_code("def divide")
    assert len(matches) > 0
    assert matches[0]["file"] in ["app.py", "tests/test_app.py"]
    assert "divide" in matches[0]["content"]


def test_compute_diff(repo_tools: RepoTools):
    """Test unified diff calculation."""
    orig = "line 1\nline 2\n"
    new = "line 1\nline 2 edited\n"
    diff = repo_tools.compute_diff(orig, new, "test.txt")
    assert "--- a/test.txt" in diff
    assert "+++ b/test.txt" in diff
    assert "+line 2 edited" in diff
