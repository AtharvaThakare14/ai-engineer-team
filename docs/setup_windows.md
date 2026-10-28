# Windows 11 & VS Code Setup Guide

This guide provides exact, verified step-by-step instructions to run and develop the **AI Engineering Team** on Windows 11 with VS Code.

---

## 1. Prerequisites Checklist

| Component | Minimum Version | Verified Path / Command |
| :--- | :--- | :--- |
| **Operating System** | Windows 10/11 x64 | Windows 11 Pro |
| **IDE** | VS Code 1.85+ | Visual Studio Code |
| **Python** | Python 3.10+ | `C:\Users\athar\AppData\Local\Programs\Python\Python311\python.exe` |
| **Git** | Git 2.40+ | `git version 2.44.0.windows.1` |
| **Docker Desktop** | Docker Desktop 4.25+ | `C:\Users\athar\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe` |

---

## 2. Python Environment & Dependency Setup

Open a PowerShell terminal in VS Code within `ai-engineering-team`:

```powershell
# 1. Create a clean virtual environment
python -m venv .venv

# 2. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# If execution policy blocks activation:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 3. Upgrade pip and install package with development dependencies
python -m pip install --upgrade pip
pip install -e .[dev]
```

---

## 3. Docker Desktop & Switch Infrastructure Setup

Switch provides official standalone Docker Compose configurations that bundle the **Switch Server**, **Switch Gateway**, and **Mattermost**.

### A. Start Docker Desktop
If Docker Desktop is not running:
```powershell
Start-Process "C:\Users\athar\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
```
Wait until the tray icon turns steady green or `docker ps` outputs container status.

### B. Launch Switch & Mattermost
In your deployment directory, launch the stack with the `collab` (Mattermost) and `gateway` profiles:

```powershell
# Set required bootstrap tokens and profiles
$env:AGENT_REGISTRATION_TOKEN = "switch_bootstrap_token_secret_12345"
$env:SECRET_KEYS = "key1:a_very_long_secret_key_string_32chars!"
$env:GATEWAY_ADMIN_EMAIL = "admin@example.com"
$env:GATEWAY_ADMIN_PASSWORD = "AdminPassword123!"
$env:COMPOSE_PROFILES = "collab,gateway"

# Run Compose (or use docker compose from Switch repo)
docker compose --profile collab --profile gateway up -d
```

### Services Published:
- **Switch API & Agent Bridge**: `http://localhost:8000`
- **Switch Administrative Gateway**: `http://localhost:3000`
- **Mattermost Chat Server**: `http://localhost:8065`

---

## 4. Mattermost Configuration

1. **Access Mattermost**:
   Open `http://localhost:8065` in your browser. Log in with the admin credentials set during setup.
2. **Allow Bot Account Creation**:
   - Open **System Console** (top-left menu).
   - Under **Integrations**, select **Bot Accounts**.
   - Set **Enable Bot Account Creation** to `true`.
   - Save changes.
3. **Configure Teammate Display Names**:
   - In System Console, open **Site Configuration** -> **Users and Teams**.
   - Set **Teammate Name Display** to **Show first and last name**.
4. **Allow Untrusted Internal Connections (for Callback Buttons)**:
   - In System Console, navigate to **Environment** -> **Developer**.
   - Add `switch, localhost, 127.0.0.1` to **Allow untrusted internal connections to**.
   - Save changes.
5. **Connect to Switch**:
   - Open Switch Gateway at `http://localhost:3000`.
   - On the **Home** page under **Messaging apps**, click **Connect** -> **Mattermost**.
   - Enter Url: `http://mattermost:8065` (or `http://localhost:8065`), Team: `engineering`, Callback Base Url: `http://host.docker.internal:8082`.
   - Click **Connect** and link your user account.

---

## 5. Configure `.env`

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Review or edit `.env`:
```ini
SWITCH_SERVER_URL=http://localhost:8000
SWITCH_API_KEY=your_agent_api_key_from_registration
SWITCH_AGENT_ID=your_registered_agent_id
SWITCH_REGISTRATION_TOKEN=switch_bootstrap_token_secret_12345
SWITCH_DEFAULT_ROOM_ID=room_default

MATTERMOST_URL=http://localhost:8065
MATTERMOST_TEAM=engineering
MATTERMOST_ADMIN_USER=admin
MATTERMOST_ADMIN_PASSWORD=AdminPassword123!

TARGET_REPO_PATH=../
ALLOWED_REPO_PATHS=../,./

HUMAN_APPROVAL_REQUIRED=true
AUTO_RUN_TESTS=true
APP_HOST=0.0.0.0
APP_PORT=8082
LOG_LEVEL=INFO
```

---

## 6. Running the AI Engineering Team

Start the FastAPI application and Switch agent connection:

```powershell
python -m uvicorn engineering_team.main:app --host 0.0.0.0 --port 8082 --reload
```

You will see:
```text
INFO:     Starting AI Engineering Team Service...
INFO:     Connecting to Switch WebSocket: ws://localhost:8000/agents/.../connection/ws
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8082
```

---

## 7. Running the Automated Test Suite

To run the complete unit and integration test suite:

```powershell
python -m pytest -v
```

To run with coverage reporting:
```powershell
python -m pytest --cov=engineering_team tests/
```

---

## 8. Troubleshooting & Shutdown

### Port 8082 or 8000 in use:
Find and terminate existing processes:
```powershell
Get-NetTCPConnection -LocalPort 8082 -ErrorAction SilentlyContinue | Select-Object OwningProcess
Stop-Process -Id <PID> -Force
```

### Shutting down Docker services:
```powershell
docker compose --profile collab --profile gateway down
```
