# 📚 Updates Manager Tool - Documentation Index

**Welcome to the complete documentation for the Updates Manager Tool!**

This document helps you navigate all available documentation based on your role and needs.

---

## 🎯 Choose Your Path

### 👨‍💻 **I'm a Developer - I want to publish updates**

**Start here**: [Quick Start](./README.md#-quick-start-5-minutes) (5 minutes)

**Then read**:
1. [CLI Usage Guide](./DOCUMENTATION.md#interface-cli) - Learn all CLI commands
2. [Publishing Workflow](./DOCUMENTATION.md#workflow-de-publication) - Understand the process
3. [Examples](./DOCUMENTATION.md#exemples-dutilisation) - Copy-paste ready commands

**Tools you'll use**:
- `.\Run-CLI.ps1 publish` - Publish updates
- `.\Run-CLI.ps1 verify` - Verify publication
- `.\Run-CLI.ps1 fleet` - Check device status

---

### 🖥️ **I'm a System Admin - I need to set up the backend**

**Start here**: [API Server Reference](./API_SERVER_REFERENCE.md)

**Main sections**:
1. [Installation](./API_SERVER_REFERENCE.md#installation-côté-serveur) - Server setup
2. [Configuration](./API_SERVER_REFERENCE.md#configuration) - Database, MySQL tables
3. [Authentication](./API_SERVER_REFERENCE.md#authentification) - Bearer token flow
4. [API Endpoints](./API_SERVER_REFERENCE.md#endpoints) - All available routes

**Your responsibilities**:
- ✅ Set up Apache & PHP on Meeting server
- ✅ Create MySQL tables (update_channels, devices, etc)
- ✅ Configure Bearer token authentication
- ✅ Manage published updates directory (`/var/meeting/published/`)

---

### 🚀 **I'm a CI/CD Engineer - I need to integrate with pipelines**

**Start here**: [Integration Guide](./INTEGRATION_GUIDE.md)

**Key sections**:
1. [GitLab CI/CD](./INTEGRATION_GUIDE.md#gitlab-cicd) - `.gitlab-ci.yml` examples
2. [GitHub Actions](./INTEGRATION_GUIDE.md#github-actions) - Workflow templates
3. [Automation Scripts](./INTEGRATION_GUIDE.md#scripts-dautomatisation) - Auto-publishing
4. [Monitoring](./INTEGRATION_GUIDE.md#monitoring-et-alertes) - Health checks & alerts

**You'll create**:
- CI/CD pipeline that publishes builds automatically
- Monitoring scripts that alert on failures
- Rollback procedures for failed deployments

---

### 🏢 **I'm an Integrator - I need to deploy to 100+ devices**

**Start here**: [Installation on Devices](./INTEGRATION_GUIDE.md#installation-sur-nouveaux-devices)

**Key sections**:
1. [Bulk Provisioning](./INTEGRATION_GUIDE.md#onboarding-en-masse) - Deploy to many devices
2. [Canary Deployments](./INTEGRATION_GUIDE.md#promotion-progressive-canary-deploy) - Staged rollouts
3. [Health Monitoring](./INTEGRATION_GUIDE.md#monitoring-et-alertes) - Track deployments
4. [Rollback Procedures](./INTEGRATION_GUIDE.md#rollback-et-récupération) - Recovery plans

**Your workflow**:
- Provision devices in bulk using scripts
- Stage updates to alpha → beta → production
- Monitor deployment health
- Execute rollbacks if needed

---

### 📖 **I'm a User - I just want to use the GUI**

**Start here**: [GUI Documentation](./DOCUMENTATION.md#interface-gui)

**Main tabs**:
- **Dashboard** - Overview of your fleet
- **Channels** - Manage distribution channels
- **Publish** - Upload new updates (with UI helpers)
- **Fleet** - See all devices and their status
- **History** - View past deployments
- **Diagnostics** - Test connectivity
- **Settings** - Configure profiles & tokens

**Quick reference**:
1. Configure a profile in Settings
2. Go to Publish tab
3. Select device type (dropdown auto-loads from server!)
4. Select distribution (auto-populates)
5. Upload your archive
6. Click Publish

---

## 📚 Documentation Files

### **README.md** (This file structure)
- Overview of the project
- Quick start (5 minutes)
- Common tasks
- Troubleshooting
- System requirements

**→ Use for**: First impression, getting started, feature overview

---

### **DOCUMENTATION.md** (Comprehensive User Guide)
- **Size**: ~30 KB
- **Time to read**: 45 minutes

**Sections**:
1. [Overview](./DOCUMENTATION.md#vue-densemble) - What is this tool?
2. [Architecture](./DOCUMENTATION.md#architecture) - How it works
3. [Installation](./DOCUMENTATION.md#installation) - Setup steps
4. [Configuration](./DOCUMENTATION.md#configuration) - Profiles & settings
5. [CLI Interface](./DOCUMENTATION.md#interface-cli) - Command reference
6. [GUI Interface](./DOCUMENTATION.md#interface-gui) - Tab documentation
7. [Publishing Workflow](./DOCUMENTATION.md#workflow-de-publication) - Step-by-step process
8. [API Server](./DOCUMENTATION.md#api-server) - Backend details
9. [Examples](./DOCUMENTATION.md#exemples-dutilisation) - Use cases
10. [Troubleshooting](./DOCUMENTATION.md#troubleshooting) - Common issues
11. [Development](./DOCUMENTATION.md#développement) - Extending the tool

**→ Use for**: Complete reference, learning all features, deep dives

---

### **API_SERVER_REFERENCE.md** (Backend API Spec)
- **Size**: ~25 KB
- **Time to read**: 30 minutes

**Sections**:
1. [Architecture](./API_SERVER_REFERENCE.md#architecture-api) - Backend structure
2. [Server Installation](./API_SERVER_REFERENCE.md#installation-côté-serveur) - Setup steps
3. [Configuration](./API_SERVER_REFERENCE.md#configuration) - Config files, MySQL
4. [Authentication](./API_SERVER_REFERENCE.md#authentification) - Bearer token flow
5. [Endpoints](./API_SERVER_REFERENCE.md#endpoints) - 7 REST APIs documented
6. [Data Structures](./API_SERVER_REFERENCE.md#structure-des-données) - manifest.json format
7. [Permissions](./API_SERVER_REFERENCE.md#gestion-des-permissions) - Role-based access
8. [cURL Examples](./API_SERVER_REFERENCE.md#exemples-curl) - Testing endpoints
9. [Troubleshooting](./API_SERVER_REFERENCE.md#troubleshooting) - Common backend issues

**→ Use for**: Backend setup, API integration, admin configuration

---

### **INTEGRATION_GUIDE.md** (Deployment & Automation)
- **Size**: ~28 KB
- **Time to read**: 45 minutes

**Sections**:
1. [CI/CD Integration](./INTEGRATION_GUIDE.md#intégration-cicd) - GitLab/GitHub
2. [Device Installation](./INTEGRATION_GUIDE.md#installation-sur-nouveaux-devices) - Bootstrapping
3. [Multi-Channel Workflow](./INTEGRATION_GUIDE.md#workflow-multi-distributeur) - Staged deployments
4. [Automation Scripts](./INTEGRATION_GUIDE.md#scripts-dautomatisation) - Auto-publishing
5. [Monitoring](./INTEGRATION_GUIDE.md#monitoring-et-alertes) - Health checks
6. [Rollback](./INTEGRATION_GUIDE.md#rollback-et-récupération) - Recovery

**→ Use for**: CI/CD setup, bulk deployment, automation

---

## 🔗 Quick Navigation

### By Topic

| Topic | Location |
|-------|----------|
| Publishing my first update | [DOCUMENTATION.md - Workflow](./DOCUMENTATION.md#workflow-de-publication) |
| Setting up a development environment | [DOCUMENTATION.md - Installation](./DOCUMENTATION.md#installation) |
| Understanding the architecture | [DOCUMENTATION.md - Architecture](./DOCUMENTATION.md#architecture) |
| Configuring Bearer tokens | [API_SERVER_REFERENCE.md - Auth](./API_SERVER_REFERENCE.md#authentification) |
| All REST API endpoints | [API_SERVER_REFERENCE.md - Endpoints](./API_SERVER_REFERENCE.md#endpoints) |
| GitLab CI/CD integration | [INTEGRATION_GUIDE.md - GitLab](./INTEGRATION_GUIDE.md#gitlab-cicd) |
| GitHub Actions integration | [INTEGRATION_GUIDE.md - GitHub](./INTEGRATION_GUIDE.md#github-actions) |
| Deploying to 100 devices | [INTEGRATION_GUIDE.md - Bulk Deployment](./INTEGRATION_GUIDE.md#onboarding-en-masse) |
| Canary/staged deployments | [INTEGRATION_GUIDE.md - Canary](./INTEGRATION_GUIDE.md#promotion-progressive-canary-deploy) |
| Troubleshooting issues | [DOCUMENTATION.md - Troubleshooting](./DOCUMENTATION.md#troubleshooting) |
| API troubleshooting | [API_SERVER_REFERENCE.md - Troubleshooting](./API_SERVER_REFERENCE.md#troubleshooting) |

### By Command

| Command | Where to learn |
|---------|----------------|
| `.\Run-CLI.ps1 publish` | [DOCUMENTATION.md - publish command](./DOCUMENTATION.md#2-publish---publier-une-mise-à-jour) |
| `.\Run-CLI.ps1 verify` | [DOCUMENTATION.md - verify command](./DOCUMENTATION.md#3-verify---vérifier-une-publication) |
| `.\Run-CLI.ps1 fleet` | [DOCUMENTATION.md - fleet command](./DOCUMENTATION.md#4-fleet---état-de-la-flotte-de-devices) |
| `.\Run-CLI.ps1 history` | [DOCUMENTATION.md - history command](./DOCUMENTATION.md#5-history---historique-des-mises-à-jour) |
| `curl /api/admin/updates/publish` | [API_SERVER_REFERENCE.md - Publish endpoint](./API_SERVER_REFERENCE.md#2-post-apiadminupdatespublish) |
| `curl /api/admin/updates/verify` | [API_SERVER_REFERENCE.md - Verify endpoint](./API_SERVER_REFERENCE.md#3-get-apiadminupdatesverify) |
| `curl /api/admin/device-updates` | [API_SERVER_REFERENCE.md - Fleet endpoint](./API_SERVER_REFERENCE.md#6-get-apiadmindevice-updates) |

### By Error Message

| Error | Solution |
|-------|----------|
| `AUTH_MISSING` | [DOCUMENTATION.md - Auth error](./DOCUMENTATION.md#-auth_missing-ou-auth_denied) |
| `VALIDATION - device_type required` | [DOCUMENTATION.md - Validation](./DOCUMENTATION.md#-validation---device_type-distribution-version-required) |
| `Source not found` | [DOCUMENTATION.md - Source error](./DOCUMENTATION.md#-source-not-found) |
| `Verification failed` | [DOCUMENTATION.md - Verify error](./DOCUMENTATION.md#-verification-failed---check-server-logs) |
| `ImportError: No module named 'PySide6'` | [DOCUMENTATION.md - Import error](./DOCUMENTATION.md#-importerror-no-module-named-pyside6) |
| `GUI fails to launch` | [DOCUMENTATION.md - GUI error](./DOCUMENTATION.md#-la-gui-ne-se-lance-pas) |
| `SSL certificate problem` | [API_SERVER_REFERENCE.md - SSL error](./API_SERVER_REFERENCE.md#-curl-60-ssl-certificate-problem) |
| `FILE_TOO_LARGE` | [API_SERVER_REFERENCE.md - File size](./API_SERVER_REFERENCE.md#-file_too_large) |

---

## 💡 Learning Paths

### Path 1: "I'm Publishing My First Update" (15 minutes)
1. Read: [README.md - Quick Start](./README.md#-quick-start-5-minutes)
2. Follow: [DOCUMENTATION.md - Workflow](./DOCUMENTATION.md#workflow-de-publication)
3. Try: `.\Run-CLI.ps1 publish --help`
4. Publish! ✅

### Path 2: "I'm Setting Up the Backend" (1 hour)
1. Read: [API_SERVER_REFERENCE.md - Installation](./API_SERVER_REFERENCE.md#installation-côté-serveur)
2. Follow: Setup steps (Apache, PHP, MySQL)
3. Test: [API_SERVER_REFERENCE.md - cURL Examples](./API_SERVER_REFERENCE.md#exemples-curl)
4. Deploy! ✅

### Path 3: "I'm Integrating with GitLab CI/CD" (45 minutes)
1. Skim: [INTEGRATION_GUIDE.md - CI/CD](./INTEGRATION_GUIDE.md#intégration-cicd)
2. Copy: [INTEGRATION_GUIDE.md - GitLab config](./INTEGRATION_GUIDE.md#configuration-gitlab-cicd)
3. Adapt: Variables (MEETING_API_URL, token)
4. Test: Push a tag to trigger pipeline ✅

### Path 4: "I'm Deploying to 100 Devices" (2 hours)
1. Read: [INTEGRATION_GUIDE.md - Device Installation](./INTEGRATION_GUIDE.md#installation-sur-nouveaux-devices)
2. Run: [INTEGRATION_GUIDE.md - Bulk Provisioning Script](./INTEGRATION_GUIDE.md#onboarding-en-masse)
3. Monitor: [INTEGRATION_GUIDE.md - Health Monitoring](./INTEGRATION_GUIDE.md#monitoring-et-alertes)
4. Deploy! ✅

---

## 🎓 Key Concepts

### Bearer Token
- **What**: API authentication credential
- **Where to learn**: [API_SERVER_REFERENCE.md - Authentication](./API_SERVER_REFERENCE.md#authentification)
- **How to get**: Admin panel > User Manager > Generate token

### Device Types
- **What**: Category of devices (RTSP-Recorder, Jupiter, etc.)
- **Where to learn**: [DOCUMENTATION.md - Device Types](./DOCUMENTATION.md#device-types-dropdown-dynamique)
- **How to list**: `.\Run-CLI.ps1 --json list-channels` or [GUI Channels tab](./DOCUMENTATION.md#2-channels-🔀)

### Distributions
- **What**: Release channels (232, beta, alpha, etc.)
- **Where to learn**: [DOCUMENTATION.md - Workflow](./DOCUMENTATION.md#workflow-de-publication)
- **How to use**: Auto-populated based on device type

### Manifest
- **What**: JSON file describing an update
- **Format**: [API_SERVER_REFERENCE.md - Manifest](./API_SERVER_REFERENCE.md#format-du-manifestjson)
- **Where stored**: `/var/meeting/published/{type}/{dist}/{version}/manifest.json`

### Channels
- **What**: Links a device type + distribution to a target version
- **Create**: [DOCUMENTATION.md - GUI Channels](./DOCUMENTATION.md#2-channels-🔀)
- **Manage**: Admin > Updates > Channels

---

## 🆘 Getting Help

### I don't know where to start
→ Choose your role in [this section](#-choose-your-path)

### I can't find what I'm looking for
1. Check the [Quick Navigation](#-quick-navigation) section
2. Use Ctrl+F to search in documentation files
3. Check [Common Issues](./DOCUMENTATION.md#troubleshooting)

### I found a bug or have a feature request
- Report via: admin@meeting.ygsoft.fr
- Include: Error message, steps to reproduce, OS version

### The documentation is outdated
- Last updated: 2026-02-04
- Check recent changes in the docs or repo

---

## 📊 Documentation Stats

| File | Size | Sections | Time to Read |
|------|------|----------|--------------|
| README.md | 12 KB | 12 | 10 min |
| DOCUMENTATION.md | 30 KB | 11 | 45 min |
| API_SERVER_REFERENCE.md | 25 KB | 9 | 30 min |
| INTEGRATION_GUIDE.md | 28 KB | 6 | 45 min |
| **Total** | **95 KB** | **38** | **2.5 hours** |

---

## 🎯 Next Steps

1. **Choose your role** above
2. **Start reading** the recommended documentation
3. **Try the examples** provided
4. **Reference back** to this index as needed

---

**Documentation v1.0.0** | Created: 2026-02-04

*Last updated: 2026-02-04 - All documentation current and tested*
