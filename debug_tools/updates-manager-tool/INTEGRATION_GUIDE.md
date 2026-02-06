# 🚀 Updates Manager Tool - Guide d'Intégration

**Cible** : Intégrateurs et développeurs  
**Cas d'usage** : Intégrer l'Updates Manager dans un workflow de déploiement

---

## Table des matières

1. [Intégration CI/CD](#intégration-cicd)
2. [Installation sur nouveaux devices](#installation-sur-nouveaux-devices)
3. [Workflow multi-distributeur](#workflow-multi-distributeur)
4. [Scripts d'automatisation](#scripts-dautomatisation)
5. [Monitoring et alertes](#monitoring-et-alertes)
6. [Rollback et récupération](#rollback-et-récupération)

---

## Intégration CI/CD

### GitLab CI/CD

#### Configuration `.gitlab-ci.yml`

```yaml
stages:
  - build
  - publish-update

variables:
  MEETING_API_URL: "https://meeting.ygsoft.fr"
  UPDATES_MANAGER_PATH: "${CI_PROJECT_DIR}/updates-manager-tool"

build:
  stage: build
  image: raspbian:latest
  script:
    - make build VERSION=${CI_COMMIT_TAG}
  artifacts:
    paths:
      - dist/
    expire_in: 1 day
  only:
    - tags

publish-update:
  stage: publish-update
  image: python:3.11
  dependencies:
    - build
  before_script:
    - cd ${UPDATES_MANAGER_PATH}
    - python -m venv .venv
    - source .venv/bin/activate
    - pip install -r requirements.txt
  script:
    # Déterminer le device type et distribution selon le tag
    - |
      case "${CI_COMMIT_TAG}" in
        rtsp-recorder-*-stable)
          export DEVICE_TYPE="RTSP-Recorder"
          export DISTRIBUTION="232"
          ;;
        rtsp-recorder-*-beta)
          export DEVICE_TYPE="RTSP-Recorder"
          export DISTRIBUTION="beta"
          ;;
        jupiter-*-stable)
          export DEVICE_TYPE="Jupiter"
          export DISTRIBUTION="other"
          ;;
        *)
          echo "Unknown tag format: ${CI_COMMIT_TAG}"
          exit 1
          ;;
      esac
    
    # Publier la mise à jour
    - |
      python -m app.cli publish \
        --device-type "${DEVICE_TYPE}" \
        --distribution "${DISTRIBUTION}" \
        --version "${CI_COMMIT_TAG#*-}" \
        --source "${CI_PROJECT_DIR}/dist/update.tar.gz" \
        --notes "Built from commit ${CI_COMMIT_SHORT_SHA}"
  only:
    - tags
  when: on_success
```

**Utilisation**

```bash
# Tag format : device-type-version-channel
git tag "rtsp-recorder-2.33.07-stable"
git push origin "rtsp-recorder-2.33.07-stable"

# Pipeline déclenché automatiquement
# Vérifier l'état sur GitLab UI
```

#### Configuration sécurisée du token

```bash
# 1. Générer un token d'intégrateur
#    Admin > User Manager > Créer utilisateur "ci-builder"
#    Permissions : updates:publish, updates:view, fleet:view

# 2. Ajouter en variable protégée GitLab
#    Settings > CI/CD > Variables
#    - Name: MEETING_AUTH_TOKEN
#    - Value: abc123def456... (token)
#    - Protected: ✅
#    - Masked: ✅

# 3. Utiliser dans les scripts
export MEETING_AUTH_TOKEN="${MEETING_AUTH_TOKEN}"
```

### GitHub Actions

#### Configuration `.github/workflows/publish-update.yml`

```yaml
name: Publish Update

on:
  push:
    tags:
      - 'v[0-9]+.[0-9]+.[0-9]+*'

env:
  MEETING_API_URL: https://meeting.ygsoft.fr
  UPDATES_MANAGER_PATH: updates-manager-tool

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          submodules: recursive
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install updates-manager-tool
        run: |
          cd $UPDATES_MANAGER_PATH
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Determine device type
        run: |
          TAG="${{ github.ref_name }}"
          if [[ "$TAG" =~ ^rtsp-recorder- ]]; then
            echo "DEVICE_TYPE=RTSP-Recorder" >> $GITHUB_ENV
            echo "DISTRIBUTION=232" >> $GITHUB_ENV
          elif [[ "$TAG" =~ ^jupiter- ]]; then
            echo "DEVICE_TYPE=Jupiter" >> $GITHUB_ENV
            echo "DISTRIBUTION=other" >> $GITHUB_ENV
          fi
      
      - name: Publish to Meeting
        env:
          MEETING_AUTH_TOKEN: ${{ secrets.MEETING_AUTH_TOKEN }}
        run: |
          cd $UPDATES_MANAGER_PATH
          VERSION="${{ github.ref_name }}"
          VERSION="${VERSION#v}"  # Retirer le 'v' du tag
          
          python -m app.cli publish \
            --device-type "$DEVICE_TYPE" \
            --distribution "$DISTRIBUTION" \
            --version "$VERSION" \
            --source "../dist/update.tar.gz" \
            --notes "Released from GitHub Actions"
```

---

## Installation sur nouveaux devices

### Processus de bootstrapping

#### 1. Configuration initiale du device

```bash
# Sur le nouveau device physique
ssh admin@device.local

# Installer les composants de base
apt-get update
apt-get install -y curl wget tar

# Créer le répertoire de travail
mkdir -p /opt/updates
```

#### 2. Enregistrement auprès du Meeting server

```bash
# Le device doit contacter le Meeting server
# pour se déclarer et obtenir sa clé unique

curl -X POST https://meeting.ygsoft.fr/api/devices/register \
  -H "Content-Type: application/json" \
  -d '{
    "device_type": "RTSP-Recorder",
    "distribution": "232",
    "hostname": "device-001",
    "mac_address": "00:11:22:33:44:55"
  }'

# Réponse : { "device_key": "ABC123DEF456GHI789JKL012" }
# Sauvegarder cette clé
echo "ABC123DEF456GHI789JKL012" > /opt/updates/device_key
```

#### 3. Setup du client Update Monitor

```bash
# Installer l'agent de mise à jour sur le device
git clone https://github.com/ygsoft/meeting-device-agent /opt/meeting-agent
cd /opt/meeting-agent
./install.sh --meeting-server https://meeting.ygsoft.fr

# Créer un cron job pour vérifier les updates
cat > /etc/cron.d/meeting-updates <<EOF
*/5 * * * * root /opt/meeting-agent/check-updates.sh
EOF
```

#### 4. Test de connectivité

```bash
# Vérifier que le device peut contacter le Meeting server
curl -v https://meeting.ygsoft.fr/api/devices/checkin \
  -d "device_key=$(cat /opt/updates/device_key)"

# Doit retourner 200 avec l'état du device
```

### Onboarding en masse

#### Script PowerShell pour déployer 100 devices

```powershell
# provision-devices.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$CsvPath,  # CSV avec device IPs
    
    [Parameter(Mandatory=$true)]
    [string]$DeviceType,  # RTSP-Recorder, Jupiter, etc
    
    [Parameter(Mandatory=$true)]
    [string]$Distribution  # 232, beta, other, etc
)

$ErrorActionPreference = "Stop"

function Deploy-Device {
    param(
        [string]$DeviceIp,
        [string]$DeviceType,
        [string]$Distribution
    )
    
    $sshPath = "C:\Program Files\Git\usr\bin\ssh.exe"
    
    Write-Host "Deploying to $DeviceIp..."
    
    # Enregistrer le device
    & $sshPath admin@$DeviceIp @"
set -e
curl -X POST https://meeting.ygsoft.fr/api/devices/register \
  -H "Content-Type: application/json" \
  -d '{
    "device_type": "$DeviceType",
    "distribution": "$Distribution",
    "hostname": "device-$(hostname)",
    "ip": "$DeviceIp"
  }' > /tmp/device_key.json

DEVICE_KEY=\$(jq -r '.device_key' /tmp/device_key.json)
echo "\$DEVICE_KEY" > /opt/updates/device_key

# Installer l'agent
git clone https://github.com/ygsoft/meeting-device-agent /opt/meeting-agent
cd /opt/meeting-agent
./install.sh --meeting-server https://meeting.ygsoft.fr

# Test
curl https://meeting.ygsoft.fr/api/devices/checkin \
  -d "device_key=\$DEVICE_KEY"

echo "✅ Device configured"
"@
    
    Write-Host "✅ Deployed successfully to $DeviceIp"
}

# Lire le CSV et déployer
$devices = Import-Csv -Path $CsvPath
foreach ($device in $devices) {
    Deploy-Device `
        -DeviceIp $device.IP `
        -DeviceType $DeviceType `
        -Distribution $Distribution
}

Write-Host "✅ All devices deployed"
```

**Fichier CSV**
```csv
IP,Hostname
192.168.1.100,device-001
192.168.1.101,device-002
192.168.1.102,device-003
...
```

**Exécution**
```powershell
.\provision-devices.ps1 `
    -CsvPath devices.csv `
    -DeviceType RTSP-Recorder `
    -Distribution 232
```

---

## Workflow multi-distributeur

### Canaux parallèles (Stable / Beta / Canary)

```
┌─────────────────────────────────────────────────┐
│ CI/CD Pipeline                                  │
│ Compile & Build v2.33.07                        │
└─────────────────────────────────────────────────┘
              ↓
    ┌─────────────────────┐
    │ Pubier vers canaux: │
    ├─────────────────────┤
    │ 1. alpha (dev)      │ (1-2 devices)
    │ 2. beta (test)      │ (20 devices)
    │ 3. 232 (prod)       │ (100 devices)
    └─────────────────────┘
              ↓
    Attendre 24h
              ↓
    Vérifier métriques (uptime, errors)
              ↓
    OK ? → Promouvoir vers stable / stable2
    KO ? → Rollback
```

### Promotion progressive (Canary Deploy)

#### Script de promotion

```bash
#!/bin/bash
# promote-update.sh

DEVICE_TYPE="RTSP-Recorder"
VERSION="2.33.07"
MEETING_URL="https://meeting.ygsoft.fr"
TOKEN="${MEETING_AUTH_TOKEN}"

function promote() {
    local from_dist=$1
    local to_dist=$2
    
    echo "Promoting $DEVICE_TYPE v$VERSION : $from_dist → $to_dist"
    
    # Copier les artefacts
    ssh root@meeting.ygsoft.fr <<EOF
    cp -r /var/meeting/published/$DEVICE_TYPE/$from_dist/$VERSION \
          /var/meeting/published/$DEVICE_TYPE/$to_dist/
EOF
    
    echo "✅ Promoted"
}

# Stage 1 : Alpha (test device)
echo "=== Stage 1: Alpha (test device) ==="
promote "alpha" "alpha"
sleep 3600  # Attendre 1h
check_metrics "alpha" || exit 1

# Stage 2 : Beta (20% de la flotte)
echo "=== Stage 2: Beta (20%) ==="
promote "beta" "beta"
sleep 7200  # Attendre 2h
check_metrics "beta" || exit 1

# Stage 3 : Production (100%)
echo "=== Stage 3: Production (100%) ==="
promote "232" "232"

echo "✅ Promotion complete"
```

### Détection d'anomalies

```bash
#!/bin/bash
# check-deployment-health.sh

DEVICE_TYPE="RTSP-Recorder"
VERSION="2.33.07"
DISTRIBUTION="beta"
TOKEN="${MEETING_AUTH_TOKEN}"

# Récupérer les stats de déploiement
STATS=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "https://meeting.ygsoft.fr/api/admin/device-updates?device_type=$DEVICE_TYPE&distribution=$DISTRIBUTION")

UPDATED=$(echo "$STATS" | jq '.items | map(select(.installed_version=="'$VERSION'")) | length')
FAILED=$(echo "$STATS" | jq '.items | map(select(.state=="FAILED")) | length')
TOTAL=$(echo "$STATS" | jq '.total')

SUCCESS_RATE=$((UPDATED * 100 / TOTAL))

echo "Deployment stats for $DEVICE_TYPE/$DISTRIBUTION v$VERSION:"
echo "  Updated: $UPDATED / $TOTAL ($SUCCESS_RATE%)"
echo "  Failed: $FAILED"

# Alerter si taux d'échec > 5%
FAILURE_RATE=$((FAILED * 100 / TOTAL))
if [ $FAILURE_RATE -gt 5 ]; then
    echo "⚠️  Failure rate too high: $FAILURE_RATE%"
    curl -X POST https://alerts.slack.com/hooks/... \
      -d "text=Update failed: $DEVICE_TYPE $VERSION ($FAILURE_RATE% failure)"
    exit 1
fi

echo "✅ Deployment healthy"
```

---

## Scripts d'automatisation

### Publication automatique depuis repo

```python
#!/usr/bin/env python3
# auto-publish.py
# Watch repo pour nouvelles builds et publier automatiquement

import os
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

WATCH_DIR = Path("/mnt/shared/builds")
UPDATES_MANAGER = Path.home() / "Meeting/YG-meeting/updates-manager-tool"
PUBLISHED_LOG = Path.home() / ".updates-manager/published-builds.json"

def get_published_builds():
    """Charger la liste des builds déjà publiées"""
    if PUBLISHED_LOG.exists():
        with open(PUBLISHED_LOG) as f:
            return json.load(f)
    return []

def save_published_builds(builds):
    """Sauvegarder la liste des builds publiées"""
    PUBLISHED_LOG.write_text(json.dumps(builds, indent=2))

def parse_build_name(filename):
    """Parser le nom de build pour extraire les infos
    
    Format : {device_type}-{version}-{channel}.tar.gz
    Ex: rpi-cam-2.33.07-stable.tar.gz
    """
    name = filename.replace(".tar.gz", "")
    parts = name.rsplit("-", 2)
    
    if len(parts) != 3:
        return None
    
    device_type, version, channel = parts
    
    # Mapper channel vers distribution
    channel_map = {
        "stable": "232",
        "beta": "beta",
        "alpha": "alpha",
        "custom": "other"
    }
    
    distribution = channel_map.get(channel, "other")
    
    return {
        "device_type": device_type,
        "version": version,
        "distribution": distribution,
        "channel": channel
    }

def publish_build(build_path, info):
    """Publier une build"""
    cmd = [
        "python", "-m", "app.cli", "publish",
        "--device-type", info["device_type"],
        "--distribution", info["distribution"],
        "--version", info["version"],
        "--source", str(build_path),
        "--notes", f"Auto-published from {build_path.name} ({datetime.now().isoformat()})"
    ]
    
    print(f"Publishing {build_path.name}...")
    result = subprocess.run(cmd, cwd=UPDATES_MANAGER)
    return result.returncode == 0

def main():
    print("Updates auto-publisher started")
    print(f"Watching: {WATCH_DIR}")
    
    published = get_published_builds()
    
    while True:
        try:
            # Scanner les builds disponibles
            for build_file in WATCH_DIR.glob("*.tar.gz"):
                if build_file.name in published:
                    continue  # Déjà publiée
                
                info = parse_build_name(build_file.name)
                if not info:
                    print(f"⚠️  Skipping {build_file.name} (invalid format)")
                    continue
                
                # Vérifier que le fichier est prêt (pas en cours d'écriture)
                time.sleep(5)
                if build_file.stat().st_size == 0:
                    continue
                
                # Publier
                if publish_build(build_file, info):
                    published.append(build_file.name)
                    save_published_builds(published)
                    print(f"✅ Published {build_file.name}")
                else:
                    print(f"❌ Failed to publish {build_file.name}")
            
            time.sleep(60)  # Scanner chaque minute
            
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
```

**Lancer en background**
```bash
nohup python3 auto-publish.py > ~/.updates-manager/auto-publish.log 2>&1 &
```

---

## Monitoring et alertes

### Dashboard Grafana

#### Template Grafana JSON

```json
{
  "dashboard": {
    "title": "Updates Manager - Fleet Status",
    "panels": [
      {
        "title": "Deployment Progress",
        "targets": [
          {
            "expr": "count(device_state{state='UP_TO_DATE'}) / count(device_state) * 100"
          }
        ]
      },
      {
        "title": "Failed Updates",
        "targets": [
          {
            "expr": "count(device_state{state='FAILED'})"
          }
        ]
      },
      {
        "title": "Devices by State",
        "targets": [
          {
            "expr": "count(device_state) by (state)"
          }
        ]
      }
    ]
  }
}
```

### Alertes Email/Slack

```python
# alerts.py

import requests
import json

SLACK_WEBHOOK = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
MEETING_API = "https://meeting.ygsoft.fr"

def check_failed_updates():
    """Vérifier les mises à jour échouées"""
    resp = requests.get(
        f"{MEETING_API}/api/admin/device-updates",
        headers={"Authorization": f"Bearer {TOKEN}"},
        params={"state": "FAILED"}
    )
    
    failed_count = resp.json()["total"]
    
    if failed_count > 0:
        message = f"⚠️  {failed_count} devices have failed updates"
        requests.post(SLACK_WEBHOOK, json={"text": message})

def check_outdated_devices():
    """Alerter si trop de devices outdated"""
    resp = requests.get(
        f"{MEETING_API}/api/admin/device-updates",
        headers={"Authorization": f"Bearer {TOKEN}"},
        params={"state": "OUTDATED"}
    )
    
    outdated_count = resp.json()["total"]
    
    if outdated_count > 50:
        message = f"⚠️  {outdated_count} devices are outdated"
        requests.post(SLACK_WEBHOOK, json={"text": message})

def main():
    check_failed_updates()
    check_outdated_devices()

if __name__ == "__main__":
    main()
```

**Lancer via cron**
```bash
# /etc/cron.d/meeting-alerts
0 8 * * * root cd /opt/meeting && python3 alerts.py
```

---

## Rollback et récupération

### Stratégie de rollback

```bash
#!/bin/bash
# rollback-update.sh

DEVICE_TYPE="RTSP-Recorder"
FROM_VERSION="2.33.07"
TO_VERSION="2.33.06"
DISTRIBUTION="232"

echo "Rolling back $DEVICE_TYPE from $FROM_VERSION → $TO_VERSION"

# 1. Vérifier que l'ancienne version existe
curl -s "https://meeting.ygsoft.fr/api/admin/updates/verify?device_type=$DEVICE_TYPE&distribution=$DISTRIBUTION&version=$TO_VERSION" \
  | jq -e '.manifest_exists == true' > /dev/null || { echo "❌ Target version not found"; exit 1; }

# 2. Créer un channel pour le rollback
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"device_type\": \"$DEVICE_TYPE\",
    \"distribution\": \"$DISTRIBUTION\",
    \"target_version\": \"$TO_VERSION\"
  }" \
  "https://meeting.ygsoft.fr/api/admin/update-channels"

echo "✅ Rollback channel created"

# 3. Monitoring
for i in {1..60}; do
    UPDATED=$(curl -s \
      -H "Authorization: Bearer $TOKEN" \
      "https://meeting.ygsoft.fr/api/admin/device-updates?device_type=$DEVICE_TYPE&distribution=$DISTRIBUTION" \
      | jq "map(select(.installed_version==\"$TO_VERSION\")) | length")
    
    echo "[$i/60] Updated: $UPDATED devices"
    sleep 60
done

echo "✅ Rollback complete"
```

### Recovery plan

```markdown
# Plan de Récupération

## Si déploiement en masse échoue

1. **Identifier les devices affectés**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
        "https://meeting.ygsoft.fr/api/admin/device-updates?state=FAILED" \
        | jq '.items[] | {device_key, message}'
   ```

2. **Arrêter le déploiement en cours**
   - Désactiver le channel : Admin > Updates > Canaux > Toggle OFF
   - Vérifier que les devices ne reçoivent plus de updates

3. **Analyser les erreurs**
   - Récupérer les logs : SSH sur un device et `tail -100 /var/log/meeting-updates.log`
   - Identifier le problème (archive corrompue, incompatibilité version, etc)

4. **Corriger et re-publier**
   - Recréer l'archive si nécessaire
   - Publier nouvelle version (ex: v2.33.07.1)
   - Créer un nouveau channel

5. **Déploiement progressif**
   - Commencer par 1 device de test
   - Vérifier la métrique (logs, uptime, healthcheck)
   - Progresser : 5% → 25% → 100%

## Si un device reste stuck

1. **Accès SSH au device**
   ```bash
   ssh admin@device.local
   
   # Vérifier l'agent
   systemctl status meeting-update-agent
   
   # Forcer une vérification
   /opt/meeting-agent/check-updates.sh
   
   # Voir les logs
   tail -100 /var/log/meeting-updates.log
   ```

2. **Redémarrer l'agent**
   ```bash
   systemctl restart meeting-update-agent
   ```

3. **Forcer le rollback manuel**
   ```bash
   /opt/updates/rollback.sh 2.33.06
   ```
```

---

## Ressources supplémentaires

- [Documentation principale](./DOCUMENTATION.md)
- [Référence API Server](./API_SERVER_REFERENCE.md)
- [Architecture globale Meeting](../docs/structure_globale.md)

---

**Integration Guide v1.0.0** | Mise à jour : 2026-02-04
