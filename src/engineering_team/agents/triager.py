"""Issue Triager Agent.

Responsible for:
1. Classifying incoming user requests (Bug, Feature, Exploration)
2. Extracting structured acceptance criteria
3. Identifying candidate files in the repository
4. Transitioning task to TRIAGED
"""

import logging
import re
from typing import List, Optional

from engineering_team.models import EngineeringTask, TaskStatus, TaskType
from engineering_team.tools.repository import RepoTools

logger = logging.getLogger(__name__)


class IssueTriager:
    def __init__(self, repo_tools: RepoTools):
        self.repo_tools = repo_tools

    async def triage(self, raw_request: str, user_id: str = "developer", room_id: str = "default_room") -> EngineeringTask:
        """Analyze a raw text request and create a structured EngineeringTask."""
        logger.info("Triaging incoming request from %s: %s", user_id, raw_request[:80])

        lower = raw_request.lower()

        # Classify task type
        if any(w in lower for w in ["bug", "fix", "error", "broken", "issue", "crash", "fails"]):
            task_type = TaskType.BUG
            title_prefix = "Fix"
        elif any(w in lower for w in ["feature", "add", "implement", "support", "new", "enhance"]):
            task_type = TaskType.FEATURE
            title_prefix = "Feature"
        elif any(w in lower for w in ["test", "coverage", "verify"]):
            task_type = TaskType.TEST
            title_prefix = "Test"
        else:
            task_type = TaskType.EXPLORATION
            title_prefix = "Investigate"

        # Generate a concise title
        cleaned = re.sub(r"^(!fix|!bug|!task|@[\w\-]+)\s*", "", raw_request, flags=re.IGNORECASE).strip()
        first_line = cleaned.splitlines()[0] if cleaned else "Software Task"
        title = f"{title_prefix}: {first_line[:60]}"

        # Search repository for mentioned files or keywords
        target_files: List[str] = []
        all_repo_files = self.repo_tools.list_files()

        # Check for explicit file mentions in the prompt (e.g., app.py, config.py)
        for f in all_repo_files:
            base = f.split("/")[-1]
            if base.lower() in lower and base not in [".gitignore", "license"]:
                if f not in target_files:
                    target_files.append(f)

        # Formulate acceptance criteria
        acceptance_criteria: List[str] = [
            f"Address requirement: '{first_line[:80]}'",
            "Ensure existing unit tests continue to pass",
            "Verify no regressions introduced"
        ]

        task = EngineeringTask(
            title=title,
            description=cleaned,
            task_type=task_type,
            status=TaskStatus.TRIAGED,
            assigned_agent="lead-engineer",
            acceptance_criteria=acceptance_criteria,
            target_files=target_files,
            room_id=room_id,
            user_id=user_id
        )

        task.log_event("TRIAGED", "issue-triager", {
            "type": task_type.value,
            "target_files": target_files
        })

        logger.info("Task %s successfully triaged as %s with %d target files.", task.id, task_type.value, len(target_files))
        return task
