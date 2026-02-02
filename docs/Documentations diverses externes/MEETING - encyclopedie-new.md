# Meeting — Encyclopédie technique (vérifiée)

Dernière vérification : 2026-02-02

## Sources de vérité utilisées

- Code local (autorité d’implémentation)
  - Backend PHP : `api/index.php`, `api/controllers/*.php`, `api/config.php`
  - Reverse tunnel : `reverse_tunnel/server/proxy.js`, `reverse_tunnel/devices/ygs-agent.js`
  - Proxy historique (à comparer) : `YG-proxy/proxy.js`
- API live (autorité opérationnelle)
  - GET https://meeting.ygsoft.fr/api → 200, `{ "status": "Meeting API ready", "version": "3.3.1" }`
  - GET https://meeting.ygsoft.fr/api/metrics?action=get → 200, clés `success`, `metrics`
  - GET https://meeting.ygsoft.fr/api/tunnels → 200, `{ "tunnels": [...] }`
  - GET https://meeting.ygsoft.fr/api/ssh-hostkey → 200, texte `ssh-keyscan` compatible

> Toute information non confirmée par le code ou l’API live est exclue de ce document.

---

## 1) Présentation générale

Meeting est un backend REST (PHP) pour orchestrer des devices IoT/Edge derrière NAT via des tunnels inversés. Le cœur fonctionnel combine :

- Provisioning et gestion des devices (clés, tokens, type, distribution, notes).
- Gestion des tunnels reverse (SSH/HTTP/VNC/SCP/relay) via une base SQL et un proxy Node.
- Heartbeat/last_seen pour la disponibilité.
- Gestion des clés SSH devices et clés utilisateurs.
- Logs de connexions device et métriques système.
- Distrib Builder (workflow de build/packaging).

---

## 2) Architecture globale

### 2.1 Backend PHP (API REST)

Point d’entrée unique : `api/index.php`.

Contrôleurs principaux :
- `DeviceController` (devices, services, notes, distrib.json, liste)
- `TunnelController` (tunnels, autorisation, statut)
- `StatusController` (heartbeat/online)
- `DeviceAvailabilityController` (availability)
- `DeviceLogsController` (logs)
- `DeviceRelationController` (parent/ghost/bundles/serial/type)
- `FlashController` (flash, distributions, files)
- `SshKeysController` (clés SSH devices + hostkey)
- `ForceCommandController` (clé device, port tunnel)
- `DeviceTypeController` (CRUD device_types)
- `MetricsController` (metrics système)
- `UserController` (builder_users)
- `BuilderController` (Distrib Builder)

### 2.2 Reverse tunnel (Node.js)

#### ygs-proxy (serveur) — `reverse_tunnel/server/proxy.js`
- Ouvre un port de contrôle (9001/TCP) pour les agents.
- Synchronise les tunnels publics en lisant `GET /api/tunnels`.
- Écoute les ports publics déclarés en base (plage 9050–9130 par défaut).
- Chaque connexion publique est relayée via le socket agent du device correspondant.

#### ygs-agent (device) — `reverse_tunnel/devices/ygs-agent.js`
- Maintient une connexion de contrôle vers le proxy.
- Envoie un heartbeat régulier vers l’API : `POST /api/devices/{device_key}/online`.
- Gère la clé SSH device :
  - upload `PUT /api/devices/{device_key}/ssh-key`
  - fetch `GET /api/forcecommand/get_device_key?device_key=...`
  - sync hostkey `GET /api/ssh-hostkey`

---

## 3) Concepts fondamentaux

### 3.1 Device
- Identifié par `device_key`.
- Champs clés : `authorized`, `token_code`, `token_count`, `device_type`, `distribution`, `last_seen`, `services`.

### 3.2 Services
- Services supportés côté API tunnel : `ssh`, `http`, `vnc`, `scp`, `relay`.
- `debug` est un service déclaratif (exposé via API, mais ne déclenche pas un tunnel).

### 3.3 Tunnels reverse
- Gestion centralisée par la table SQL `tunnel_ports`.
- Le proxy lit `/api/tunnels` et ouvre les ports publics correspondants.

