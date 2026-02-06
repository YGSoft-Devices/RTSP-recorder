# 📦 Updates Manager Tool - Documentation Complète

**Version**: 1.0.0  
**Date**: 2026-02-04  
**Auteur**: Meeting Server Team

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Interface CLI](#interface-cli)
6. [Interface GUI](#interface-gui)
7. [Workflow de Publication](#workflow-de-publication)
8. [API Server](#api-server)
9. [Exemples d'utilisation](#exemples-dutilisation)
10. [Troubleshooting](#troubleshooting)
11. [Développement](#développement)

---

## Vue d'ensemble

L'**Updates Manager Tool** est une application intégrée qui permet de :

- **Publier des mises à jour** sur le serveur Meeting pour distribution aux devices
- **Gérer les canaux de distribution** (stable, beta, custom)
- **Suivre l'état des devices** et des mises à jour
- **Vérifier l'intégrité** des artefacts (manifest, archive, SHA256)
- **Visualiser l'historique** des mises à jour

### Cas d'usage

| Rôle | Tâche |
|------|-------|
| **Développeur** | Publier une nouvelle build vers Meeting (via CLI) |
| **Intégrateur** | Configurer les canaux et assigner des versions aux devices |
| **Admin** | Visualiser l'état de la flotte et les uploads publiés |

---

## Architecture

### Stack technologique

- **Frontend GUI** : PySide6 (Qt pour Python)
- **Backend API** : PHP REST (endpoints sous `/api/admin/updates/`)
- **Storage** : Filesystem (`/var/meeting/published/`) + MySQL (métadonnées)
- **Auth** : Bearer token (token utilisateur du User Manager)

### Structure des répertoires

```
updates-manager-tool/
├── app/
│   ├── __main__.py          # Point d'entrée pour `python -m app`
│   ├── __init__.py
│   ├── main.py              # Fenêtre principale GUI
│   ├── cli.py               # Commandes CLI
│   ├── api_client.py        # Client API Meeting
│   ├── publisher.py         # Logique d'archive et manifest
│   ├── storage.py           # Gestion profiles & historique local
│   ├── logger.py            # Logging
│   ├── settings.py          # Gestion des paramètres
│   ├── diagnostics.py       # Tests de connectivité
│   ├── channels.py          # Gestion des canaux
│   ├── fleet.py             # État des devices
│   ├── history.py           # Historique des updates
│   └── widgets/             # Composants GUI
│       ├── channels.py
│       ├── dashboard.py
│       ├── diagnostics.py
│       ├── fleet.py
│       ├── history.py
│       ├── publish.py
│       └── settings.py
├── run.py                   # Launcher GUI
├── requirements.txt         # Dépendances Python
├── .venv/                   # Environnement virtuel Python
├── Start-GUI.ps1            # Launcher PowerShell (GUI)
├── Run-CLI.ps1              # Launcher PowerShell (CLI)
├── start.bat                # Launcher batch (GUI)
├── cli.bat                  # Launcher batch (CLI)
└── README.md                # Guide rapide
```

### Structure des données côté serveur

```
/var/meeting/published/
└── {device_type}/
    └── {distribution}/
        └── {version}/
            ├── manifest.json              # Métadonnées
            ├── {archive_filename}         # Archive (tar.gz ou zip)
            ├── CHANGELOG.md               # (optionnel)
            └── manifest.sig               # (optionnel)

Exemple :
/var/meeting/published/
├── RTSP-Recorder/
│   ├── 232/
│   │   └── 2.33.06/
│   │       ├── manifest.json
│   │       └── rpi-cam-update_2.33.06_20260123_235618.tar.gz
│   └── beta/
│       └── 2.33.06/
│           └── manifest.json
├── Jupiter/
│   └── other/
│       └── 1.0.0/
│           └── manifest.json
└── RTSP-Viewer/
    └── alpha/
        └── 2.0.0/
            └── manifest.json
```

### Structure du manifest

```json
{
  "version": "2.33.06",
  "device_type": "RTSP-Recorder",
  "distribution": "beta",
  "archive": "rpi-cam-update_2.33.06_20260123_235618.tar.gz",
  "sha256": "5a61aa0df2eb597c9ecf28c8a1a6a571b2d8a3b38f67bed1deaf1dc2bea8e8cd",
  "size": 493149,
  "notes": "Release notes here",
  "created_at": "2026-02-04T00:03:21Z"
}
```

---

## Installation

### Prérequis

- **Python** 3.11+ (testé avec 3.11.9)
- **pip** (gestionnaire de packages)
- **Git** (pour cloner le repo)
- **Windows/Linux/macOS** (compatible multiplateforme)

### Installation locale

1. **Cloner le repository**
   ```bash
   cd "C:\Users\{user}\Documents\gitHub\Meeting"
   git clone ... # ou déjà présent
   cd YG-meeting/updates-manager-tool
   ```

2. **Créer l'environnement virtuel**
   ```bash
   python -m venv .venv
   ```

3. **Activer l'environnement virtuel**

   **Windows (PowerShell)**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   **Linux/macOS**
   ```bash
   source .venv/bin/activate
   ```

4. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

### Dépendances principales

```
PySide6==6.7.2              # Qt pour Python (GUI)
requests==2.31.0           # HTTP client
keyring==24.1.1            # Stockage sécurisé des credentials
python-dotenv==1.0.0       # Gestion des variables d'env
```

---

## Configuration

### Profils

L'outil utilise un système de profils pour gérer plusieurs serveurs/configurations.

**Emplacement des données** : `~/.updates-manager/`
- `profiles.json` - Liste des profils
- `publish-history.json` - Historique des publications

### Création d'un profil

#### Via GUI

1. Accédez à l'onglet **Settings**
2. Cliquez sur **Add Profile**
3. Remplissez:
   - **Name**: Identifiant du profil (ex: `prod`, `staging`)
   - **Base URL**: https://meeting.ygsoft.fr
   - **Timeout**: 20 (secondes)
   - **Retries**: 3
4. Cliquez **Save Profile**
5. Configurez le **Token**: Générez un token dans l'admin Meeting > Users
6. Cliquez **Save Token**

#### Via CLI

```bash
# Lister les profils
python -m app.cli list-channels --profile prod

# Les profiles sont gérés interactivement
# Le profile actif est indiqué avec ✅
```

### Variables d'environnement

```bash
# Fichier .env (optionnel)
UPDATES_MANAGER_PROFILE=prod
UPDATES_MANAGER_DEBUG=1
```

---

## Interface CLI

### Installation rapide (CLI)

**Windows (PowerShell)**
```powershell
cd C:\Users\{user}\Documents\gitHub\Meeting\YG-meeting\updates-manager-tool
.\Run-CLI.ps1 --help
```

**Linux/macOS**
```bash
cd ~/gitHub/Meeting/YG-meeting/updates-manager-tool
python -m app.cli --help
```

### Commandes disponibles

#### 1. `list-channels` - Lister les canaux

```bash
python -m app.cli list-channels
python -m app.cli list-channels --profile prod
python -m app.cli --json list-channels
```

**Sortie** :
```
Found 3 channels:
  ✅ RTSP-Recorder/232/default → v2.33.05
  ❌ RTSP-Recorder/beta/default → v2.33.06
  ✅ Jupiter/other/default → v1.0.0
```

#### 2. `publish` - Publier une mise à jour

```bash
# Publication simple
python -m app.cli publish \
  --device-type RTSP-Recorder \
  --distribution 232 \
  --version 2.33.07 \
  --source ./build/rpi-cam-update_2.33.07.tar.gz \
  --notes "Bug fixes and improvements"

# Avec signature
python -m app.cli publish \
  --device-type Jupiter \
  --distribution other \
  --version 1.0.1 \
  --source ./dist/jupiter-update-1.0.1.zip \
  --format zip

# Dry-run (pas d'upload)
python -m app.cli publish \
  --device-type test \
  --distribution test \
  --version 1.0.0 \
  --source ./test.tar.gz \
  --dry-run
```

**Processus** :
1. Validation du source
2. Computation du SHA256
3. Construction du manifest
4. Upload (archive + manifest)
5. Vérification automatique

#### 3. `verify` - Vérifier une publication

```bash
python -m app.cli verify \
  --device-type RTSP-Recorder \
  --distribution 232 \
  --version 2.33.07

python -m app.cli --json verify \
  --device-type RTSP-Recorder \
  --distribution 232 \
  --version 2.33.07
```

**Sortie** :
```
Verification for RTSP-Recorder/232 v2.33.07:
  Manifest exists: True
  Archive exists: True
  SHA256 match: True
```

#### 4. `fleet` - État de la flotte de devices

```bash
# Tous les devices
python -m app.cli fleet

# Filtrer par type
python -m app.cli fleet --device-type RTSP-Recorder

# Filtrer par état
python -m app.cli fleet --state OUTDATED

# JSON pour traitement
python -m app.cli --json fleet | jq '.items[] | select(.state=="OUTDATED")'
```

**États possibles** :
- `UP_TO_DATE` - Version installée = version cible
- `OUTDATED` - Mise à jour disponible
- `IN_PROGRESS` - Installation en cours
- `FAILED` - Dernière tentative échouée
- `UNKNOWN` - Pas d'information

#### 5. `history` - Historique des mises à jour

```bash
# Tous les événements
python -m app.cli history

# Avec pagination
python -m app.cli history --page 2 --page-size 20

# Filtrer par device
python -m app.cli history --device-key ABC123...
```

---

## Interface GUI

### Lancement

**Windows**
```powershell
.\Start-GUI.ps1
# ou
.\start.bat
# ou
python run.py
```

**Linux/macOS**
```bash
./Start-GUI.ps1  # avec PowerShell Core
# ou
python run.py
```

### Onglets

#### 1. **Dashboard** 📊
- Résumé des états des devices
- Dernières activités
- Statistiques

#### 2. **Channels** 🔀
- **Active Channels** : Liste des canaux configurés
- **Create Channel** : Nouveau canal
- Bouton 📦 pour voir le contenu (manifest, changelog)
- Gestion (toggle, supprimer)

#### 3. **Publish** 🚀
- **Device Type** : Dropdown dynamique (chargé depuis server)
- **Distribution** : Auto-rempli selon le device type
- **Version** : Saisie libre
- **Source** : Sélectionner dossier ou archive
- Actions : Build, Compute SHA256, Validate, Upload, Verify
- Dry-run option

#### 4. **Fleet** 🖥️
- Table des devices avec:
  - Device Key
  - Type
  - Distribution
  - Dernière connexion
  - Versions installée/cible
  - État
- Filtres : Type, État, Recherche
- Pagination

#### 5. **History** 📜
- Événements de mise à jour
- Timestamps
- Statuts (success, failed)
- Détails

#### 6. **Diagnostics** 🔧
- Test de connexion (DNS, TLS, Auth)
- Test des endpoints API
- Vérification du published root
- Support bundle generator

#### 7. **Settings** ⚙️
- Gestion des profils
- Configuration du token
- Paramètres (timeout, retries)

---

## Workflow de Publication

### Processus complet

```
┌─────────────────────────────────────────────────────┐
│ 1. PRÉPARATION                                      │
│   - Compiler/builder la mise à jour                 │
│   - Générer l'archive (tar.gz ou zip)              │
│   - (Optionnel) Ajouter CHANGELOG.md               │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 2. PUBLICATION (CLI ou GUI)                        │
│   a) Valider les inputs (type, distribution, version)
│   b) Calculer SHA256 de l'archive                  │
│   c) Générer manifest.json                          │
│   d) Upload vers server Meeting                     │
│   e) Vérifier les artefacts sur le server           │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 3. SUR LE SERVER MEETING                           │
│   - Archive stockée dans:                           │
│     /var/meeting/published/{type}/{dist}/{version}/ │
│   - API retourne URLs publiques                     │
│   - Les devices peuvent découvrir et télécharger    │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 4. CONFIGURATION (optionnel)                        │
│   - Créer un channel associant type+dist+version   │
│   - Activer le channel pour distribution aux devices│
│   - Les devices détectent et déploient              │
└─────────────────────────────────────────────────────┘
```

### Exemple complet : Publication RTSP-Recorder v2.33.07

**Étape 1 : Builder le code**
```bash
cd ~/projects/rpi-cam
make build
# Génère : dist/rpi-cam-update_2.33.07_20260204_143022.tar.gz
```

**Étape 2 : Publier**
```bash
cd ~/Meeting/YG-meeting/updates-manager-tool
python -m app.cli publish \
  --device-type RTSP-Recorder \
  --distribution 232 \
  --version 2.33.07 \
  --source ~/projects/rpi-cam/dist/rpi-cam-update_2.33.07_20260204_143022.tar.gz \
  --notes "v2.33.07: Fixed RTSP stream handling, improved error logging"
```

**Sortie**
```
Publishing RTSP-Recorder/232 v2.33.07...
  Computing SHA256...
  SHA256: abc123def456...
  Size: 512345 bytes
  Building manifest...
  Uploading...
  ✅ Published successfully!
  Verifying...
  ✅ Verification passed
```

**Étape 3 : Vérifier (optionnel)**
```bash
python -m app.cli verify \
  --device-type RTSP-Recorder \
  --distribution 232 \
  --version 2.33.07
```

**Étape 4 : Activer le déploiement**

Via la page admin : https://meeting.ygsoft.fr/admin/updates_manager.php
- Créer un channel pour `RTSP-Recorder/232/default`
- Target version : `2.33.07`
- Activer le channel
- Les devices 4x RTSP-Recorder (distribution 232) téléchargeront automatiquement

---

## API Server

### Endpoints

Tous les endpoints requièrent l'authentification Bearer token.

#### `GET /api/admin/update-channels`

Liste les canaux configurés.

**Réponse**
```json
{
  "ok": true,
  "items": [
    {
      "id": 1,
      "device_type": "RTSP-Recorder",
      "distribution": "232",
      "channel": "default",
      "target_version": "2.33.07",
      "active": 1,
      "updated_at": "2026-02-04 14:30:22"
    }
  ],
  "total": 1
}
```

#### `POST /api/admin/updates/publish`

Publier une mise à jour.

**Requête (multipart/form-data)**
```
Fields:
  device_type=RTSP-Recorder
  distribution=232
  version=2.33.07

Files:
  manifest=manifest.json (JSON)
  archive=rpi-cam-update_2.33.07_20260204_143022.tar.gz (binary)
  signature=manifest.sig (optional)
```

**Réponse**
```json
{
  "ok": true,
  "message": "Published",
  "path": "RTSP-Recorder/232/2.33.07",
  "manifest_url": "https://meeting.ygsoft.fr/published/RTSP-Recorder/232/2.33.07/manifest.json",
  "archive_url": "https://meeting.ygsoft.fr/published/RTSP-Recorder/232/2.33.07/rpi-cam-update_2.33.07_20260204_143022.tar.gz"
}
```

#### `GET /api/admin/updates/verify`

Vérifier l'existence et l'intégrité des artefacts.

**Paramètres**
```
device_type=RTSP-Recorder
distribution=232
version=2.33.07
```

**Réponse**
```json
{
  "ok": true,
  "path": "/var/meeting/published/RTSP-Recorder/232/2.33.07",
  "manifest_exists": true,
  "archive_exists": true,
  "archive_name": "rpi-cam-update_2.33.07_20260204_143022.tar.gz",
  "sha256_match": true,
  "manifest": {
    "version": "2.33.07",
    "device_type": "RTSP-Recorder",
    "distribution": "232",
    "archive": "rpi-cam-update_2.33.07_20260204_143022.tar.gz",
    "sha256": "abc123def456...",
    "size": 512345,
    "notes": "v2.33.07: Fixed RTSP stream handling",
    "created_at": "2026-02-04T14:30:22Z"
  },
  "changelog": "- Fix RTSP connection issues\n- Improve error handling",
  "manifest_url": "https://...",
  "archive_url": "https://..."
}
```

#### `GET /api/admin/updates/device-types`

Lister tous les device types et distributions disponibles.

**Réponse**
```json
{
  "ok": true,
  "device_types": {
    "RTSP-Recorder": ["232", "beta", "alpha"],
    "Jupiter": ["other", "stable"],
    "RTSP-Viewer": ["alpha"],
    "test": ["test2"]
  }
}
```

#### `GET /api/admin/updates/versions`

Lister les versions disponibles pour un type/distribution.

**Paramètres**
```
device_type=RTSP-Recorder
distribution=232
```

**Réponse**
```json
{
  "ok": true,
  "versions": ["2.33.05", "2.33.06", "2.33.07"]
}
```

#### `GET /api/admin/device-updates`

État de la flotte.

**Paramètres**
```
page=1
page_size=50
state=OUTDATED (optionnel)
device_type=RTSP-Recorder (optionnel)
search=... (optionnel)
```

**Réponse**
```json
{
  "ok": true,
  "items": [
    {
      "device_key": "ABC123...",
      "device_type": "RTSP-Recorder",
      "distribution": "232",
      "last_seen": "2026-02-04 14:22:15",
      "installed_version": "2.33.06",
      "target_version": "2.33.07",
      "status": "AVAILABLE",
      "state": "OUTDATED",
      "last_attempt_at": "2026-02-04 13:00:00"
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 50
}
```

#### `GET /api/admin/device-update-history`

Historique des mises à jour.

**Réponse**
```json
{
  "ok": true,
  "items": [
    {
      "id": 123,
      "device_key": "ABC123...",
      "device_type": "RTSP-Recorder",
      "from_version": "2.33.05",
      "to_version": "2.33.06",
      "status": "SUCCESS",
      "started_at": "2026-02-03 10:00:00",
      "completed_at": "2026-02-03 10:05:30",
      "message": ""
    }
  ],
  "total": 42
}
```

---

## Exemples d'utilisation

### Cas 1 : Dev publie une build en 5 min

```bash
cd ~/projects/my-device
make release VERSION=1.2.3

cd ~/Meeting/YG-meeting/updates-manager-tool

python -m app.cli publish \
  --device-type MyDevice \
  --distribution stable \
  --version 1.2.3 \
  --source ./release/mydevice-1.2.3.tar.gz \
  --notes "v1.2.3 released"

# ✅ Publié et vérifiée en ~30 sec
```

### Cas 2 : Vérifier l'état des devices avant déploiement

```bash
python -m app.cli fleet --device-type RTSP-Recorder --json | \
  jq 'group_by(.state) | map({state: .[0].state, count: length})'

# Affiche la distribution des états
# [{"state":"UP_TO_DATE","count":2}, {"state":"OUTDATED","count":2}]
```

### Cas 3 : Dépanner via diagnostics

```bash
python -m app.cli --json diagnostics

# Affiche les logs des tests
# - Connexion au serveur
# - Vérification des endpoints
# - Accès au published root
```

### Cas 4 : Integration CI/CD

```yaml
# .gitlab-ci.yml
publish-update:
  stage: deploy
  script:
    - cd updates-manager-tool
    - python -m app.cli publish \
        --device-type $CI_DEVICE_TYPE \
        --distribution $CI_DISTRIBUTION \
        --version $CI_COMMIT_TAG \
        --source ../dist/update.tar.gz \
        --notes "Version $CI_COMMIT_TAG - $CI_COMMIT_MESSAGE"
  only:
    - tags
  variables:
    CI_DEVICE_TYPE: "my-device"
    CI_DISTRIBUTION: "stable"
```

---

## Troubleshooting

### ❌ "AUTH_MISSING" ou "AUTH_DENIED"

**Causes possibles**

1. **Token invalide ou expiré**
   ```bash
   # Solution : Régénérer le token
   # Admin > User Manager > Régénérer token utilisateur
   # Configurer dans Settings > Token
   ```

2. **Profile pas activé**
   ```bash
   # Solution : Activer le profile
   # Settings > Profiles > Sélectionner profile > Save
   ```

3. **Serveur Meeting inaccessible**
   ```bash
   # Solution : Vérifier la connexion
   curl -I https://meeting.ygsoft.fr
   ```

### ❌ "VALIDATION - device_type, distribution, version required"

**Cause** : Les champs sont vides ou ne passent pas la validation

```bash
# Valider le format
# device_type, distribution, version : [A-Za-z0-9._-]{1,128}

# ✅ Valide
python -m app.cli publish \
  --device-type RTSP-Recorder \
  --distribution 232 \
  --version 2.33.07 \
  --source ./update.tar.gz

# ❌ Invalide (caractères spéciaux)
python -m app.cli publish \
  --device-type "RTSP Recorder" \
  --distribution "232-beta" \  # ok si hyphen seul
  --version "2.33.07 final" \  # NON - espace interdit
  --source ./update.tar.gz
```

### ❌ "Source not found"

**Solution** : Utiliser le chemin absolu ou relatif correct

```bash
# ❌ Mauvais
python -m app.cli publish ... --source update.tar.gz

# ✅ Bon
python -m app.cli publish ... --source ./dist/update.tar.gz
# ou
python -m app.cli publish ... --source /home/user/dist/update.tar.gz
```

### ❌ "Verification failed - check server logs"

**Causes**

1. **Droits d'accès insuffisants**
   ```bash
   # Vérifier sur le serveur
   ssh meeting@meeting.ygsoft.fr
   ls -la /var/meeting/published/
   # Doit être accessible par www-data
   ```

2. **Espace disque insuffisant**
   ```bash
   # Vérifier sur le serveur
   df -h /var/meeting/
   ```

### ❌ "ImportError: No module named 'PySide6'"

**Solution** : Réinstaller les dépendances

```bash
pip install --force-reinstall -r requirements.txt
```

### ❌ La GUI ne se lance pas

**Solution**

1. Vérifier l'installation
   ```bash
   python -c "import PySide6; print(PySide6.__version__)"
   ```

2. Utiliser la CLI à la place
   ```bash
   python -m app.cli list-channels
   ```

### ⚠️ Lenteur lors du chargement des devices

**Cause** : Grande flotte (1000+ devices)

**Solutions**
- Utiliser la pagination : `--page 2 --page-size 50`
- Filtrer par type : `--device-type RTSP-Recorder`
- Utiliser JSON : `--json | jq` pour post-traitement

---

## Développement

### Architecture du code

#### `api_client.py` - Client API

```python
class ApiClient:
    def __init__(self, base_url, token, timeout=20, retries=3)
    
    # Update channels
    def list_channels() -> Dict
    def list_device_types() -> Dict
    
    # Publishing
    def publish_update(files, data) -> Dict
    def verify_artifacts(device_type, distribution, version) -> Dict
    
    # Fleet
    def list_device_updates(params) -> Dict
    def list_update_history(params) -> Dict
```

#### `publisher.py` - Logique d'archive

```python
def build_archive(source_dir, output_path, fmt="tar.gz") -> Path
def compute_sha256(path) -> Tuple[str, int]
def build_manifest(device_type, distribution, ...) -> Dict
def validate_manifest(manifest) -> bool
```

#### `storage.py` - Gestion du stockage local

```python
def load_profiles() -> Dict
def save_profiles(data) -> None
def get_token(profile_name) -> str
def load_publish_history() -> Dict
```

### Ajouter une nouvelle commande CLI

1. Créer la fonction dans `cli.py`

```python
def cmd_new_command(args, client: ApiClient):
    """Description de la commande."""
    # Logique
    result = client.my_api_call()
    print(result)
```

2. Enregistrer dans `main()`

```python
subparsers = parser.add_subparsers(...)
parser_new = subparsers.add_parser('new-command', help='...')
parser_new.add_argument('--param', required=True)
parser_new.set_defaults(func=cmd_new_command)
```

3. Utiliser

```bash
python -m app.cli new-command --param value
```

### Ajouter un widget GUI

1. Créer le fichier `widgets/my_widget.py`

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

class MyWidget(QWidget):
    def __init__(self, get_api_client):
        super().__init__()
        self.get_api_client = get_api_client
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        btn = QPushButton("Click me")
        layout.addWidget(btn)
```

2. Ajouter à `main.py`

```python
from .widgets.my_widget import MyWidget

# Dans __init__
self.my_tab = MyWidget(self.get_api_client)
self.tabs.addTab(self.my_tab, "My Tab")
```

### Tester en local

```bash
# Avec mock API (pas de serveur needed)
python -m pytest tests/

# Avec serveur test
UPDATES_MANAGER_TEST_URL=http://localhost:8000 pytest tests/

# Coverage
pytest --cov=app tests/
```

---

## Support et Ressources

### Documentation supplémentaire

- [Meeting Server Admin Guide](../docs/admin_setup.md)
- [API REST Meeting](../docs/api_documentation.md)
- [Architecture globale](../docs/structure_globale.md)

### Contacts

- **Admin Meeting** : admin@meeting.ygsoft.fr
- **Dev Team** : dev@ygsoft.fr
- **Issues** : Signaler via GitLab Issues

### Changelog

**v1.0.0** (2026-02-04)
- ✅ Publication de mises à jour
- ✅ Gestion des canaux
- ✅ État de la flotte
- ✅ Diagnostics
- ✅ Interface CLI et GUI
- ✅ Système de profils
- ✅ Support Windows/Linux/macOS

---

**Documentation complète v1.0.0** | Mise à jour : 2026-02-04
