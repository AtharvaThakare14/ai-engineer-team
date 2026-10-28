# AI Engineering Team 🚀
### Flip the Switch Hackathon Project (Switch AI × WeMakeDevs)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-27%20passed-brightgreen.svg)](tests/)
[![Switch AI Protocol](https://img.shields.io/badge/switch-official%20protocol-orange.svg)](https://docs.switchagents.ai/)
[![Chat Platform](https://img.shields.io/badge/chat-Mattermost-0058CC.svg)](https://mattermost.com/)
[![IDE](https://img.shields.io/badge/IDE-VS%20Code-007ACC.svg)](https://code.visualstudio.com/)

---

## 💡 Overview

**AI Engineering Team** is an autonomous, safely-governed multi-agent engineering workflow that enables human developers to assign software engineering tasks directly from **Mattermost** using **Switch AI Rooms**.

Developers no longer need to manually context-switch between issue trackers, terminal windows, code reviews, and test runners. Instead, they interact with specialized AI agents who investigate bugs, plan solutions, request explicit human approval before modifying code, execute changes on isolated Git branches, run automated tests, and provide rigorous code reviews.

---

## 🌟 Key Features

1. **Genuine Switch Agent Protocol Compliance**:
   - WebSocket transport (`/agents/{agent_id}/connection/ws`) with Bearer token authentication and unique connection IDs.
   - Active heartbeat management: Responds to server `ping` frames with `pong` carrying cursors.
   - REST operations dispatcher (`/agents/{agent_id}/ops/{operation}`) and room messaging (`/agents/{agent_id}/message`).
   - Addressing filter: Enforces `payload.addressed == True` to ignore unrelated room traffic.
   - Message deduplication to avoid duplicate work on network reconnects.

2. **Mattermost Collaboration**:
   - Each agent operates under its own bot account.
   - Rich card formatting with real-time status badges (`TRIAGED`, `AWAITING APPROVAL`, `COMPLETED`).
   - Interactive buttons (`[Approve Change]`, `[Reject]`) and direct chat commands (`!approve <req_id>`).

3. **Specialized Multi-Agent Division of Labor**:
   - **Issue Triager Agent**: Classifies incoming requests (Bug, Feature, Exploration), extracts acceptance criteria, and identifies target repository files.
   - **Lead Software Engineer Agent**: Analyzes code, formulates fix plan, submits human approval request, branches code, implements edits, and executes tests.
   - **Senior Code Reviewer Agent**: Evaluates git diffs against acceptance criteria, flags regressions, scans for hardcoded secrets, and reports findings.

4. **Safety, Sandboxing & Human Approval**:
   - **Strict Path Whitelisting**: Blocks path traversal attacks (`../`, symlinks) outside approved repository roots.
   - **Human Approval Gate**: Blocks disk modifications until a developer explicitly signs off.
   - **Isolated Git Branches**: Code changes are made on dedicated `fix/<task-id>` branches.
   - **Immutable Audit Logging**: Every critical action and decision is logged to `audit.log`.

5. **Antigravity Adapter Boundary**:
   - Clean async adapter interface (`AntigravityAdapter`) adhering to programmatic execution contracts.
   - Clearly documents the current environment status (IDE assistant active; external CLI daemon pending).
   - Provides a resilient autonomous fallback and interactive prompt exporter for seamless operation.

---

## 🏗️ Architecture

```
Developer (Mattermost)
    ↓
Mattermost Chat Room / Bot Accounts
    ↓
Switch Collaboration Bridge (Port 8000)
    ↓
SwitchClient (WebSocket Wire Protocol, Heartbeats & Deduplication)
    ↓
EngineeringWorkflow (State Machine & Permissions Gate)
    ↓
Issue Triager ──► Lead Engineer (Git Branch & Pytest) ──► Code Reviewer
    ↓
Human Approval Gate (Required for all writes)
    ↓
Results & Test Reports Posted to Mattermost
```

Detailed architecture diagrams and wire protocol specifications are available in [docs/architecture.md](docs/architecture.md).

---

## 🚀 Quickstart (Windows 11 & VS Code)

### 1. Prerequisites
- Python 3.10+
- Git for Windows
- VS Code
- Docker Desktop (optional for standalone Switch/Mattermost container stack)

### 2. Installation
```powershell
# Clone and enter directory
cd ai-engineering-team

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install package with dependencies
pip install -e .[dev]
```

### 3. Environment Configuration
```powershell
Copy-Item .env.example .env
```
Set your Switch Server and Mattermost configuration values in `.env`.

### 4. Run Application
```powershell
python -m uvicorn engineering_team.main:app --host 0.0.0.0 --port 8082 --reload
```
Check service health:
- Liveness: `http://localhost:8082/health`
- Readiness: `http://localhost:8082/ready`
- Task Dashboard: `http://localhost:8082/api/tasks`

---

## 🧪 Testing

The repository contains an automated test suite with **27 passing tests** covering every layer:

```powershell
python -m pytest -v
```

### Test Coverage Highlights:
- **`tests/test_permissions.py`**: Directory traversal blocking, path whitelisting, approval lifecycle, and audit logs.
- **`tests/test_repository.py`**: Safe read, write permissions check, directory walk, code grep, and diff calculation.
- **`tests/test_testing_tools.py`**: Subprocess pytest runner, exit code parsing, and failure capture.
- **`tests/test_switch_protocol.py`**: Registration wire model, WebSocket event parsing, ping/pong cursor tracking, addressing filters, and message deduplication.
- **`tests/test_workflow.py`**: Complete end-to-end multi-agent workflow (Triage → Approval → Execution → Test → Review → Completion).
- **`tests/test_integrations.py`**: Mattermost card rendering, approval buttons, Antigravity adapter health, and FastAPI REST endpoints.

---

## 📚 Documentation Index

- [Architecture & Protocol Wire Contract](docs/architecture.md)
- [Windows 11 & VS Code Setup Guide](docs/setup_windows.md)
- [Live Demo & Video Recording Script](docs/demo_script.md)

---

## 📄 License

MIT License. Built for the WeMakeDevs & Switch AI Flip the Switch Hackathon.