### 3.4 Heartbeat / disponibilité
- Heartbeat : `POST /api/devices/{device_key}/online`.
- Disponibilité : `GET /api/devices/{device_key}/availability`.

### 3.5 Clés SSH
- Clé publique device via `PUT /api/devices/{device_key}/ssh-key`.
- Hostkey serveur via `GET /api/ssh-hostkey`.
- Listing admin via `GET /api/ssh-keys`.

### 3.6 Distrib / Flash
- Types/distributions stockés dans un arbre de répertoires (`flash_storage_root`).
- Upload multi-part via `/api/flash/upload`.

---

## 4) Sécurité & authentification

### 4.1 Endpoints sans authentification applicative
La majorité de l’API n’impose aucune authentification côté code (ex. devices, tunnels, flash, metrics). L’accès doit être protégé au niveau réseau.

### 4.2 Endpoints protégés

- **Distrib Builder** (`/api/builder/*`) :
  - Auth par header `Authorization: Bearer <token>`.
  - Le token est validé contre `builder_users.token` ou `builder_api_token` (config).

- **SSH keys (lecture pour serveur SSH)** :
  - `GET /api/ssh-keys?user=...` et `GET /api/ssh-keys/devices?user=...`
  - Token `X-Meeting-Ssh-Token` requis **ou** accès depuis `127.0.0.1/::1`.

- **Clés utilisateurs** :
  - `GET /api/users/authorized-keys` accessible **uniquement** depuis localhost.

---

## 5) Référence API REST (vérifiée)

> Chaque endpoint est confirmé par le code local. L’état « API live » est indiqué lorsqu’il a été testé sur https://meeting.ygsoft.fr.

### 5.1 Statut général

**GET /api**
- Rôle : statut API.
- Auth : aucune.
- Réponse : `{ "status": "Meeting API ready", "version": "3.3.1" }`.
- Source : `api/index.php`.
- API live : testé (200).

---

### 5.2 Tunnels

**GET /api/tunnels**
- Rôle : liste des tunnels actifs (table `tunnel_ports`).
- Auth : aucune.
- Réponse : `{ "tunnels": [ { device_key, service, port, local_port, expires_at }, ... ] }`.
- Source : `TunnelController::listTunnels`.
- API live : testé (200).

**POST /api/devices/{device_key}/service**
- Rôle : demander un tunnel reverse pour un device.
- Auth : aucune.
- Body JSON : `{ "service": "ssh|http|vnc|scp|relay", "port": <int> }` (`port` obligatoire pour `relay`).
- Réponse : `{ "port": <int>, "url": <string>, "expires_at": <string|null> }`.
- Erreurs :
  - 400 `Missing service param` ou `Missing relay port`
  - 403 `Device not authorized` / `Device missing token`
  - 404 `Device not found`
  - 503 `No available port in range`
  - 500 `DB error`
- Source : `TunnelController::createTunnel`.
- API live : non testé.

**POST /api/devices/{device_key}/authorize-tunnel**
- Rôle : pré‑check autorisation + tokens.
- Auth : aucune.
- Body JSON : non requis.
- Réponse : `{ ok: true, device_key, authorized, token_code, token_count, distribution, registered_at }`.
- Erreurs : 404 `Device not found`, 403 `Device not authorized` / `No tokens left`.
- Source : `TunnelController::authorizeTunnel`.
- API live : non testé.

**GET /api/devices/{device_key}/tunnel-pending**
- Rôle : lecture d’une demande de tunnel via fichier `tunnel_requests_dir`.
- Auth : aucune.
- Réponse : `{ "pending": false }` ou `{ "pending": true, "request": {...} }`.
- Source : `TunnelController::getPendingTunnel`.
- API live : non testé.

**POST /api/devices/{device_key}/tunnel-status**
- Rôle : enregistrement du statut de tunnel (fichier `tunnel_status_dir`).
- Body JSON : `{ service, port, url, upnp, error }`.
- Réponse : `{ ok: true, status: {...} }`.
- Erreurs : 400 `Missing service param`.
- Source : `TunnelController::setTunnelStatus`.
- API live : non testé.

