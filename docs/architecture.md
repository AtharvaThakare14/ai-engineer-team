# Architecture: AI Engineering Team

Built for the **Flip the Switch Hackathon** (Switch AI × WeMakeDevs).

---

## 1. Executive Overview

The **AI Engineering Team** is an autonomous yet safely governed multi-agent engineering workflow that enables developers to collaborate directly with AI agents in **Mattermost** using the **Switch AI** agent infrastructure.

The system is designed with:
- **Genuine Switch Protocol Compliance**: Speaks the wire contract over WebSocket and REST.
- **Role Specialization**: Divides labor between an **Issue Triager**, a **Lead Software Engineer**, and a **Senior Code Reviewer**.
- **Defense in Depth**: Enforces directory sandboxing (preventing path traversal), isolated Git branches, and mandatory human approval gates before file modification.
- **Full Observability**: Comprehensive audit logs and real-time status reporting back to chat channels.

---

## 2. System Architecture Diagram

```
                              ┌────────────────────────┐
                              │ Human Developer        │
                              │ (Mattermost Channel)   │
                              └───────────┬────────────┘
                                          │
                                          │ 1. Posts engineering request (@engineer-bot)
                                          ▼
                              ┌────────────────────────┐
                              │ Mattermost Server      │
                              │ (Channels & Bot Accts) │
                              └───────────┬────────────┘
                                          │
                                          │ 2. Collaboration Bridge
                                          ▼
                              ┌────────────────────────┐
                              │ Switch Server / Rooms  │
                              │ (Port 8000 / Bridge)   │
                              └───────────┬────────────┘
                                          │
                                          │ 3. WebSocket (/connection/ws)
                                          │    + Bearer Auth & Connection ID
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SwitchClient                                                                │
│ - Validates Bearer token & maintains persistent Connection ID               │
│ - Heartbeat Liveness: Answers 'ping' frames with 'pong' carrying cursor     │
│ - Message Deduplication: Tracks seen message IDs                            │
│ - Addressed Event Filter: Only processes messages when addressed == True    │
│ - Outbound Dispatcher: POST /agents/{agent_id}/message and /ops             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ 4. Dispatches SwitchEvent
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ EngineeringWorkflow (State Machine & Multi-Agent Orchestrator)              │
│ State Flow:                                                                 │
│ CREATED ──► TRIAGED ──► ANALYZING ──► AWAITING_APPROVAL ──► APPROVED        │
│                                              │                              │
│                                              ▼ (Rejection)                  │
│ EXECUTING ◄────────────────────────────── REJECTED                          │
│     │                                                                       │
│     ▼                                                                       │
│  TESTING ──► IN_REVIEW ──► COMPLETED (or FAILED if review/tests fail)       │
└──────┬───────────────────────┬────────────────────────┬─────────────────────┘
       │                       │                        │
       ▼                       ▼                        ▼
┌───────────────┐      ┌───────────────┐        ┌───────────────┐
│ IssueTriager  │      │ EngineerAgent │        │ CodeReviewer  │
│ - Classifies  │      │ - Code inspect│        │ - Diff checks │
│   Bug/Feature │      │ - Formulates  │        │ - Regressions │
│ - Acceptance  │      │   fix plan    │        │ - Secret scan │
│   criteria    │      │ - Requests    │        │ - Acceptance  │
│ - File targets│      │   approval    │        │   signoff     │
└──────┬────────┘      └───────┬───────┘        └───────┬───────┘
       │                       │                        │
       └───────────────────────┼────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Permissions & Safety Sandbox Layer                                          │
│ - PermissionsManager: Validates all paths strictly within approved roots    │
│   (Blocks path traversal: '../', symlink escapes, absolute forbidden roots) │
│ - Human Approval Gate: Blocks file modifications until human explicitly     │
│   signs off via Mattermost button or '!approve <request_id>' command        │
│ - Audit Logger: Writes append-only immutable JSONL audit trail (audit.log)  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Tools & Execution Engine                                                    │
│ - RepoTools: Safe read, write, grep search, diff generation, git branches   │
│ - TestRunner: Executes pytest with strict timeouts and output capture       │
│ - Isolated Git Worktrees / Branches: 'fix/<task-id>'                        │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ AntigravityAdapter Interface Boundary                                       │
│ - Standardized async contract: execute_task, cancel_task, check_health      │
│ - Documented Limitation: IDE assistant active, external CLI daemon pending  │
│ - Autonomous Engine Fallback: Guarantees end-to-end execution & tests       │
│ - Interactive Prompt Exporter: Formats exact context for VS Code assistant  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Switch Wire Protocol Implementation

Our `SwitchClient` adheres directly to the documented protocol:

1. **Agent Registration (`POST /agents`)**:
   - Authenticates using `AGENT_REGISTRATION_TOKEN`.
   - Sends `SwitchRegistrationRequest` containing `name`, `description`, and `integration_profile` with `connection_model: always_on` and `message_exchange: true`.
   - Stores the generated unique agent ID and API key.

2. **WebSocket Transport (`/agents/{agent_id}/connection/ws`)**:
   - Opens persistent WebSocket connection.
   - Transmits `Authorization: Bearer <agent_api_key>` and `X-Switch-Connection-Id: <connection_id>`.
   - Captures `connection_state` frame to seed initial `cursor`, `generation`, and `claimed_rooms`.

3. **Liveness & Heartbeats**:
   - Whenever the Switch server emits a `{"type": "ping"}` frame, `SwitchClient` immediately responds with `{"type": "pong", "cursor": <current_cursor>}`.

4. **Addressing & Message Deduplication**:
   - Switch delivers all room traffic to subscribed agents.
   - `SwitchClient` checks `payload.addressed == True` to filter out background chatter and only process requests explicitly targeted at the agent.
   - Maintains an in-memory set of processed `message_id`s to prevent duplicate execution during network reconnections.

5. **REST Operations & Messaging**:
   - Messages are posted via `POST /agents/{agent_id}/message` with `{room_id, content}`.
   - Switch operations (e.g. `update_agent_detail`, `list_rooms`) are invoked via `POST /agents/{agent_id}/ops/{operation}` with the `X-Switch-Connection-Id` header.

---

## 4. Antigravity Integration Boundary & Limitations

### Verified Environment Findings:
- Antigravity is installed and active in the developer's VS Code IDE.
- There is no background command-line daemon (`agy`) exposed in the Windows system `PATH`.
- The `google.antigravity` Python package is not pre-installed on the system.

### Integration Architecture:
In accordance with Section 4 of the hackathon requirements:
1. We **do not fabricate** fake CLI calls or simulated binaries.
2. We implement a formal `AntigravityAdapter` exposing:
   - `execute_task(task, file_contents)`
   - `cancel_task(task_id)`
   - `check_health()`
3. In `check_health()`, the adapter clearly reports `"status": "fallback_mode"` and explicitly details the environmental limitation.
4. The adapter provides an **Autonomous Engine Fallback** that parses requirements, applies appropriate modifications, and formats a **Manual Fallback Prompt** which human operators can paste into VS Code Antigravity at any time.

---

## 5. Security & Safety Model

1. **Path Whitelisting**:
   Every file operation is passed through `PermissionsManager.validate_path()`. If a path contains traversal components (`..`) that resolve outside `ALLOWED_REPO_PATHS`, execution is immediately halted with a `PermissionDeniedError` and logged to `audit.log`.

2. **Human Approval Gates**:
   Before modifying any file on disk or creating a branch, `EngineerAgent` creates a pending `ApprovalRequest`. The workflow pauses in `AWAITING_APPROVAL` until a human operator sends `!approve <id>` in Mattermost or clicks the interactive Mattermost card button.

3. **Branch Isolation**:
   All changes are committed onto dedicated Git branches named `fix/<task-id>`, leaving `main` and active development branches untouched.

4. **No Arbitrary Shell Execution**:
   Commands are not executed from raw user chat strings. Only pre-defined, sandboxed operations (such as `python -m pytest` with configurable timeouts) are permitted.
