"""Repository exploration and modification tools with strict security sandboxing."""

import difflib
import logging
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

from engineering_team.permissions import PermissionsManager, PermissionDeniedError

logger = logging.getLogger(__name__)


class RepoTools:
    def __init__(self, repo_root: Path, permissions_manager: PermissionsManager):
        self.repo_root = repo_root.resolve()
        self.permissions = permissions_manager

    def read_file(self, relative_path: str) -> str:
        """Safely read a file within the approved repository root."""
        full_path = self.repo_root / relative_path
        validated_path = self.permissions.validate_path(full_path)

        if not validated_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        if not validated_path.is_file():
            raise IsADirectoryError(f"Target is a directory, not a file: {relative_path}")

        return validated_path.read_text(encoding="utf-8", errors="replace")

    def write_file(self, relative_path: str, content: str, approved: bool = False) -> str:
        """Safely write/modify a file within the approved repository root."""
        full_path = self.repo_root / relative_path
        validated_path = self.permissions.validate_path(full_path)

        if self.permissions.requires_approval("MODIFY_FILE") and not approved:
            raise PermissionDeniedError(
                f"Modifying '{relative_path}' requires explicit human approval."
            )

        validated_path.parent.mkdir(parents=True, exist_ok=True)
        validated_path.write_text(content, encoding="utf-8")
        self.permissions.log_audit(
            "WRITE_FILE",
            "engineer_tool",
            {"file": relative_path, "bytes": len(content)}
        )
        logger.info("Successfully wrote file: %s", relative_path)
        return f"File updated: {relative_path}"

    def list_files(self, sub_dir: str = "", max_depth: int = 4) -> List[str]:
        """List files in the repository, excluding git and cache directories."""
        target_dir = self.permissions.validate_path(self.repo_root / sub_dir)
        ignored = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".eggs", "egg-info"}

        file_list: List[str] = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignored and not d.endswith(".egg-info")]
            rel_root = Path(root).relative_to(self.repo_root)
            if len(rel_root.parts) > max_depth:
                continue
            for file in files:
                rel_file = rel_root / file
                file_list.append(str(rel_file).replace("\\", "/"))

        return sorted(file_list)

    def search_code(self, query: str, sub_dir: str = "") -> List[Dict[str, Any]]:
        """Grep for text across repository files safely."""
        target_dir = self.permissions.validate_path(self.repo_root / sub_dir)
        results: List[Dict[str, Any]] = []

        for rel_file in self.list_files(sub_dir):
            full_path = self.repo_root / rel_file
            try:
                lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                for idx, line in enumerate(lines, 1):
                    if query.lower() in line.lower():
                        results.append({
                            "file": rel_file,
                            "line": idx,
                            "content": line.strip()
                        })
                        if len(results) >= 50:
                            return results
            except Exception:
                continue

        return results

    def compute_diff(self, original_text: str, new_text: str, file_name: str = "file") -> str:
        """Generate a unified diff between two versions of a file."""
        orig_lines = original_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{file_name}",
            tofile=f"b/{file_name}"
        )
        return "".join(diff)

    def git_create_branch(self, branch_name: str, approved: bool = False) -> str:
        """Create and switch to an isolated Git branch."""
        if self.permissions.requires_approval("GIT_BRANCH") and not approved:
            raise PermissionDeniedError(
                f"Creating Git branch '{branch_name}' requires human approval."
            )

        cmd = ["git", "checkout", "-b", branch_name]
        res = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            # Maybe already exists, try checkout
            checkout_res = subprocess.run(
                ["git", "checkout", branch_name],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False
            )
            if checkout_res.returncode != 0:
                raise RuntimeError(f"Git branch creation failed: {res.stderr or checkout_res.stderr}")

        self.permissions.log_audit("GIT_BRANCH_CREATED", "git_tool", {"branch": branch_name})
        return f"Switched to branch: {branch_name}"

    def git_status(self) -> str:
        """Get git status output."""
        res = subprocess.run(["git", "status", "--short"], cwd=self.repo_root, capture_output=True, text=True, check=False)
        return res.stdout.strip()

    def git_diff(self) -> str:
        """Get git diff of uncommitted changes."""
        res = subprocess.run(["git", "diff"], cwd=self.repo_root, capture_output=True, text=True, check=False)
        return res.stdout.strip()