---

### 5.3 Devices

**GET /api/devices**
- Rôle : listing paginé des devices.
- Query : `limit` (1..100), `offset` (>=0), `prefix` (filtre device_key).
- Réponse : `{ devices: [...], total, limit, offset }`.
- Source : `DeviceController::listDevices`.
- API live : non testé.

**GET /api/devices/generate-key**
- Rôle : génération d’un device_key et token_code non enregistrés.
- Réponse : `{ devicekey, token_code }`.
- Source : `DeviceController::generateDeviceKey`.
- API live : non testé.

**POST /api/devices/generate-and-register**
- Rôle : génération + insertion device.
- Réponse : `{ devicekey, token_code, ap_ssid, ap_password, http_pw_low, http_pw_medium, http_pw_high }`.
- Source : `DeviceController::generateAndRegisterDevice`.
- API live : non testé.

**POST /api/devices/manual-create**
- Rôle : création manuelle.
- Body JSON : `{ devicekey, token_code, device_type, distribution, product_serial? }`.
- Réponse : `{ devicekey, token_code, ap_ssid, ap_password, http_pw_*, device_type, distribution, product_serial }`.
- Erreurs : 400, 409.
- Source : `DeviceController::manualCreateDevice`.
- API live : non testé.

**GET /api/devices/{device_key}**
- Rôle : détails device.
- Réponse : champs device + `services` array.
- Erreurs : 404.
- Source : `DeviceController::getDevice`.
- API live : non testé.

**DELETE /api/devices/{device_key}**
- Rôle : suppression device.
- Réponse : `{ success: true }`.
- Erreurs : 404.
- Source : `DeviceController::deleteDevice`.
- API live : non testé.

**PUT /api/devices/{device_key}**
- Rôle : mise à jour des services actifs.
- Body JSON : `{ services: ["ssh","http","vnc","scp","debug"] }`.
- Réponse : `{ success: true }`.
- Erreurs : 400 `Nothing to update`, 404.
- Source : `DeviceController::updateDevice`.
- API live : non testé.

**GET /api/devices/{device_key}/note**
- Réponse : `{ note: "..." }`.
- Source : `DeviceController::getDeviceNote`.
- API live : non testé.

**PUT /api/devices/{device_key}/note**
- Body JSON : `{ note: "..." }` (max 2000).
- Réponse : `{ success: true, note }`.
- Erreurs : 400, 404.
- Source : `DeviceController::setDeviceNote`.
- API live : non testé.

**GET /api/devices/{device_key}/service**
- Rôle : services actifs du device.
- Réponse : `{ services: ["ssh","vnc","http","scp","debug"] }`.
- Source : `DeviceController::getDeviceServices`.
- API live : non testé.

**GET /api/devices/device-types**
- Rôle : liste des types présents dans `storage_path`.
- Réponse : `{ device_types: [ ... ] }`.
- Source : `DeviceController::getDeviceTypes`.
- API live : non testé.

**GET /api/devices/device-types/{type}/distributions**
- Rôle : liste des distributions d’un type.
- Réponse : `{ distributions: [ ... ] }`.
- Erreurs : 404 type absent.
- Source : `DeviceController::getDistributionsForDeviceType`.
- API live : non testé.

**GET /api/devices/{device_key}/distrib-json**
- Rôle : retourne `distrib.json` de la distribution du device.
- Réponse : JSON libre (contenu du fichier).
- Erreurs : 404 device/distribution ou fichier absent.
- Source : `DeviceController::getDistribJson`.
- API live : non testé.

**PUT /api/devices/{device_key}/distrib-json**
- Rôle : écrit `distrib.json`.
- Body : JSON libre.
- Réponse : `{ success: true }`.
- Erreurs : 400 JSON invalide.
- Source : `DeviceController::setDistribJson`.
- API live : non testé.

---

### 5.4 Logs & disponibilité

**GET /api/devices/{device_key}/logs**
- Rôle : logs de connexions (table `connection_logs`).
- Réponse : tableau JSON (peut être vide).
- Source : `DeviceLogsController::deviceLogs`.
- API live : non testé.

