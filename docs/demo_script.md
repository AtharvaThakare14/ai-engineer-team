# AI Engineering Team: Live Demo & Video Recording Script

This script walks through a complete, reproducible software engineering scenario demonstrating the **AI Engineering Team** in action through Mattermost and Switch.

---

## 1. Demo Scenario Overview

- **Context**: A developer reports an unhandled division-by-zero bug in the project's math utility module (`sample_repo/calculator.py`).
- **Channel**: Mattermost `~engineering` channel bridged by Switch.
- **Participating Roles**:
  - **Human Developer**: Reports issue and approves code modifications.
  - **Issue Triager Agent**: Parses problem, identifies target files, and formalizes acceptance criteria.
  - **Lead Software Engineer Agent**: Formulates solution, creates isolated Git branch, requests human approval, applies code edits, and runs automated tests.
  - **Senior Code Reviewer Agent**: Evaluates diffs, checks regression risks, validates acceptance criteria, and issues final sign-off.

---

## 2. Step-by-Step Walkthrough

### Step 1: Start Services & Verification
Open PowerShell in VS Code:
```powershell
cd ai-engineering-team
python -m uvicorn engineering_team.main:app --host 0.0.0.0 --port 8082
```
*Verification Check*: Open `http://localhost:8082/ready` in a browser. It returns:
```json
{
  "status": "ready",
  "antigravity": {
    "name": "AntigravityAdapter",
    "cli_available": false,
    "status": "fallback_mode",
    "limitation_documented": "Antigravity is active as the IDE assistant in VS Code..."
  },
  "switch": {
    "server": "http://localhost:8000",
    "connection_id": "..."
  }
}
```

---

### Step 2: Developer Assigns Bug in Mattermost
In the Mattermost `~engineering` channel, the developer tags the agent:

> **Developer:**
> `@lead-engineer Fix unhandled division by zero error in calculator.py so it raises ValueError when denominator is zero.`

---

### Step 3: Issue Triager Responds Automatically
Within seconds, the Issue Triager classifies the task and posts a structured card:

> **Issue Triager (`issue-triager`):**
> 📋 `TRIAGED` Task: **Fix: unhandled division by zero error in calculator.py** (`TASK-7B9A2F`)
> **Type:** `BUG` | **Assigned To:** `lead-engineer`
>
> **Acceptance Criteria:**
> - [ ] Denominator zero raises `ValueError("Cannot divide by zero")`
> - [ ] Existing test cases in `sample_repo/tests/test_calculator.py` continue to pass
> - [ ] No regressions or unexpected side effects
>
> **Target Files:** `calculator.py`, `tests/test_calculator.py`

---

### Step 4: Lead Engineer Inspects Code & Requests Human Approval
The Lead Engineer analyzes `calculator.py`, plans the fix on an isolated Git branch, and posts the approval request:

> **Lead Software Engineer (`lead-engineer`):**
> ### 🛡️ **Human Approval Required**
> **Task ID:** `TASK-7B9A2F` | **Action:** `MODIFY_FILE`
>
> Proposed modification for 1 file(s): `calculator.py`
> - Guard `divide(a, b)` with `if b == 0: raise ValueError(...)`
> - Branch: `fix/task-7b9a2f`
>
> **Options:**
> - Click button: **[Approve Change]**
> - Or reply in chat: `!approve <approval_request_id>`

---

### Step 5: Human Approves Modification
The developer approves the action:

> **Developer:**
> `!approve <approval_request_id>`
> *(Or clicks the **[Approve Change]** interactive card button)*

---

### Step 6: Engineer Implements Fix on Branch & Runs Pytest
The Lead Engineer immediately executes the approved changes:

> **Lead Software Engineer (`lead-engineer`):**
> ⚙️ **Approval received!**
> - Switched to isolated Git branch `fix/task-7b9a2f`
> - Applied file modification to `calculator.py`
> - Executing test suite `pytest sample_repo/tests/`...
>
> 🧪 **Test Results (✅ Passed):**
> ```text
> 5 passed in 0.02s
> ```

---

### Step 7: Senior Code Reviewer Signs Off
The Code Reviewer inspects the unified git diff:

> **Senior Code Reviewer (`code-reviewer`):**
> ### 🎉 `COMPLETED` Task: **Fix: unhandled division by zero error in calculator.py** (`TASK-7B9A2F`)
> **Type:** `BUG` | **Assigned To:** `lead-engineer`
> **Branch:** `fix/task-7b9a2f`
>
> **Acceptance Criteria:**
> - [x] Denominator zero raises `ValueError("Cannot divide by zero")`
> - [x] Existing test cases continue to pass
> - [x] No regressions or security risks
>
> **Code Review (✅ Approved):**
> All acceptance criteria verified. Code changes are clean, tests passed, and no regressions found.
> Branch `fix/task-7b9a2f` is ready for PR merge!

---

## 3. Video Recording Checklist

When recording the demo for hackathon submission:

- [ ] **Introduction (0:00 - 0:30)**: State project name (*AI Engineering Team*), technology stack (Switch AI, Mattermost, Python, VS Code, Antigravity, Pytest), and problem statement.
- [ ] **Architecture Overview (0:30 - 1:00)**: Show the architecture diagram from `docs/architecture.md`, highlighting the Switch WebSocket protocol, permissions gate, and role division.
- [ ] **Live Demo Trigger (1:00 - 2:00)**: Post the bug fix prompt in Mattermost, show the automatic triage card and the human approval prompt.
- [ ] **Approval & Execution (2:00 - 3:00)**: Show the human approval in action, the Git branch creation, the code modification, and the green test results.
- [ ] **Code Review & Audit Log (3:00 - 3:30)**: Show the Code Reviewer's signoff and the immutable `audit.log` entries on disk.
- [ ] **Automated Test Suite (3:30 - 4:00)**: Run `python -m pytest -v` in terminal showing all 27 tests passing.
