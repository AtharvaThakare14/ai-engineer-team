"""Interactive Live Demo Script for AI Engineering Team.

Run this script to test the complete multi-agent workflow directly in your terminal:
    python run_demo.py
"""

import asyncio
import sys
from pathlib import Path

# Enable UTF-8 console output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add src to path
src_dir = Path(__file__).resolve().parent / "src"
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


async def main():
    print("=" * 70)
    print("🚀 AI Engineering Team — Live Interactive Demonstration")
    print("   Flip the Switch Hackathon (Switch AI × Mattermost)")
    print("=" * 70)
    print()

    # 1. Initialize configuration pointing to sample_repo
    base_dir = Path(__file__).resolve().parent
    sample_repo = base_dir / "sample_repo"

    settings = Settings(
        target_repo_path=sample_repo,
        allowed_repo_paths=[sample_repo, base_dir],
        human_approval_required=True,
        auto_run_tests=True
    )

    permissions = PermissionsManager(settings, audit_log_path=base_dir / "audit.log")
    repo_tools = RepoTools(sample_repo, permissions)
    test_runner = TestRunner(sample_repo, permissions)
    antigravity = AntigravityAdapter()

    switch_client = SwitchClient(settings)
    switch_client.mock_mode = True  # Local live simulation
    mattermost = MattermostClient(settings)
    mattermost.mock_mode = True

    triager = IssueTriager(repo_tools)
    engineer = EngineerAgent(repo_tools, test_runner, permissions, antigravity)
    reviewer = CodeReviewer()

    workflow = EngineeringWorkflow(
        settings=settings,
        triager=triager,
        engineer=engineer,
        reviewer=reviewer,
        permissions=permissions,
        switch_client=switch_client,
        mattermost_client=mattermost
    )

    # 2. Simulate developer submitting request
    print("💬 [Developer in Mattermost #engineering]:")
    prompt = "@lead-engineer Fix unhandled division by zero in calculator.py so it raises ValueError when denominator is 0"
    print(f"   \"{prompt}\"\n")
    await asyncio.sleep(1)

    # 3. Issue Triager classifies and prepares task
    print("🤖 [Step 1: Issue Triager Agent]")
    task = await workflow.handle_user_request(prompt, user_id="developer_alice", room_id="room_engineering")
    print(f"   Status:       {task.status.value}")
    print(f"   Task ID:      {task.id}")
    print(f"   Task Type:    {task.task_type.value}")
    print(f"   Title:        {task.title}")
    print(f"   Target Files: {task.target_files}")
    print("   Acceptance Criteria:")
    for ac in task.acceptance_criteria:
        print(f"     - {ac}")
    print()
    await asyncio.sleep(1)

    # 4. Human Approval Gate
    approval_req = task.approvals[0]
    print("🛡️ [Step 2: Human Approval Gate]")
    print(f"   Approval Request ID: {approval_req.request_id}")
    print(f"   Action Type:         {approval_req.action_type}")
    print(f"   Description:         {approval_req.description}")
    print()

    # Prompt user or auto-approve
    print("   👉 Simulating developer approval ('!approve' or clicking [Approve Change] in Mattermost)...")
    await asyncio.sleep(1)
    print("   ✅ Developer approved the modification!")
    print()

    # 5. Lead Engineer applies changes and runs tests
    print("⚙️ [Step 3: Lead Software Engineer]")
    print("   - Applying approved changes...")
    print("   - Running automated test suite (pytest)...")
    completed_task = await workflow.process_approval_decision(
        request_id=approval_req.request_id,
        approved=True,
        decided_by="developer_alice"
    )
    print(f"   Test Result:  {'✅ PASSED' if completed_task.test_results.passed else '❌ FAILED'}")
    print(f"   Test Summary: {completed_task.test_results.summary}")
    print()
    await asyncio.sleep(1)

    # 6. Senior Code Reviewer evaluates results
    print("👀 [Step 4: Senior Code Reviewer]")
    review = completed_task.review_result
    print(f"   Review Approved: {'✅ YES' if review.approved else '❌ NO'}")
    print(f"   Review Comments: {review.comments}")
    print(f"   Findings:        {len(review.findings)} issues flagged")
    print()

    # 7. Final Result Card Posted to Mattermost
    print("📢 [Step 5: Final Result Card Posted to Mattermost]")
    card = mattermost.format_task_card(completed_task)
    print("-" * 50)
    print(card)
    print("-" * 50)
    print()
    print("🎉 Workflow completed successfully! All audit logs written to audit.log.")


if __name__ == "__main__":
    asyncio.run(main())