**POST /api/devices/{device_key}/purge-logs**
- Rôle : purge des logs (table `connection_logs`).
- Réponse : `{ success: true }`.
- Source : `DeviceLogsController::purgeLogs`.
- API live : non testé.

**GET /api/devices/{device_key}/availability**
- Rôle : disponibilité basée sur `last_seen` et `device_heartbeat_timeout`.
- Réponse : `{ status: "Available|Disconnected|Unknown", last_heartbeat, since, uptime }`.
- Source : `DeviceAvailabilityController::deviceAvailability`.
- API live : non testé.

---

### 5.5 Heartbeat / status

**POST /api/devices/{device_key}/online**
- Rôle : heartbeat + mise à jour IP/services/note.
- Body JSON (optionnel) :
  - `ip_address`
  - `services`: `{ ssh, vnc, http, scp, debug }`
  - `note`
- Réponse : `{ ok: true, ip_address, last_seen }`.
- Erreurs : 404 device absent.
- Source : `StatusController::deviceOnline`.
- API live : non testé.

**POST /api/status/{device_key}/online**
- Rôle : alias du heartbeat.
- Source : routage `api/index.php` → `StatusController::deviceOnline`.
- API live : non testé.

**GET /api/status/{device_key}/last-seen**
- Rôle : retourne `last_seen`.
- Réponse : `{ device_key, last_seen }`.
- Erreurs : 404.
- Source : `StatusController::deviceLastSeen`.
- API live : non testé.

---

### 5.6 Relations device

**PUT /api/devices/{device_key}/parent**
- Body JSON : `{ parent_device_key }`.
- Réponse : `{ success: true, parent_device_key }`.
- Source : `DeviceRelationController::setParentDevice`.

**PUT /api/devices/{device_key}/ghost**
- Body JSON : `{ ghost_candidate_url }`.
- Réponse : `{ success: true, ghost_candidate_url }`.
- Source : `DeviceRelationController::setGhostCandidate`.

**PUT /api/devices/{device_key}/bundles**
- Body JSON : `{ bundles: [...] }` (stocké en JSON string).
- Réponse : `{ success: true, bundles }`.
- Source : `DeviceRelationController::setBundles`.

**PUT /api/devices/{device_key}/product-serial**
- Body JSON : `{ product_serial }`.
- Réponse : `{ success: true, product_serial }`.
- Source : `DeviceRelationController::setProductSerial`.

**PUT /api/devices/{device_key}/device-type**
- Body JSON : `{ device_type }`.
- Réponse : `{ success: true, device_type }`.
- Source : `DeviceRelationController::setDeviceType`.

---

### 5.7 Flash / distributions

**GET /api/flash/{device_key}/distribution-files**
- Rôle : liste des fichiers de distribution liés au device.
- Réponse : `{ devicetype, distribution, files }`.
- Erreurs : 400/404.
- Source : `FlashController::listDistributionFiles`.

**POST /api/flash/upload** (multipart)
- Champs : `devicetype`, `distribution`, `file`.
- Réponse : `{ success: true, file }`.
- Erreurs : 400/500.
- Source : `FlashController::uploadDistributionFile`.

**POST /api/flash/create-type**
- Body JSON : `{ devicetype }`.
- Réponse : `{ success: true, devicetype }`.
- Erreurs : 400/409/500.
- Source : `FlashController::createDeviceType`.

**POST /api/flash/create-distribution**
- Body JSON : `{ devicetype, distribution }`.
- Réponse : `{ success: true, devicetype, distribution }`.
- Erreurs : 400/409/500.
- Source : `FlashController::createDistribution`.

**DELETE /api/flash/{device_type}/{distribution}/{filename}**
- Réponse : `{ success: true }`.
- Erreurs : 404/500.
- Source : `FlashController::deleteDistributionFile`.

**GET /api/flash/device-types**
- Réponse : `{ device_types: [...] }`.
- Source : `FlashController::listDeviceTypes`.

**GET /api/flash/{device_type}/distributions**
- Réponse : `{ distributions: [...] }`.
- Erreurs : 404.
- Source : `FlashController::listDistributions`.

