# Meeting — Guide d’intégration device (heartbeats, clés, tunnel)

Dernière vérification : 2026-02-02 (StatusController v1.8.0)

Ce document s’adresse aux développeurs qui ajoutent le support de **Meeting** sur leurs devices.
Il décrit le **minimum viable** côté device : provisioning (device_key), heartbeat, publication de clé SSH, synchronisation de hostkey, et (optionnel) l’agent de tunnel inversé.

> Source de vérité : implémentation actuelle du backend PHP et des agents Node.js.

---

## 1) Concepts (à connaître)

### 1.1 `device_key`
- Identifiant stable du device (utilisé dans toutes les routes REST, dans la base, et par le proxy).
- Le `device_key` **n’est pas un secret** : il circule dans les URLs et peut apparaître dans des logs.

### 1.2 `authorized`
- Booléen côté serveur.
- Tant que `authorized = 0`, plusieurs actions serveur seront refusées (tunnel, ports, etc.).

### 1.3 `token_code` / `token_count`
- `token_code` : secret côté serveur, utilisé dans certains workflows (ex: pré-check tunnel).
- `token_count` : compteur (ex: gating pour certains usages comme tunnel/flash selon endpoints).

Côté device :
- vous n’avez généralement **pas besoin** d’envoyer `token_code` dans les heartbeats.
- vous devez surtout garantir un heartbeat régulier (`last_seen`) pour être considéré “online”.

### 1.4 `last_seen`
- Timestamp UTC mis à jour à chaque heartbeat.
- Utilisé par certaines opérations côté serveur (ex: “device offline (no recent heartbeat)”).

### 1.5 Services (source de vérité : Meeting)

> **⚠️ Important (v1.7.0+)** : Le champ `services` dans le heartbeat est **ignoré** par le serveur.
> Meeting est la **source de vérité** pour les services — les devices ne peuvent pas auto-déclarer leurs services.
> Les services sont gérés exclusivement via l'interface admin Meeting.

Clés existantes côté serveur : `ssh`, `http`, `vnc`, `scp`, `debug`.

---

## 2) Provisioning côté device (ce qui doit exister localement)

### 2.1 `device_key`
L’agent officiel (`ygs-agent`) lit le `device_key` depuis :
- `/etc/meeting/device_info.json`

Exemple :
```json
{
  "device_key": "0123456789abcdef0123456789abcdef"
}
```

### 2.2 Token de contrôle du tunnel (agent ↔ proxy)
Le tunnel inversé utilise un **token de contrôle** (différent de `token_code`).
Dans l’agent officiel, il est stocké dans `reverse_tunnel/devices/config.json` sous la clé `token`.

---

## 3) API REST — endpoints utilisés par un device

Base URL (prod) : `https://meeting.ygsoft.fr`

### 3.1 Heartbeat (présence / last_seen)

**POST** `/api/devices/{device_key}/online`

Objectif :
- mettre à jour `last_seen`
- mettre à jour l’IP côté serveur (`ip_address`)
- optionnellement publier les services et une note

Payload JSON (recommandé) :
```json
{
  "ip_address": "203.0.113.10",
  "ip_lan": "192.168.1.100",
  "ip_public": "203.0.113.10",
  "mac": "AA:BB:CC:DD:EE:FF",
  "cluster_ip": "10.0.0.5",
  "note": "optional short status"
}
```

**Champs réseau supportés (v1.8.0+)** :
| Champ | Format | Description |
|-------|--------|-------------|
| `ip_address` | IPv4/IPv6 | IP principale (fallback: REMOTE_ADDR) |
| `ip_lan` | IPv4/IPv6 | IP LAN du device |
| `ip_public` | IPv4/IPv6 | IP publique détectée par le device |
| `mac` | `AA:BB:CC:DD:EE:FF` | Adresse MAC (format avec `:`) |
| `cluster_ip` | string | IP(s) cluster si applicable |

Notes importantes :
- Tous les champs sont optionnels.
- `ip_address` : s'il est absent, le serveur utilise `REMOTE_ADDR`.
- Les IPs sont validées via `FILTER_VALIDATE_IP`.
- Le MAC est validé par regex `/^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/`.
- **Le champ `services` est ignoré** (voir section 1.5).
- Erreur typique : `404 Device not found` si le `device_key` n’existe pas en base.

Réponse (200) :
```json
{ "ok": true, "ip_address": "…", "last_seen": "2026-02-02 12:34:56" }
```

Recommandations d’implémentation :
- Intervalle : 60s est une valeur de référence (voir `ygs-agent`).
- Retry : backoff progressif (ex: 5s → 30s) sur erreurs réseau.
- Tolérance : en cas de 404, ne spammez pas : remontez une erreur “device non provisionné”.

### 3.2 Synchronisation de la hostkey SSH du serveur

