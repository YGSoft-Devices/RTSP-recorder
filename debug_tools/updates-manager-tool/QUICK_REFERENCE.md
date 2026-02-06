# ⚡ Updates Manager Tool - Quick Reference Card

**Print this page or save as bookmark for quick lookups!**

---

## 🚀 Essential Commands

### CLI - Fast Publishing
```powershell
# Publish update
.\Run-CLI.ps1 publish --device-type DEVICE --distribution DIST --version VER --source FILE

# Verify publication
.\Run-CLI.ps1 verify --device-type DEVICE --distribution DIST --version VER

# Check fleet
.\Run-CLI.ps1 fleet --state OUTDATED

# List channels
.\Run-CLI.ps1 list-channels
```

### GUI - Visual Workflow
```powershell
# Launch GUI
.\Start-GUI.ps1

# Tabs: Dashboard → Publish → Fleet → History
```

---

## 🔑 Token Management

| Task | Steps |
|------|-------|
| **Get token** | Admin > User Manager > Generate/copy token |
| **Configure** | GUI Settings > Configure Token > paste |
| **Test token** | CLI: `list-channels` command |
| **Reset** | Regenerate in Admin > paste new token |

---

## 📝 Publishing Checklist

- [ ] Compiled update archive
- [ ] Device type selected (from dropdown)
- [ ] Distribution chosen (auto-populated)
- [ ] Version number formatted correctly
- [ ] Archive file located and readable
- [ ] Token configured and valid
- [ ] Network connection to meeting.ygsoft.fr
- [ ] Publish & verify

**Expected time**: 2-5 minutes

---

## 🐛 Instant Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| `AUTH_MISSING` | Regenerate token > configure in Settings |
| `No module PySide6` | `pip install -r requirements.txt` |
| `Can't connect` | Check VPN, firewall, token validity |
| `Upload fails` | Verify archive format (tar.gz or zip) |
| `Slow GUI` | Use CLI instead or filter devices |
| `Device not listed` | Verify correct device_type spelling |

---

## 📍 Key File Locations

| Item | Path |
|------|------|
| **Published updates** | `/var/meeting/published/{type}/{dist}/{version}/` |
| **Token storage** | Windows Keyring (encrypted) |
| **Local history** | `~/.updates-manager/publish-history.json` |
| **Log files** | `/var/log/meeting/api-updates.log` (server) |

---

## 🔗 Important APIs

| Endpoint | Purpose | HTTP |
|----------|---------|------|
| `/api/admin/updates/publish` | Upload update | POST |
| `/api/admin/updates/verify` | Check publication | GET |
| `/api/admin/updates/device-types` | List device types | GET |
| `/api/admin/device-updates` | Fleet status | GET |
| `/api/admin/update-channels` | List channels | GET |

**All require Bearer token except `/device-types`**

---

## 🏷️ Valid Formats

```
Device Type:   [A-Za-z0-9._-]{1,128}    RTSP-Recorder ✅
Distribution:  [A-Za-z0-9._-]{1,128}    232, beta, alpha ✅
Version:       [A-Za-z0-9._-]{1,64}     2.33.07, 1.0.0 ✅
Archive:       .tar.gz or .zip          max 100 MB ✅
```

---

## 💾 Manifest.json Template

```json
{
  "version": "2.33.07",
  "device_type": "RTSP-Recorder",
  "distribution": "232",
  "archive": "rpi-cam-update_2.33.07.tar.gz",
  "sha256": "abc123def456...",
  "size": 512345,
  "notes": "Bug fixes and improvements",
  "created_at": "2026-02-04T14:30:22Z"
}
```

---

## 📊 Common curl Examples

```bash
# List channels
curl -H "Authorization: Bearer TOKEN" \
     https://meeting.ygsoft.fr/api/admin/update-channels

# Get device types
curl https://meeting.ygsoft.fr/api/admin/updates/device-types

# Verify update
curl "https://meeting.ygsoft.fr/api/admin/updates/verify?device_type=RTSP-Recorder&distribution=232&version=2.33.07"

# Fleet status
curl -H "Authorization: Bearer TOKEN" \
     https://meeting.ygsoft.fr/api/admin/device-updates?state=OUTDATED
```

---

## ⌚ Deployment Timeline

| Phase | Duration | Action |
|-------|----------|--------|
| Publish | 1-5 min | Upload archive + manifest |
| Verify | < 1 min | Confirm on server |
| Alpha | 1 hour | Test on 1-2 devices |
| Beta | 2 hours | Deploy to 20% |
| Production | 4 hours | Full rollout (100%) |
| **Total** | **~8 hours** | Canary deployment |

