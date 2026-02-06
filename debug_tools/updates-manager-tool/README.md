# 📦 Updates Manager Tool

**Unified platform for publishing updates, managing distribution channels, and supervising device fleets.**

**Available for**: Windows, macOS, Linux | **Language**: Python 3.11+ | **Framework**: PySide6 (Qt)

---

## 🎯 Quick Links

📖 **[Full Documentation](./DOCUMENTATION.md)** — Comprehensive user guide for developers and integrators

🔌 **[API Server Reference](./API_SERVER_REFERENCE.md)** — Backend endpoints, authentication, data structures

🚀 **[Integration Guide](./INTEGRATION_GUIDE.md)** — CI/CD integration, bulk deployment, automation scripts

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **Dashboard** | 📊 Fleet status overview, recent activity, key metrics |
| **Publish** | 🚀 Build archives, generate manifests, upload to Meeting server |
| **Channels** | 🔀 Create/edit distribution channels, assign versions to devices |
| **Fleet Status** | 🖥️ Monitor all devices, filter by type/state, detect outdated systems |
| **History** | 📜 Audit trail of all updates with timestamps and status |
| **Diagnostics** | 🔧 Connectivity tests, API validation, troubleshooting tools |
| **Settings** | ⚙️ Multi-profile support, secure token storage via Windows Keyring |

---

## 📋 Requirements

- **Operating System**: Windows 10/11 (primary), macOS, Linux
- **Python**: 3.11 or later
- **Meeting Backend**: Admin API access with valid Bearer token
- **Internet**: HTTPS connection to Meeting server
- **Storage**: ~500 MB for tool + dependencies

---

## ⚡ Quick Start (5 minutes)

### 1. Installation

```powershell
cd C:\Users\$env:USERNAME\Documents\gitHub\Meeting\YG-meeting\updates-manager-tool

# Create virtual environment (first time only)
python -m venv .venv

# Activate and install
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Launch GUI

```powershell
# Option A: Using PowerShell script (recommended)
.\Start-GUI.ps1

# Option B: Using batch file
.\start.bat

# Option C: Direct Python
.\.venv\Scripts\python.exe run.py
```

### 3. Configure Profile

1. Go to **Settings** tab
2. Click **Add Profile**
3. Enter:
   - **Name**: `prod` (or your choice)
   - **Base URL**: `https://meeting.ygsoft.fr`
4. Click **Save Profile**
5. Click **Configure Token** and paste your Bearer token

### 4. Publish Your First Update

```powershell
# Or use CLI for scripting
.\Run-CLI.ps1 publish `
  --device-type RTSP-Recorder `
  --distribution 232 `
  --version 2.33.07 `
  --source ./path/to/update.tar.gz
```

---

## 🎮 Usage Modes

### 🖱️ GUI Mode (Recommended for interactive work)

**Launch**
```powershell
.\Start-GUI.ps1
```

**Tabs**
- **Dashboard** — See fleet at a glance
- **Channels** — Manage distribution channels
- **Publish** — Upload new updates
- **Fleet** — Monitor devices
- **History** — View past deployments
- **Diagnostics** — Test connectivity
- **Settings** — Configure profiles and tokens

### 💻 CLI Mode (Recommended for automation)

**Launch**
```powershell
.\Run-CLI.ps1 --help
```

**Device Registration (Required)**
```powershell
# Register device with Meeting server (first time)
.\Run-CLI.ps1 register --device-key YOUR_DEVICE_KEY --token-code ABC123

# Check registration status
.\Run-CLI.ps1 status
```

**Self-Update**
```powershell
# Check for available updates
.\Run-CLI.ps1 check-update

# Download and install update (interactive)
.\Run-CLI.ps1 self-update

# Auto-install without confirmation
.\Run-CLI.ps1 self-update --yes
```

**Common Commands**
```powershell
# List channels
.\Run-CLI.ps1 list-channels

# Publish update
.\Run-CLI.ps1 publish --device-type RTSP-Recorder --distribution 232 --version 2.33.07 --source ./update.tar.gz

# Verify publication
.\Run-CLI.ps1 verify --device-type RTSP-Recorder --distribution 232 --version 2.33.07

# Check fleet status
.\Run-CLI.ps1 fleet

# View update history
.\Run-CLI.ps1 history
```

