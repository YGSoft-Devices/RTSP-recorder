# 🔧 Updates Manager Tool - API Server Reference

**Cible** : Administrateurs et développeurs Meeting Backend  
**Langage** : PHP 7.4+  
**Authentification** : Bearer Token (user token)

---

## 📋 Table des matières

1. [Architecture API](#architecture-api)
2. [Installation côté serveur](#installation-côté-serveur)
3. [Configuration](#configuration)
4. [Authentification](#authentification)
5. [Endpoints](#endpoints)
6. [Structure des données](#structure-des-données)
7. [Gestion des permissions](#gestion-des-permissions)
8. [Exemples cURL](#exemples-curl)
9. [Troubleshooting](#troubleshooting)

---

## Architecture API

### Structure fichiers

```
/var/www/meeting-backend/
├── api/
│   ├── index.php                          # Router API
│   ├── config.php                         # Configuration
│   ├── log_helpers.php                    # Logging
│   └── controllers/
│       └── AdminUpdateController.php      # Contrôleur updates
├── admin/
│   └── updates_manager.php                # Interface web admin
└── .htaccess                              # Apache rules
```

### Architecture de contrôle

```
Request HTTP
    ↓
.htaccess (rewrite)
    ↓
api/index.php (router)
    ↓
api/controllers/AdminUpdateController.php
    ↓
Fichiers /var/meeting/published/
+ MySQL (metadata)
    ↓
JSON Response
```

---

## Installation côté serveur

### Prérequis

- **Apache 2.4+** avec modules :
  - `mod_rewrite` (URL rewriting)
  - `mod_php` ou PHP-FPM
- **PHP 7.4+** avec extensions :
  - `ext-json` (gestion JSON)
  - `ext-pdo` (database)
- **MySQL 5.7+**
- **Espace disque** : `/var/meeting/` doit être accessible en lecture/écriture par www-data

### Étapes d'installation

#### 1. Créer la structure de répertoires

```bash
ssh root@meeting.ygsoft.fr

mkdir -p /var/meeting/published
chmod 755 /var/meeting
chmod 755 /var/meeting/published

# Créer les répertoires par type (exemple)
mkdir -p /var/meeting/published/RTSP-Recorder/{232,beta,alpha}
mkdir -p /var/meeting/published/Jupiter/other
chown www-data:www-data -R /var/meeting/published
```

#### 2. Vérifier l'installation PHP

```bash
php -v
php -m | grep -i json  # Doit être présent
```

#### 3. Configuration Apache

Le `.htaccess` doit contenir :

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^api(.*)$ api/index.php [QSA,L]
</IfModule>

# Important : Passer le header Authorization
<IfModule mod_setenvif.c>
    SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1
</IfModule>
```

#### 4. Déployer les fichiers

```bash
# Depuis le repo local
cd ~/Meeting/YG-meeting

# Copier via SCP (voir meeting_server_scp.ps1)
scp api/controllers/AdminUpdateController.php \
    www-user@meeting.ygsoft.fr:/var/www/meeting-backend/api/controllers/

scp api/.htaccess www-user@meeting.ygsoft.fr:/var/www/meeting-backend/

scp admin/updates_manager.php \
    www-user@meeting.ygsoft.fr:/var/www/meeting-backend/admin/
```

#### 5. Tester l'API

```bash
# Localement ou via proxy
curl -I https://meeting.ygsoft.fr/api/admin/update-channels \
     -H "Authorization: Bearer <token>"

# Doit répondre 200
```

---

## Configuration

### Fichier `api/config.php`

```php
<?php
// Base de données
define('DB_HOST', $_ENV['DB_HOST'] ?? 'localhost');
define('DB_USER', $_ENV['DB_USER'] ?? 'meeting_user');
define('DB_PASS', $_ENV['DB_PASS'] ?? '');
define('DB_NAME', $_ENV['DB_NAME'] ?? 'meeting_db');

// Published root (pour fichiers)
define('PUBLISHED_ROOT', '/var/meeting/published');

// API timeout
define('API_TIMEOUT', 20);

// Logging
define('LOG_LEVEL', $_ENV['LOG_LEVEL'] ?? 'INFO'); // DEBUG, INFO, WARN, ERROR
define('LOG_FILE', '/var/log/meeting/api-updates.log');

// CORS
define('CORS_ALLOWED_ORIGINS', [
    'http://localhost:3000',
    'https://meeting.ygsoft.fr',
    'https://*.ygsoft.fr'
]);
```

### Variables d'environnement (`.env`)

```bash
DB_HOST=localhost
DB_USER=meeting_user
DB_PASS=secure_password_here
DB_NAME=meeting_db

LOG_LEVEL=INFO
LOG_FILE=/var/log/meeting/api-updates.log
```

### Tables MySQL

#### `update_channels`

```sql
CREATE TABLE update_channels (
    id INT PRIMARY KEY AUTO_INCREMENT,
    device_type VARCHAR(128) NOT NULL,
    distribution VARCHAR(128) NOT NULL,
    channel VARCHAR(128) DEFAULT 'default',
    target_version VARCHAR(64) NOT NULL,
    active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_channel (device_type, distribution, channel),
    INDEX idx_active (active),
    INDEX idx_device_type (device_type)
);
```

#### `devices`

```sql
CREATE TABLE devices (
    id INT PRIMARY KEY AUTO_INCREMENT,
    device_key VARCHAR(256) UNIQUE NOT NULL,
    device_type VARCHAR(128) NOT NULL,
    distribution VARCHAR(128) NOT NULL,
    installed_version VARCHAR(64),
    last_seen DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_device_type (device_type),
    INDEX idx_last_seen (last_seen)
);
```

#### `device_update_attempts`

```sql
CREATE TABLE device_update_attempts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    device_id INT NOT NULL,
    from_version VARCHAR(64),
    to_version VARCHAR(64) NOT NULL,
    status ENUM('PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED') DEFAULT 'PENDING',
    message TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    INDEX idx_status (status),
    INDEX idx_device_id (device_id)
);
```

#### `builder_users`

```sql
CREATE TABLE builder_users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(255),
    token VARCHAR(32) UNIQUE NOT NULL,
    token_expires_at DATETIME,
    permissions JSON,
    active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_token (token),
    INDEX idx_active (active)
);
```

---

## Authentification

### Flux d'authentification

```
Client request
    ↓
Extract Authorization header
    ↓
getallheaders() → apache_request_headers() → $_SERVER['HTTP_AUTHORIZATION']
    ↓
Parse "Bearer <token>"
    ↓
SELECT * FROM builder_users WHERE token = '<token>'
    ↓
Check token validity (not expired, user active)
    ↓
Extract user permissions (JSON field)
    ↓
Verify permission 'updates:publish' or 'admin:full'
    ↓
Allow/Deny
```

### Classe `getAuthorizationHeader()`

Source : `api/controllers/AdminUpdateController.php`

```php
private function getAuthorizationHeader() {
    $headers = null;
    
    // Méthode 1 : getallheaders() (PHP built-in)
    if (function_exists('getallheaders')) {
        $headers = getallheaders();
        if (isset($headers['Authorization'])) {
            return $headers['Authorization'];
        }
    }
    
    // Méthode 2 : apache_request_headers() (Apache)
    if (function_exists('apache_request_headers')) {
        $headers = apache_request_headers();
        if (isset($headers['Authorization'])) {
            return $headers['Authorization'];
        }
    }
    
    // Méthode 3 : Nginx / PHP-FPM via FastCGI
    if (!empty($_SERVER['HTTP_AUTHORIZATION'])) {
        return $_SERVER['HTTP_AUTHORIZATION'];
    }
    
    // Méthode 4 : Environnement Apache (SetEnvIf)
    if (!empty($_SERVER['REDIRECT_HTTP_AUTHORIZATION'])) {
        return $_SERVER['REDIRECT_HTTP_AUTHORIZATION'];
    }
    
    return null;
}
```

### Validation du token

```php
private function requireAuth() {
    $authHeader = $this->getAuthorizationHeader();
    
    if (!$authHeader || !preg_match('/Bearer\s+(.+)$/i', $authHeader, $m)) {
        $this->sendError('AUTH_MISSING', 'Authorization header missing or invalid', 401);
    }
    
    $token = $m[1];
    
    // Chercher le token en BDD
    $query = "SELECT * FROM builder_users WHERE token = ? AND active = 1";
    $stmt = $this->pdo->prepare($query);
    $stmt->execute([$token]);
    $user = $stmt->fetch(PDO::FETCH_ASSOC);
    
    if (!$user) {
        $this->sendError('AUTH_DENIED', 'Invalid token', 401);
    }
    
    // Checker expiration
    if ($user['token_expires_at'] && strtotime($user['token_expires_at']) < time()) {
        $this->sendError('AUTH_EXPIRED', 'Token expired', 401);
    }
    
    // Retourner l'utilisateur authentifié
    return $user;
}
```

### Gestion des permissions

```php
private function checkPermission($user, $permission) {
    $perms = json_decode($user['permissions'] ?? '[]', true);
    
    // Admin a tous les droits
    if (in_array('admin:full', $perms)) {
        return true;
    }
    
    // Vérifier la permission spécifique
    return in_array($permission, $perms);
}

// Utilisation
$user = $this->requireAuth();
$this->checkPermission($user, 'updates:publish')
    or $this->sendError('FORBIDDEN', 'Insufficient permissions', 403);
```

---

## Endpoints

### 1. `GET /api/admin/update-channels`

Liste les canaux de distribution.

**Authentification** : Requis  
**Permission** : `updates:view` (ou `admin:full`)

**Query parameters**
```
page=1           (optionnel, default: 1)
page_size=50     (optionnel, default: 50)
active=1         (optionnel, filter by active status)
device_type=...  (optionnel, filter by device type)
```

**Exemple de requête**
```bash
curl -H "Authorization: Bearer abc123" \
     "https://meeting.ygsoft.fr/api/admin/update-channels?page=1&page_size=10"
```

**Réponse 200 OK**
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
      "created_at": "2026-02-01T12:00:00Z",
      "updated_at": "2026-02-04T14:30:22Z"
    },
    {
      "id": 2,
      "device_type": "Jupiter",
      "distribution": "other",
      "channel": "default",
      "target_version": "1.0.0",
      "active": 0,
      "created_at": "2026-01-15T08:00:00Z",
      "updated_at": "2026-02-01T10:15:00Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 50
}
```

**Réponse 401 Unauthorized**
```json
{
  "ok": false,
  "error": "AUTH_MISSING",
  "message": "Authorization header missing or invalid"
}
```

---

### 2. `POST /api/admin/updates/publish`

Publier une nouvelle mise à jour.

**Authentification** : Requis  
**Permission** : `updates:publish`  
**Content-Type** : `multipart/form-data`

**Form fields**
```
device_type   (string, required)    Device type name
distribution  (string, required)    Distribution channel
version       (string, required)    Version number
manifest      (file, required)      manifest.json
archive       (file, required)      Update archive (tar.gz or zip)
signature     (file, optional)      manifest.sig
```

**Exemple de requête**
```bash
curl -X POST \
  -H "Authorization: Bearer abc123" \
  -F "device_type=RTSP-Recorder" \
  -F "distribution=232" \
  -F "version=2.33.07" \
  -F "manifest=@manifest.json" \
  -F "archive=@rpi-cam-update_2.33.07.tar.gz" \
  "https://meeting.ygsoft.fr/api/admin/updates/publish"
```

**Réponse 200 OK**
```json
{
  "ok": true,
  "message": "Published successfully",
  "path": "RTSP-Recorder/232/2.33.07",
  "manifest_url": "https://meeting.ygsoft.fr/published/RTSP-Recorder/232/2.33.07/manifest.json",
  "archive_url": "https://meeting.ygsoft.fr/published/RTSP-Recorder/232/2.33.07/rpi-cam-update_2.33.07_20260204_143022.tar.gz",
  "size_bytes": 512345
}
```

**Réponse 400 Bad Request**
```json
{
  "ok": false,
  "error": "VALIDATION_FAILED",
  "message": "Invalid device_type format",
  "details": {
    "device_type": "Must match [A-Za-z0-9._-]{1,128}"
  }
}
```

**Réponse 413 Payload Too Large**
```json
{
  "ok": false,
  "error": "FILE_TOO_LARGE",
  "message": "Archive exceeds maximum size (100 MB)"
}
```

---

### 3. `GET /api/admin/updates/verify`

Vérifier l'existence et l'intégrité des artefacts.

**Authentification** : Requis (optionnel pour lecture)  
**Permission** : Aucune (endpoint public)

**Query parameters**
```
device_type   (string, required)    Device type
distribution  (string, required)    Distribution
version       (string, required)    Version
```

**Exemple de requête**
```bash
curl "https://meeting.ygsoft.fr/api/admin/updates/verify?device_type=RTSP-Recorder&distribution=232&version=2.33.07"
```

**Réponse 200 OK**
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
    "sha256": "5a61aa0df2eb597c9ecf28c8a1a6a571b2d8a3b38f67bed1deaf1dc2bea8e8cd",
    "size": 512345,
    "notes": "v2.33.07: Fixed RTSP stream handling, improved error logging",
    "created_at": "2026-02-04T14:30:22Z"
  },
  "changelog": "- Fix RTSP connection issues (issue #234)\n- Improve error handling\n- Add debug logging",
  "manifest_url": "https://meeting.ygsoft.fr/published/RTSP-Recorder/232/2.33.07/manifest.json",
  "archive_url": "https://meeting.ygsoft.fr/published/RTSP-Recorder/232/2.33.07/rpi-cam-update_2.33.07_20260204_143022.tar.gz"
}
```

**Réponse 404 Not Found**
```json
{
  "ok": false,
  "error": "NOT_FOUND",
  "message": "Update not found",
  "manifest_exists": false,
  "archive_exists": false
}
```

---

### 4. `GET /api/admin/updates/device-types`

Lister tous les device types et distributions disponibles.

**Authentification** : Non requis  
**Permission** : Aucune

**Exemple de requête**
```bash
curl "https://meeting.ygsoft.fr/api/admin/updates/device-types"
```

**Réponse 200 OK**
```json
{
  "ok": true,
  "device_types": {
    "RTSP-Recorder": {
      "distributions": ["232", "beta", "alpha"],
      "latest_versions": {
        "232": "2.33.06",
        "beta": "2.33.07",
        "alpha": "2.34.00-rc1"
      }
    },
    "Jupiter": {
      "distributions": ["other", "stable"],
      "latest_versions": {
        "other": "1.0.0",
        "stable": "0.9.5"
      }
    },
    "RTSP-Viewer": {
      "distributions": ["alpha"],
      "latest_versions": {
        "alpha": "2.0.0"
      }
    }
  },
  "total_types": 3,
  "total_versions": 8
}
```

---

### 5. `GET /api/admin/updates/versions`

Lister les versions disponibles pour un type/distribution.

**Authentification** : Non requis  
**Permission** : Aucune

**Query parameters**
```
device_type   (string, required)    Device type
distribution  (string, required)    Distribution
limit         (int, optional)       Max results (default: 20)
```

**Exemple de requête**
```bash
curl "https://meeting.ygsoft.fr/api/admin/updates/versions?device_type=RTSP-Recorder&distribution=232&limit=10"
```

**Réponse 200 OK**
```json
{
  "ok": true,
  "device_type": "RTSP-Recorder",
  "distribution": "232",
  "versions": [
    "2.33.07",
    "2.33.06",
    "2.33.05",
    "2.33.04",
    "2.33.03"
  ],
  "total": 5
}
```

---

### 6. `GET /api/admin/device-updates`

État de la flotte de devices.

**Authentification** : Requis  
**Permission** : `fleet:view`

**Query parameters**
```
page=1           (optionnel, default: 1)
page_size=50     (optionnel, default: 50)
state=OUTDATED   (optionnel, filter: UP_TO_DATE, OUTDATED, IN_PROGRESS, FAILED, UNKNOWN)
device_type=...  (optionnel, filter by type)
search=...       (optionnel, search in device_key)
```

**Exemple de requête**
```bash
curl -H "Authorization: Bearer abc123" \
     "https://meeting.ygsoft.fr/api/admin/device-updates?state=OUTDATED&page=1&page_size=20"
```

**Réponse 200 OK**
```json
{
  "ok": true,
  "items": [
    {
      "device_key": "ABC123DEF456GHI789JKL012",
      "device_type": "RTSP-Recorder",
      "distribution": "232",
      "last_seen": "2026-02-04T14:15:30Z",
      "installed_version": "2.33.06",
      "target_version": "2.33.07",
      "update_status": "AVAILABLE",
      "state": "OUTDATED",
      "last_attempt_at": "2026-02-03T22:00:00Z",
      "last_attempt_status": "FAILED"
    },
    {
      "device_key": "XYZ789ABC123DEF456GHI012",
      "device_type": "RTSP-Recorder",
      "distribution": "232",
      "last_seen": "2026-02-04T13:45:00Z",
      "installed_version": "2.33.05",
      "target_version": "2.33.07",
      "update_status": "AVAILABLE",
      "state": "OUTDATED",
      "last_attempt_at": null,
      "last_attempt_status": null
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 50,
  "stats": {
    "up_to_date": 2,
    "outdated": 2,
    "in_progress": 0,
    "failed": 0,
    "unknown": 0
  }
}
```

---

### 7. `GET /api/admin/device-update-history`

Historique des mises à jour.

**Authentification** : Requis  
**Permission** : `fleet:view`

**Query parameters**
```
page=1           (optionnel, default: 1)
page_size=50     (optionnel, default: 50)
device_key=...   (optionnel, filter by device)
device_type=...  (optionnel, filter by type)
status=SUCCESS   (optionnel, filter: SUCCESS, FAILED, IN_PROGRESS, PENDING)
```

**Exemple de requête**
```bash
curl -H "Authorization: Bearer abc123" \
     "https://meeting.ygsoft.fr/api/admin/device-update-history?status=SUCCESS&page=1"
```

**Réponse 200 OK**
```json
{
  "ok": true,
  "items": [
    {
      "id": 234,
      "device_key": "ABC123DEF456GHI789JKL012",
      "device_type": "RTSP-Recorder",
      "device_distribution": "232",
      "from_version": "2.33.05",
      "to_version": "2.33.06",
      "status": "SUCCESS",
      "started_at": "2026-02-03T10:00:00Z",
      "completed_at": "2026-02-03T10:05:30Z",
      "duration_seconds": 330,
      "message": ""
    },
    {
      "id": 233,
      "device_key": "XYZ789ABC123DEF456GHI012",
      "device_type": "RTSP-Recorder",
      "device_distribution": "232",
      "from_version": "2.33.06",
      "to_version": "2.33.07",
      "status": "FAILED",
      "started_at": "2026-02-03T22:00:00Z",
      "completed_at": "2026-02-03T22:01:15Z",
      "duration_seconds": 75,
      "message": "Failed to extract archive"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 50
}
```

---

## Structure des données

### Format du manifest.json

```json
{
  "version": "2.33.07",
  "device_type": "RTSP-Recorder",
  "distribution": "232",
  "archive": "rpi-cam-update_2.33.07_20260204_143022.tar.gz",
  "sha256": "5a61aa0df2eb597c9ecf28c8a1a6a571b2d8a3b38f67bed1deaf1dc2bea8e8cd",
  "size": 512345,
  "notes": "v2.33.07: Fixed RTSP stream handling, improved error logging",
  "created_at": "2026-02-04T14:30:22Z"
}
```

### Stockage des fichiers

```
/var/meeting/published/
└── {device_type}/                        # Ex: RTSP-Recorder
    └── {distribution}/                   # Ex: 232
        └── {version}/                    # Ex: 2.33.07
            ├── manifest.json             # Métadonnées (obligatoire)
            ├── {archive_name}            # Archive update (obligatoire)
            ├── CHANGELOG.md              # Notes (optionnel)
            └── manifest.sig              # Signature (optionnel)
```

### Permissions JSON (builder_users table)

```json
[
  "admin:full",
  "updates:publish",
  "updates:view",
  "fleet:view",
  "fleet:manage",
  "channels:edit"
]
```

---

## Gestion des permissions

### Hiérarchie des permissions

| Permission | Accès |
|------------|-------|
| `admin:full` | Toutes les actions (surpasse tout) |
| `updates:publish` | Publier des mises à jour |
| `updates:view` | Lire les canaux et versions |
| `fleet:view` | Voir l'état des devices |
| `fleet:manage` | Modifier les assignations |
| `channels:edit` | Créer/modifier les canaux |

### Assignation de permissions

```bash
# Via l'admin Meeting
ssh root@meeting.ygsoft.fr
mysql meeting_db -e "
UPDATE builder_users 
SET permissions = JSON_ARRAY('updates:publish', 'updates:view', 'fleet:view')
WHERE username = 'dev-user'
"
```

---

## Exemples cURL

### Lister les canaux

```bash
TOKEN="abc123def456"
curl -H "Authorization: Bearer $TOKEN" \
     "https://meeting.ygsoft.fr/api/admin/update-channels"
```

### Publier une mise à jour

```bash
TOKEN="abc123def456"

curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "device_type=RTSP-Recorder" \
  -F "distribution=232" \
  -F "version=2.33.07" \
  -F "manifest=@manifest.json" \
  -F "archive=@update.tar.gz" \
  "https://meeting.ygsoft.fr/api/admin/updates/publish"
```

### Vérifier une mise à jour

```bash
curl "https://meeting.ygsoft.fr/api/admin/updates/verify?device_type=RTSP-Recorder&distribution=232&version=2.33.07" | jq
```

### Récupérer l'état de la flotte

```bash
TOKEN="abc123def456"

curl -H "Authorization: Bearer $TOKEN" \
     "https://meeting.ygsoft.fr/api/admin/device-updates?page=1&page_size=10" | jq
```

### Filter et comptabiliser les devices outdated

```bash
TOKEN="abc123def456"

curl -s -H "Authorization: Bearer $TOKEN" \
     "https://meeting.ygsoft.fr/api/admin/device-updates?state=OUTDATED" | \
  jq '.items | length'
```

---

## Troubleshooting

### ❌ `curl: (60) SSL certificate problem`

**Cause** : Certificat SSL invalide ou auto-signé

**Solutions**
```bash
# 1. Accepter le certificat (dev only)
curl -k https://meeting.ygsoft.fr/api/...

# 2. Ajouter le certificat à la chaîne CA
# Voir la doc de déploiement serveur
```

### ❌ `"error": "AUTH_MISSING"`

**Cause** : Header Authorization manquant ou mal formé

```bash
# ✅ Bon format
curl -H "Authorization: Bearer <token>" https://...

# ❌ Mauvais format
curl -H "Authorization: <token>" https://...       # Sans "Bearer"
curl -H "Auth: <token>" https://...               # Mauvais header
```

### ❌ `"error": "VALIDATION_FAILED"`

**Cause** : Les paramètres ne passent pas la validation

**Règles de validation**
- `device_type`, `distribution` : `[A-Za-z0-9._-]{1,128}`
- `version` : `[A-Za-z0-9._-]{1,64}`
- Archive : Max 100 MB, format tar.gz ou zip

```bash
# ✅ Valide
device_type=RTSP-Recorder  # Tirets OK
version=2.33.07            # Points OK
distribution=232           # Chiffres OK

# ❌ Invalide
device_type="RTSP Recorder" # Espaces non permis
version="2.33.07 final"    # Espaces non permis
```

### ❌ `"error": "FILE_TOO_LARGE"`

**Cause** : Archive > 100 MB

**Solution** : Compresser davantage
```bash
# Vérifier la taille
ls -lh rpi-cam-update.tar.gz

# Recompresser si possible
tar czf rpi-cam-update.tar.gz -C build .
```

### ❌ `"error": "DISK_FULL"`

**Cause** : Espace disque insuffisant sur le serveur

**Solution sur le serveur**
```bash
df -h /var/meeting/
# Si < 10% libre, nettoyer les anciennes versions
find /var/meeting/published -type d -mtime +30 -exec rm -rf {} \;
```

### ❌ Fichiers manifest.json corrompus

**Symptôme** : Erreur 500 lors de `/api/admin/updates/verify`

**Solution** : Vérifier le format

```bash
# Sur le serveur
ssh root@meeting.ygsoft.fr
cat /var/meeting/published/RTSP-Recorder/232/2.33.07/manifest.json | jq

# Si invalide, le rejq, sinon recréer
python3 -c "
import json
m = {
  'version': '2.33.07',
  'device_type': 'RTSP-Recorder',
  ...
}
print(json.dumps(m, indent=2))
" > /var/meeting/published/RTSP-Recorder/232/2.33.07/manifest.json
```

### 🐌 Réponses API lentes

**Cause** : Grande flotte (1000+ devices), requête sans pagination

**Solution**
```bash
# ❌ Lent
curl "https://meeting.ygsoft.fr/api/admin/device-updates"

# ✅ Rapide
curl "https://meeting.ygsoft.fr/api/admin/device-updates?page=1&page_size=50"

# Filter aussi
curl "https://meeting.ygsoft.fr/api/admin/device-updates?device_type=RTSP-Recorder&page=1"
```

---

## Ressources supplémentaires

- [Updates Manager Tool - Guide utilisateur](./DOCUMENTATION.md)
- [Meeting Server - Architecture globale](../docs/structure_globale.md)
- [MySQL Setup](../docs/mysql_setup.md)

---

**API Reference v1.0.0** | Mise à jour : 2026-02-04