---

## 🎯 Role Quick Links

| Role | Start | Main Docs |
|------|-------|-----------|
| **Developer** | Publish | DOCUMENTATION.md - CLI |
| **Admin** | Backend | API_SERVER_REFERENCE.md |
| **DevOps** | CI/CD | INTEGRATION_GUIDE.md |
| **Integrator** | Bulk | INTEGRATION_GUIDE.md |

---

## ⚙️ Configuration Paths

```powershell
# Windows paths
Token:          Windows Keyring (encrypted)
Profiles:       C:\Users\%USERNAME%\.updates-manager\
History:        C:\Users\%USERNAME%\.updates-manager\publish-history.json

# Server paths
Published:      /var/meeting/published/
Config:         /var/www/meeting-backend/api/config.php
Database:       MySQL (meeting_db)
```

---

## 🚨 Error Code Reference

| Code | Meaning | Fix |
|------|---------|-----|
| `AUTH_MISSING` | No token provided | Configure in Settings |
| `AUTH_DENIED` | Invalid token | Regenerate token |
| `AUTH_EXPIRED` | Token expired | Regenerate token |
| `VALIDATION_FAILED` | Invalid parameters | Check format (table above) |
| `FILE_TOO_LARGE` | Archive > 100 MB | Compress more |
| `DISK_FULL` | Server out of space | Clean old versions |
| `NOT_FOUND` | Update not found | Verify publish succeeded |

---

## 📋 Pre-Deployment Checklist

```markdown
## Before Publishing v2.33.07 to Production

### Archive
- [ ] Built with correct flags
- [ ] Archive size reasonable (< 100 MB)
- [ ] Tested locally on device
- [ ] No sensitive data included

### Metadata
- [ ] Device type valid and exists
- [ ] Distribution matches rollout plan
- [ ] Version follows semantic versioning
- [ ] Release notes prepared

### Process
- [ ] Token configured and tested
- [ ] Network connectivity verified
- [ ] Alpha channel tested (1-2 devices)
- [ ] Beta metrics reviewed (OK)
- [ ] Approval from team lead

### Communication
- [ ] Stakeholders notified
- [ ] Rollback procedure documented
- [ ] Support team briefed
- [ ] Monitoring alerts enabled

### Post-Publish
- [ ] [ ] Verify publication succeeded
- [ ] [ ] Monitor alpha deployment (1h)
- [ ] [ ] Monitor beta deployment (2h)
- [ ] [ ] Monitor production (4h)
- [ ] [ ] Confirm success rate > 95%
```

---

## 🔐 Security Checklist

- [ ] Token never stored in plaintext
- [ ] HTTPS used for all connections
- [ ] Token kept confidential (not in logs)
- [ ] CI/CD token marked as "protected"
- [ ] Regular token rotation scheduled
- [ ] Expired tokens revoked
- [ ] Access logs reviewed
- [ ] Archive integrity verified (SHA256)

---

## 📞 Quick Support

**Documentation**
- Full: [DOCUMENTATION.md](./DOCUMENTATION.md)
- API: [API_SERVER_REFERENCE.md](./API_SERVER_REFERENCE.md)
- Integration: [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)
- Index: [DOCS_INDEX.md](./DOCS_INDEX.md)

**Contacts**
- Slack: #meeting-team
- Email: admin@meeting.ygsoft.fr
- Issues: GitLab Issues (project repo)

---

## 💡 Pro Tips

1. **Dry-run before production**: `--dry-run` flag to test
2. **Use JSON output**: `--json` for scripting/parsing
3. **Filter large fleets**: `--device-type X --state OUTDATED`
4. **Watch builds**: Run auto-publisher script for CI/CD
5. **Backup token**: Save in password manager (not plain text)
6. **Monitor metrics**: Set up Slack alerts for failures
7. **Document deployments**: Keep deployment log/runbook
8. **Test rollback**: Practice recovery before incident

---

## 🎓 Learning Resources

| Topic | Time | Link |
|-------|------|------|
| Quick Start | 5 min | README.md #quick-start |
| Full User Guide | 45 min | DOCUMENTATION.md |
| API Reference | 30 min | API_SERVER_REFERENCE.md |
| CI/CD Integration | 45 min | INTEGRATION_GUIDE.md |
| Navigation | 10 min | DOCS_INDEX.md |

---

**Quick Reference v1.0.0** | Last updated: 2026-02-04

*Bookmark this page for instant lookup!*
