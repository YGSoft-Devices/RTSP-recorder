# Bug Report - Meeting API Services Management

**Date**: 2026-02-02  
**Reporter**: RTSP-Recorder Team  
**Severity**: HIGH  
**Components**: Meeting API, RTSP-Recorder  
**Status**: ✅ **RESOLVED** (2026-02-02)

---

## Résumé des Corrections

| Bug | Description | Status | Commit |
|-----|-------------|--------|--------|
| BUG-001 | Services écrasés par heartbeat | ✅ CORRIGÉ | StatusController.php v1.7.0 |
| BUG-002 | Erreur SSL tunnel port 9001 | ✅ CORRIGÉ | proxy.js v2.1.0 (TLS optionnel) |
| BUG-003 | Endpoint `/api/ssh/pubkey` manquant | ✅ CORRIGÉ | SshKeysController.php v1.10.0 |

### Fichiers Modifiés
- `api/controllers/StatusController.php` - Ignore le champ services dans heartbeat
- `api/controllers/SshKeysController.php` - Nouvel endpoint GET /api/ssh/pubkey
- `api/index.php` - Routing pour le nouvel endpoint
- `reverse_tunnel/server/proxy.js` - Support TLS optionnel (env: YGS_TLS=1)

---

## 1. Bug: Devices Can Overwrite Declared Services on Meeting ✅ CORRIGÉ

### Description
Actuellement, le heartbeat envoyé par les devices contient un champ `services` qui est **accepté et enregistré** par Meeting API, écrasant ainsi les services déclarés côté Meeting.

### Comportement Actuel (INCORRECT)
1. Admin déclare sur Meeting les services autorisés pour un device : `{ssh: true, vnc: false, http: true, scp: true, debug: false}`
2. Device envoie un heartbeat avec `services: {ssh: true, vnc: false, http: true, scp: true, debug: false}`
3. Meeting **accepte ces valeurs** et les enregistre, **écrasant la configuration admin**

### Comportement Attendu (CORRECT)
1. Admin déclare sur Meeting les services autorisés pour un device
2. Device envoie un heartbeat (IP, status, etc.) **SANS champ services**
3. Meeting **conserve sa propre liste de services** comme source de vérité
4. Device interroge Meeting pour savoir quels services sont autorisés

### Impact
- **Sécurité**: Un device compromis pourrait s'auto-autoriser des services (debug, vnc...)
- **Cohérence**: La configuration admin peut être écrasée involontairement
- **Architecture**: Violation du principe "Meeting est la source de vérité"

### Correction Requise (Meeting API)

#### Option A - Ignorer le champ services dans le heartbeat (RECOMMANDÉ)
```javascript
// Dans le handler POST /api/devices/:deviceKey/online
const { ip_address, note, timestamp, ...rest } = req.body;

// NE PAS utiliser rest.services - l'ignorer silencieusement
// Les services sont définis uniquement via l'interface admin Meeting
```

#### Option B - Rejeter le heartbeat si services est présent
```javascript
if (req.body.services) {
    return res.status(400).json({ 
        error: 'services field not allowed in heartbeat',
        message: 'Services are managed by Meeting admin only'
    });
}
```

---

## 2. Bug: Connexion SSH via Meeting échoue

### Symptômes
```
ssh> ssh 3316A52EB08837267BF6BD3E2B2E8DC7
Requesting ssh tunnel, please wait
Waiting for port 9065 to open... OK

✔ SSH tunnel ready! Connecting with:
ssh -o UserKnownHostsFile=/home/meeting/.ssh/meeting_known_hosts \
    -o StrictHostKeyChecking=accept-new \
    -i /home/meeting/.ssh/id_rsa_meeting \
    -p 9065 device@clusterto83.meeting.ygsoft.fr

kex_exchange_identification: read: Connection reset by peer
Connection reset by 82.67.82.19 port 9065
SSH connection failed.
```

### Analyse

#### Problème 1: Tunnel Agent ne se connecte pas au port 9001
```
2026-02-02 01:51:11 - TunnelAgent - ERROR - Connection error: 
[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol
```
- Le tunnel agent essaie de se connecter à `meeting.ygsoft.fr:9001`
- Le serveur ferme la connexion SSL immédiatement
- **Cause probable**: Port 9001 non ouvert ou service tunnel non démarré côté Meeting