**POST /api/devices/{device_key}/flash-request**
- Rôle : consomme un token.
- Réponse : `{ success: true, tokens_left }`.
- Erreurs : 403/404/500.
- Source : `FlashController::flashRequest`.

**PUT /api/devices/{device_key}/authorize**
- Body JSON : `{ authorized: 0|1 }`.
- Réponse : `{ success: true, authorized }`.
- Source : `FlashController::setAuthorization`.

**PUT /api/devices/{device_key}/tokens**
- Body JSON : `{ token_count: <int> }`.
- Réponse : `{ success: true, token_count }`.
- Erreurs : 400.
- Source : `FlashController::setTokens`.

**PUT /api/devices/{device_key}/distribution**
- Body JSON : `{ distribution }`.
- Réponse : `{ success: true, distribution }`.
- Source : `FlashController::setDistribution`.

**PUT /api/devices/{device_key}/token-code**
- Body JSON : `{ token_code }`.
- Réponse : `{ success: true, token_code }`.
- Source : `FlashController::setTokenCode`.

---

### 5.8 SSH keys (devices & serveur)

**GET /api/ssh-keys**
- Rôle : liste admin des clés devices.
- Réponse : `{ keys: [ { device_key, ssh_user, pubkey, status, added, modified, fingerprint, last_ssh } ] }`.
- Source : `SshKeysController::getAllDeviceKeys`.

**GET /api/devices/{device_key}/ssh-key**
- Réponse : `{ device_key, ssh_user, pubkey, status, added, modified, fingerprint, last_ssh }`.
- Erreurs : 404.
- Source : `SshKeysController::getSshKey`.

**PUT /api/devices/{device_key}/ssh-key**
- Body JSON : `{ pubkey, ssh_user?, status? }` (`status`: `authorized` ou `revoked`).
- Réponse : `{ success: true }`.
- Effets : met à jour `devices`, synchronise `device_keys`, lance `ygs-KeysSync.sh`.
- Source : `SshKeysController::setDeviceSshKey`.

**DELETE /api/devices/{device_key}/ssh-key**
- Rôle : révocation (soft delete).
- Réponse : `{ success: true }`.
- Source : `SshKeysController::removeSshKey`.

**GET /api/devices/{device_key}/ssh-key-log**
- Rôle : audit local des opérations SSH key.
- Réponse : tableau JSON.
- Source : `SshKeysController::getSshKeyLog`.

**GET /api/devices/{device_key}/private-ppk**
- Rôle : conversion PPK (PuTTY).
- Réponse : fichier binaire, header `X-PPK-Passphrase`.
- Erreurs : 404/500.
- Source : `SshKeysController::getPrivatePpk`.

**GET /api/ssh-keys?user=USERNAME**
- Auth : `X-Meeting-Ssh-Token` ou localhost.
- Réponse : `{ keys: ["ssh-..."] }`.
- Erreurs : 400/401/404.
- Source : `SshKeysController::getAuthorizedKeys`.

**GET /api/ssh-keys/devices?user=USERNAME**
- Auth : `X-Meeting-Ssh-Token` ou localhost.
- Réponse : `{ devices: [ { device_key, ssh_public_key, authorized, revoked } ] }`.
- Source : `SshKeysController::listUserDevicesWithKeys`.

**POST /api/ssh-keys/server**
- Body JSON : `{ pubkey }`.
- Réponse : `{ success: true, fingerprint, date }`.
- Source : `SshKeysController::saveServerPubKey`.

**POST /api/ssh-keys/server/regenerate**
- Rôle : regen clé serveur via script.
- Réponse : `{ success: true, pubkey?, fingerprint?, date? }`.
- Source : `SshKeysController::regenerateServerKey`.

**GET /api/ssh-hostkey**
- Rôle : hostkey(s) serveur en texte `ssh-keyscan`.
- Réponse : texte brut.
- Source : `SshKeysController::getServerHostKeys`.
- API live : testé (200).

---

### 5.9 ForceCommand (ports & clés)