**GET** `/api/ssh-hostkey`

Objectif :
- récupérer la/les clés publiques SSH du serveur au format compatible `ssh-keyscan`
- mettre à jour `known_hosts` côté device

Réponse : `text/plain` (une ligne par clé)

Bonnes pratiques :
- mettre à jour de façon atomique (fichier temporaire + rename)
- protéger contre les écritures concurrentes (lockfile)

### 3.3 Publication de la clé SSH du device

Pré-requis :
- générer une paire de clés (ex: ed25519) si absente

**PUT** `/api/devices/{device_key}/ssh-key`

Payload JSON :
```json
{ "pubkey": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA… comment" }
```

Notes :
- Le backend accepte aussi `ssh_user` et `status` (usage admin), mais côté device `pubkey` suffit.
- En cas de clé invalide : 400.

### 3.4 (Optionnel) Récupération “device key” côté ForceCommand

**GET** `/api/forcecommand/get_device_key?device_key={device_key}`

Réponse :
- `200 text/plain` : la clé publique (si connue)
- `404` : introuvable

Usage typique :
- récupération de la clé publiée côté serveur pour la déposer localement (debug/compat).

---

## 4) Reverse tunnel — intégrer l’agent (optionnel mais recommandé)

Si vous implémentez un agent compatible, vous devez :
- maintenir une connexion TCP persistante vers le proxy (`serverHost:serverPort`, typiquement `9001`)
- gérer un protocole de multiplexing simple (`N`, `D`, `C`)

### 4.1 Handshake (agent → proxy)
À la connexion, envoyer une ligne JSON terminée par `\n` :
```json
{"token":"<TOKEN>","name":"<device_key>"}
```
- `token` : le `token_code` du device (6 caractères hex, visible dans l'admin Meeting)
- `name` : le `device_key` (identification côté proxy)

> **Note (v2.2.0+)** : Le proxy valide le device via l'API Meeting (`GET /api/devices/{device_key}`).
> Le device doit exister et être enregistré pour que la connexion soit acceptée.

Le proxy répond avec une ligne JSON :
```json
{"status":"authenticated","device_key":"<device_key>"}
```
ou en cas d'erreur :
```json
{"error":"auth_failed","reason":"<reason>"}
```

Après authentification, le proxy passe en mode frames binaires.

### 4.2 Frames (proxy ↔ agent)
Chaque frame :
- 1 byte : type ASCII (`'N'`, `'D'`, `'C'`)
- 4 bytes : `streamId` (uint32 big-endian)
- 4 bytes : `payloadLength` (uint32 big-endian)
- N bytes : payload

Types :
- `N` (New stream): payload = `localPort` (uint16 big-endian). Le proxy demande à l’agent d’ouvrir une connexion TCP locale vers `127.0.0.1:localPort`.
- `D` (Data): payload = bytes à forwarder.
- `C` (Close): payload vide. Fermer le stream.

Comportement attendu côté agent :
- Sur `N`: ouvrir un socket local vers `127.0.0.1:localPort`, associer au `streamId`.
- Sur data local → envoyer `D` vers le proxy.
- Sur `D` reçu → écrire dans le socket local.
- Sur close (local ou `C` reçu) → envoyer `C` et nettoyer.

### 4.3 Découverte des ports publics
Le proxy serveur se base sur `GET /api/tunnels` pour savoir quels ports publics écouter.
Côté device, vous n’avez rien à faire : c’est serveur-side.

---

## 5) Checklist d’intégration

- [ ] Le device dispose d’un `device_key` provisionné (fichier local / config).
- [ ] Heartbeat `POST /api/devices/{device_key}/online` toutes les ~60s.
- [ ] Hostkey SSH : `GET /api/ssh-hostkey` périodique + mise à jour `known_hosts`.
- [ ] Clé SSH device : génération + `PUT /api/devices/{device_key}/ssh-key`.
- [ ] (Optionnel) Agent tunnel TCP vers le proxy (port 9001) + multiplexing.

---

## 6) Exemples rapides (curl)

Heartbeat (avec infos réseau) :
```bash
curl -sS -X POST "https://meeting.ygsoft.fr/api/devices/$DEVICE_KEY/online" \
  -H "Content-Type: application/json" \
  -d '{"ip_lan":"192.168.1.100","ip_public":"203.0.113.10","mac":"AA:BB:CC:DD:EE:FF"}'
```

Upload clé SSH :
```bash
curl -sS -X PUT "https://meeting.ygsoft.fr/api/devices/$DEVICE_KEY/ssh-key" \
  -H "Content-Type: application/json" \
  -d '{"pubkey":"ssh-ed25519 AAAA... comment"}'
```

Récupérer hostkey :
```bash
curl -sS "https://meeting.ygsoft.fr/api/ssh-hostkey"
```