#### Problème 2: authorized_keys vide sur le device
```bash
$ cat ~/.ssh/authorized_keys
(vide)
```
- La clé publique SSH de Meeting n'a jamais été ajoutée au device
- Même si le tunnel fonctionnait, SSH serait refusé

### Corrections Requises

#### Côté Meeting Server
1. Vérifier que le service tunnel écoute sur le port 9001
2. Vérifier les logs du service tunnel pour comprendre pourquoi il ferme les connexions SSL

#### Côté RTSP-Recorder (à faire)
1. Implémenter `POST /api/meeting/device/pubkey` pour récupérer et installer la clé Meeting
2. Lors du provisionnement, récupérer automatiquement la clé publique Meeting

### Flux de connexion SSH attendu
```
1. Device: tunnel_agent.py se connecte à meeting.ygsoft.fr:9001 (WebSocket SSL)
2. Device: Envoie handshake JSON avec device_key
3. Meeting: Accepte la connexion, garde le tunnel ouvert
4. Admin: ssh device@meeting via terminal Meeting
5. Meeting: Envoie frame "N" (new stream) au device via tunnel
6. Device: Ouvre connexion TCP vers 127.0.0.1:22 (SSH local)
7. Device: Relaye les données entre tunnel et SSH local
8. SSH: Vérifie la clé Meeting dans authorized_keys → OK
9. Connexion établie
```

---

## 3. Actions Requises

### Meeting API Team
- [x] **CRITICAL**: Ignorer le champ `services` dans les heartbeats ✅ StatusController.php v1.7.0
- [x] Vérifier le service tunnel sur port 9001 ✅ proxy.js v2.1.0 avec TLS optionnel
- [x] **NEW**: Créer endpoint `GET /api/ssh/pubkey` ✅ SshKeysController.php v1.10.0
  - Endpoint disponible : `GET /api/ssh/pubkey` 
  - Formats supportés : JSON (par défaut) ou texte brut (`?format=plain`)
  - Retourne : pubkey, fingerprint, host, generated_at, usage

### RTSP-Recorder Team
- [x] Documenter le bug (ce document)
- [ ] Retirer `services` du payload heartbeat (optionnel, Meeting l'ignore maintenant)
- [ ] Implémenter la récupération automatique de la clé publique Meeting via `GET /api/ssh/pubkey`

---

## 4. Test de l'endpoint `/api/ssh/pubkey`

### Requête JSON
```bash
curl -X GET "https://meeting.ygsoft.fr/api/ssh/pubkey"
```

### Réponse
```json
{
  "pubkey": "ssh-rsa AAAAB3...",
  "fingerprint": "SHA256:oWjssuhqASzjbR6MMmx2dzjLKnrI404pXCXBjfSquKg",
  "host": "clusterTO83.meeting.ygsoft.fr",
  "generated_at": "2025-05-25 18:12:00",
  "usage": "Add this public key to ~/.ssh/authorized_keys on your device..."
}
```

---

## 5. Information Complémentaire

### Réponse API Meeting actuelle pour le device
```json
{
  "device_key": "3316A52EB08837267BF6BD3E2B2E8DC7",
  "device_name": "3316A52EB08837267BF6BD3E2B2E8DC7",
  "authorized": true,
  "device_type": "RTSP-Recorder",
  "ip_address": "192.168.1.4",
  "services": ["ssh", "http", "scp"],
  "note": "RTSP Recorder - Raspberry Pi 3 Model B Rev 1.2 - 192.168.1.4"
}
```

### Logs Tunnel Agent (device)
```
2026-02-02 01:51:11 - TunnelAgent - INFO - Connecting to meeting.ygsoft.fr:9001...
2026-02-02 01:51:11 - TunnelAgent - ERROR - Connection error: 
  [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1029)
2026-02-02 01:51:11 - TunnelAgent - INFO - Reconnecting in 40s...
```
→ Le port 9001 existe mais ferme immédiatement la connexion SSL

---

## Références

- Meeting API Integration Guide
- RTSP-Recorder AGENTS.md
- tunnel_agent.py (implémentation tunnel inversé)