**POST /api/forcecommand/register_device_key**
- Body JSON : `{ device_key, pubkey }`.
- Réponse : `{ status: "ok" }`.
- Source : `ForceCommandController::registerDeviceKey`.

**POST /api/forcecommand/validate_device_key**
- Body JSON : `{ pubkey }`.
- Réponse : `{ status: "ok", device_key }` ou `{ status: "invalid" }` (401).
- Source : `ForceCommandController::validateDeviceKey`.

**GET /api/forcecommand/get_device_key?device_key=...**
- Réponse : texte brut (pubkey) ou `{ status: "not_found" }`.
- Source : `ForceCommandController::getDeviceKey`.

**POST /api/forcecommand/request-port**
- Body JSON (optionnel) : `{ device_key, service?, port? }`.
- Réponse : `{ status: "ok", port }`.
- Erreurs : 400/403/404/503.
- Source : `ForceCommandController::requestTunnelPort`.

**POST /api/devices/{device_key}/request-tunnel-port**
- Alias de `request-port`.
- Source : routage `api/index.php` → `ForceCommandController::requestTunnelPort`.

**DELETE /api/forcecommand/remove_device_key**
- Body JSON : `{ device_key }`.
- Réponse : `{ status: "ok", deleted }` ou `{ status: "not_found", deleted: 0 }`.
- Source : `ForceCommandController::removeDeviceKey`.

---

### 5.10 Device types (table `device_types`)

**GET /api/device-types**
- Réponse : `{ device_types: [...] }` (status != `deleted`).
- Source : `DeviceTypeController::listTypes`.

**POST /api/device-types** (multipart possible)
- Champs : `name`, `serial_prefix`, optionnels (`platform`, `services_default`, `description`, `icon`, `tags`, `default_distribution`, `parent_id`).
- Réponse : `{ success: true, id }`.
- Erreurs : 400/409.
- Source : `DeviceTypeController::createType`.

**PUT /api/device-types/{id}**
- Body : form-data ou urlencoded (support multipart + `icon`).
- Réponse : `{ success: true }`.
- Erreurs : 400/409.
- Source : `DeviceTypeController::updateType`.

**POST /api/device-types/{id}/fork**
- Body : `name`, `serial_prefix`, optionnels + `icon`.
- Réponse : `{ success: true, id }`.
- Erreurs : 400/404/409.
- Source : `DeviceTypeController::forkType`.

**POST /api/device-types/{id}/merge**
- Réponse : `{ success: true }`.
- Erreurs : 400/404.
- Source : `DeviceTypeController::mergeType`.

**DELETE /api/device-types/{id}**
- Rôle : soft delete (`status = 'deleted'`).
- Réponse : `{ success: true }`.
- Source : `DeviceTypeController::deleteType`.

---

### 5.11 Metrics

**GET /api/metrics?action=get**
- Réponse : `{ success: true, metrics: {...} }`.
- Source : `MetricsController::getMetrics`.
- API live : testé (200).

**GET /api/metrics?action=logs[&lines=N]**
- Réponse : `{ success: true, log: [...] }`.
- Source : `MetricsController::getMetricsLogs`.

---

### 5.12 Users (builder_users)

**GET /api/users**
- Réponse : `{ users: [...] }`.
- Source : `UserController::listUsers`.

**GET /api/users/{id}**
- Réponse : `{ id, username, role, token, ssh_pubkey, authorized, created_at }`.
- Erreurs : 404.
- Source : `UserController::getUser`.

**POST /api/users**
- Body JSON : `{ username, password, role?, ssh_pubkey?, authorized? }`.
- Réponse : `{ success: true, id, token }`.
- Source : `UserController::createUser`.

**PUT /api/users/{id}**
- Body JSON partiel.
- Réponse : `{ success: true }`.
- Source : `UserController::updateUser`.

**GET /api/users/authorized-keys**
- Accès : localhost uniquement.
- Réponse : texte brut (clés SSH).
- Source : `UserController::getAuthorizedKeys`.

---

### 5.13 Distrib Builder

Tous les endpoints `/api/builder/*` exigent un header `Authorization`.