**Full CLI documentation** → [DOCUMENTATION.md#interface-cli](./DOCUMENTATION.md#interface-cli)

---

## 📚 Documentation

### For Different Roles

| Role | Start Here |
|------|-----------|
| **Dev publishing updates** | [DOCUMENTATION.md](./DOCUMENTATION.md) - CLI examples |
| **System Admin** | [API_SERVER_REFERENCE.md](./API_SERVER_REFERENCE.md) - Backend setup |
| **CI/CD Engineer** | [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) - GitLab/GitHub integration |
| **Integrator** | [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) - Multi-device deployment |

### Documentation Files

- **[DOCUMENTATION.md](./DOCUMENTATION.md)** (25 KB)
  - Complete user guide
  - Architecture overview
  - All API endpoints
  - Troubleshooting section
  - Development guide

- **[API_SERVER_REFERENCE.md](./API_SERVER_REFERENCE.md)** (20 KB)
  - Backend API specification
  - Authentication & permissions
  - Endpoint documentation with examples
  - MySQL schema
  - cURL examples

- **[INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)** (18 KB)
  - CI/CD pipeline integration
  - Bulk device provisioning
  - Canary deployment strategies
  - Automation scripts
  - Rollback procedures

---

## 🔑 Authentication

### Get Your Token

1. Access admin panel: `https://meeting.ygsoft.fr/admin/`
2. Go to **User Manager**
3. Create/select your user account
4. Generate or copy your **Bearer Token**
5. Save it in **Settings > Configure Token** (encrypted in Windows Keyring)

### Security Notes

- ✅ Tokens stored securely via Windows Keyring
- ✅ HTTPS only (no plaintext transmission)
- ✅ Token validates Bearer token format
- ✅ Expired tokens are detected and reported

---

## 📦 Architecture

```
updates-manager-tool/
├── app/
│   ├── main.py              # GUI entry point
│   ├── cli.py               # CLI commands
│   ├── api_client.py        # REST client
│   ├── publisher.py         # Archive/manifest logic
│   └── widgets/             # GUI components
├── run.py                   # GUI launcher
├── requirements.txt         # Python dependencies
├── Start-GUI.ps1            # PowerShell GUI launcher
├── Run-CLI.ps1              # PowerShell CLI launcher
└── DOCUMENTATION.md         # Full user guide
```

**Backend** (Meeting Server)
```
/var/www/meeting-backend/
├── api/controllers/AdminUpdateController.php
├── admin/updates_manager.php
└── .htaccess
```

---

## 🛠️ Common Tasks

### Publishing Updates

**Via GUI**
1. Open **Publish** tab
2. Select **Device Type** from dropdown
3. **Distribution** auto-populates
4. Enter **Version**
5. Select archive file
6. Click **Publish**

**Via CLI**
```powershell
.\Run-CLI.ps1 publish `
  --device-type RTSP-Recorder `
  --distribution 232 `
  --version 2.33.07 `
  --source C:\builds\update.tar.gz `
  --notes "Bug fix release"
```

### Checking Fleet Status

**Via GUI**
1. Open **Fleet** tab
2. Filter by Type or State
3. Click device for details

**Via CLI**
```powershell
# All devices
.\Run-CLI.ps1 fleet

# JSON output for processing
.\Run-CLI.ps1 --json fleet | jq '.items[] | select(.state=="OUTDATED")'

# Only outdated
.\Run-CLI.ps1 fleet --state OUTDATED
```

### Verifying Published Updates

```powershell
.\Run-CLI.ps1 verify `
  --device-type RTSP-Recorder `
  --distribution 232 `
  --version 2.33.07
```

Output:
```
Verification for RTSP-Recorder/232 v2.33.07:
  Manifest exists: True
  Archive exists: True
  SHA256 match: True
```

---

## 🔧 Troubleshooting

### ❌ "AUTH_MISSING" or "AUTH_DENIED"

```powershell
# Check token validity
.\Run-CLI.ps1 list-channels  # Will show error if auth fails

# Solution: Re-generate token in Admin panel
# Settings > Configure Token > paste new token
```

### ❌ "Import error: No module named 'PySide6'"

```powershell
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### 🐢 Slow when loading 1000+ devices

```powershell
# Use pagination and filters
.\Run-CLI.ps1 fleet --page 1 --device-type RTSP-Recorder

# Or filter by state
.\Run-CLI.ps1 fleet --state OUTDATED
```

**Full troubleshooting** → [DOCUMENTATION.md#troubleshooting](./DOCUMENTATION.md#troubleshooting)

---

## 🚀 Automation & Integration

### GitLab CI/CD

```yaml
publish-update:
  stage: deploy
  script:
    - cd updates-manager-tool
    - python -m app.cli publish \
        --device-type $DEVICE_TYPE \
        --version $CI_COMMIT_TAG \
        --source ../dist/update.tar.gz
  only:
    - tags
```

### GitHub Actions

```yaml
- name: Publish to Meeting
  env:
    MEETING_AUTH_TOKEN: ${{ secrets.MEETING_AUTH_TOKEN }}
  run: |
    python -m app.cli publish \
      --device-type MyDevice \
      --version ${{ github.ref_name }}
      --source ./dist/update.tar.gz
```

**Full integration guide** → [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)

---

## 📊 System Requirements

| Component | Requirement |
|-----------|-------------|
| **RAM** | 256 MB minimum |
| **Disk** | 500 MB (tool + deps) |
| **Network** | HTTPS to Meeting server |
| **Python** | 3.11+ |
| **OS** | Windows 10/11, macOS 10.14+, Ubuntu 18.04+ |

---

## 🤝 Support

**Documentation**
- 📖 [Full Documentation](./DOCUMENTATION.md)
- 🔌 [API Reference](./API_SERVER_REFERENCE.md)
- 🚀 [Integration Guide](./INTEGRATION_GUIDE.md)

**Issues or Questions**
- Check [Troubleshooting](./DOCUMENTATION.md#troubleshooting) section
- Review [API examples](./API_SERVER_REFERENCE.md#exemples-curl)
- Contact: admin@meeting.ygsoft.fr

---

## 📄 License

See [LICENSE](../LICENSE) file

---

**Version 1.0.0** | Last updated: 2026-02-04

✨ *Ready to publish? Start with [Quick Start](#-quick-start-5-minutes) or see [Full Documentation](./DOCUMENTATION.md)*
.\Run-CLI.ps1 verify --device-type rpi4 --distribution stable --version 1.0.0

# Option 2: Batch file
.\cli.bat --help

# Option 3: Direct Python (must be in tool directory with venv active)
.\.venv\Scripts\python.exe -m app.cli --help
```

### CLI Examples
```powershell
# List update channels
.\Run-CLI.ps1 list-channels

# Verify artifacts
.\Run-CLI.ps1 verify --device-type rpi4 --distribution stable --version 1.0.0

# Publish a release
.\Run-CLI.ps1 publish --device-type rpi4 --distribution stable --version 1.0.0 --source ./build

# List fleet status
.\Run-CLI.ps1 fleet --state OUTDATED

# View update history
.\Run-CLI.ps1 history --device-key abc123

# JSON output
.\Run-CLI.ps1 list-channels --json
```

## Configuration

### First-Time Setup
1. Launch the GUI: `python -m app.main`
2. Go to **Settings** tab
3. Create a new profile:
   - **Profile Name**: e.g., "Production"
   - **Base URL**: e.g., `https://meeting.ygsoft.fr`
   - **Token**: Your admin API token
4. Click **Save Profile** then **Set as Active**

### Token Storage
- Tokens are stored securely in Windows Credential Manager via `keyring`
- Fallback to `MEETING_TOKEN` environment variable if keyring unavailable
- Tokens are never logged or displayed in clear text

## Project Structure
```
updates-manager-tool/
├── .venv/                # Virtual environment (created on install)
├── app/
│   ├── __init__.py
│   ├── __main__.py       # Allows: python -m app
│   ├── main.py           # GUI entry point
│   ├── cli.py            # CLI entry point
│   ├── api_client.py     # HTTP client with retry
│   ├── publisher.py      # Archive building & manifest
│   ├── diagnostics.py    # Health checks service
│   ├── settings.py       # Token management
│   ├── storage.py        # Local storage helpers
│   ├── logger.py         # Rotating logs
│   └── widgets/          # GUI pages
│       ├── dashboard.py
│       ├── publish.py
│       ├── channels.py
│       ├── fleet.py
│       ├── history.py
│       ├── diagnostics.py
│       └── settings.py
├── run.py                # Launcher script
├── Start-GUI.ps1         # PowerShell GUI launcher
├── Run-CLI.ps1           # PowerShell CLI launcher
├── start.bat             # Batch GUI launcher
├── cli.bat               # Batch CLI launcher
├── requirements.txt
└── README.md
```

## Backend Requirements

The tool requires the following admin API endpoints in the Meeting backend:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/update-channels` | GET, POST | List/create channels |
| `/api/admin/update-channels/{id}` | PUT, DELETE | Update/delete channel |
| `/api/admin/updates/publish` | POST | Upload release artifacts |
| `/api/admin/updates/verify` | GET | Verify artifacts exist |
| `/api/admin/device-updates` | GET | Fleet status with filters |
| `/api/admin/device-updates/export` | GET | Export to CSV/JSON |
| `/api/admin/device-update-history` | GET | Update history |

See [docs/updatermanagertool.md](../docs/updatermanagertool.md) for full API specification.

## Packaging (Optional)

To create a standalone executable:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name UpdatesManagerTool app/main.py
```

## Troubleshooting

### Connection Issues
1. Go to **Diagnostics** tab
2. Click **Run All Tests**
3. Review results and generate support bundle if needed

### Token Issues
- Ensure token has admin privileges on the Meeting server
- Check if `MEETING_TOKEN` env var is set (takes precedence)
- Try **Clear Token** in Settings then re-enter