**GET /api/builder/whoami**
- Réponse : `{ user }`.

**GET /api/builder/device-types**
- Query : `q`.
- Réponse : `{ device_types: [ { name, desc, icon } ] }`.

**GET /api/builder/distributions?type=...**
- Réponse : `{ distributions: [ { name, last_version } ] }`.

**POST /api/builder/suggest-version**
- Body JSON : `{ device_type, distribution }`.
- Réponse : `{ suggested_version }`.

**POST /api/builder/start**
- Body JSON : manifest initial.
- Réponse : `{ build_id, upload_url, manifest_url }`.

**POST /api/builder/upload-file** (multipart)
- Champs : `build_id`, `type?`, `file`.
- Réponse : `{ success, filename, filetype, path }`.

**GET /api/builder/manifest?build_id=...**
- Réponse : `{ manifest, valid, missing }`.

**POST /api/builder/manifest**
- Body JSON : `{ build_id, manifest }`.
- Réponse : `{ success, valid, missing }`.

**POST /api/builder/package**
- Body JSON : `{ build_id, format? }`.
- Réponse : `{ success, job_id, status_url }`.

**GET /api/builder/package-status?job_id=...**
- Réponse : `{ state, progress, download_url, sha256, log }`.

**GET /api/builder/download/{job_id}**
- Réponse : fichier binaire.

**POST /api/builder/commit**
- Body JSON : `{ job_id, notes? }`.
- Réponse : `{ success, path, published_url }`.

**GET /api/builder/history?type=...&distribution=...**
- Réponse : `{ history: [...] }`.

**POST /api/builder/rollback**
- Body JSON : `{ device_type, distribution, version }`.
- Réponse : `{ success }`.

**POST /api/builder/duplicate**
- Body JSON : `{ device_type, distribution, version, new_version, notes? }`.
- Réponse : `{ success }`.

Sources : `BuilderController` + routage `api/index.php`.

---

## 6) Workflows opérationnels (confirmés par code)

### 6.1 Onboarding device (sans UI)
1. `GET /api/devices/generate-key`
2. `POST /api/devices/manual-create`
3. `PUT /api/devices/{device_key}/ssh-key` (pubkey device)
4. `PUT /api/devices/{device_key}/authorize`
5. `POST /api/devices/{device_key}/online`

### 6.2 Demande d’un tunnel
1. `POST /api/devices/{device_key}/service` avec `{ service: "ssh" }`.
2. Le proxy récupère la réservation via `GET /api/tunnels`.

### 6.3 Heartbeat continu (agent)
- `POST /api/devices/{device_key}/online` à intervalle régulier.

---

## 7) Glossaire

- **device_key** : identifiant unique device.
- **token_code** : code requis pour certains workflows (tunnel).
- **token_count** : compteur de tokens pour flash/tunnel precheck.
- **tunnel_ports** : table SQL des ports réservés.
- **heartbeat** : signal périodique qui met à jour `last_seen`.
- **authorized_keys** : liste de clés SSH autorisées (devices/users).

---

## Annexe – Vérification rapide

> Commandes sans effet de bord (GET/HEAD). Remplacer les placeholders.

- Vérifier statut API
  - `curl -s https://meeting.ygsoft.fr/api`

- Vérifier métriques
  - `curl -s "https://meeting.ygsoft.fr/api/metrics?action=get"`

- Vérifier tunnels actifs
  - `curl -s https://meeting.ygsoft.fr/api/tunnels`

- Vérifier hostkey serveur
  - `curl -s https://meeting.ygsoft.fr/api/ssh-hostkey`

- Vérifier disponibilité d’un device
  - `curl -s https://meeting.ygsoft.fr/api/devices/<DEVICE_KEY>/availability`

- Vérifier clés SSH autorisées (token requis)
  - `curl -s -H "X-Meeting-Ssh-Token: <TOKEN>" "https://meeting.ygsoft.fr/api/ssh-keys?user=<USERNAME>"`

- Vérifier Distrib Builder (token requis)
  - `curl -s -H "Authorization: Bearer <TOKEN>" https://meeting.ygsoft.fr/api/builder/whoami`
