# Bug Report: Device SSH Connection Reset via Reverse Tunnel

**Date:** 2026-02-02  
**Reporter:** Debug Tools Testing Session  
**Severity:** High  
**Component:** Device SSH Server / Reverse Tunnel  

---

## Summary

Les connexions SSH vers le device via le tunnel reverse sont systématiquement rejetées avec "Connection reset by peer" lors de l'échange de clés SSH (kex_exchange_identification), malgré un tunnel TCP fonctionnel.

---

## Device Information

| Field | Value |
|-------|-------|
| **Device Key** | `3316A52EB08837267BF6BD3E2B2E8DC7` |
| **Device Type** | RTSP-Recorder |
| **IP Address** | 192.168.1.4 |
| **Last Seen** | 2026-02-02 01:41:52 |
| **Status** | Available (online) |
| **Authorized** | Yes |

---

## Tunnel Information

| Field | Value |
|-------|-------|
| **Tunnel Port** | 9063 (puis 9108 après re-demande) |
| **Service** | SSH |
| **Expiration** | 2026-02-02 01:29:02 (port 9108) |
| **Port Status** | Listening (vérifié avec netstat) |

---

## Reproduction Steps

1. S'assurer que le device est online (API `/api/devices/{key}/availability` retourne "Available")
2. Demander un tunnel SSH via API `/api/devices/{key}/request-tunnel-port`
3. L'API retourne un port (ex: 9063)
4. Vérifier que le port est bien en écoute sur le serveur Meeting (netstat confirme)
5. Tenter une connexion SSH : `ssh -p 9063 device@meeting.ygsoft.fr`
6. **Résultat:** Connexion reset immédiatement après l'échange initial

---

## Verbose SSH Output

```
OpenSSH_8.9p1 Ubuntu-3ubuntu0.10, OpenSSL 3.0.2 15 Mar 2022
debug1: Connecting to meeting.ygsoft.fr [92.154.44.5] port 9063.
debug1: Connection established.
debug1: identity file /home/meeting/.ssh/id_rsa type -1
debug1: identity file /home/meeting/.ssh/id_rsa-cert type -1
debug1: identity file /home/meeting/.ssh/id_ecdsa type -1
debug1: identity file /home/meeting/.ssh/id_ecdsa-cert type -1
debug1: identity file /home/meeting/.ssh/id_ecdsa_sk type -1
debug1: identity file /home/meeting/.ssh/id_ecdsa_sk-cert type -1
debug1: identity file /home/meeting/.ssh/id_ed25519 type -1
debug1: identity file /home/meeting/.ssh/id_ed25519-cert type -1
debug1: identity file /home/meeting/.ssh/id_ed25519_sk type -1
debug1: identity file /home/meeting/.ssh/id_ed25519_sk-cert type -1
debug1: identity file /home/meeting/.ssh/id_xmss type -1
debug1: identity file /home/meeting/.ssh/id_xmss-cert type -1
debug1: identity file /home/meeting/.ssh/id_dsa type -1
debug1: identity file /home/meeting/.ssh/id_dsa-cert type -1
debug1: Local version string SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.10
kex_exchange_identification: read: Connection reset by peer
Connection reset by 92.154.44.5 port 9063
```

---

## Analysis

### What Works ✅
1. Device est online et répond aux heartbeats
2. API Meeting retourne les bonnes informations
3. Tunnel reverse est établi (port attribué et en écoute)
4. Connexion TCP s'établit correctement vers le port du tunnel
5. Le client SSH envoie sa version string

### What Fails ❌
1. Le device **reset la connexion** immédiatement après avoir reçu la version string SSH
2. L'échange de clés n'a même pas le temps de commencer
3. Le reset vient du côté device (pas du serveur Meeting)

---

## Possible Causes

### 1. **SSH Server Non Démarré sur le Device**
Le daemon SSH n'est peut-être pas actif sur le device.

**À vérifier:**
```bash
systemctl status sshd
# ou
systemctl status ssh
```

### 2. **SSH Server Écoute sur Mauvaise Interface**
Le SSH pourrait n'écouter que sur localhost et pas sur l'interface tunnel.

**À vérifier dans `/etc/ssh/sshd_config`:**
```
ListenAddress 0.0.0.0
# ou absence de ListenAddress restrictif
```

### 3. **Firewall Bloquant les Connexions**
iptables/nftables pourrait bloquer les connexions entrantes sur le tunnel.

**À vérifier:**
```bash
iptables -L -n
ufw status
```

### 4. **AllowUsers/DenyUsers Restrictifs**
La config SSH pourrait restreindre les utilisateurs autorisés.

**À vérifier dans `/etc/ssh/sshd_config`:**
```
AllowUsers device
# ou
DenyUsers *
```

### 5. **TCP Wrapper / hosts.allow / hosts.deny**
```bash
cat /etc/hosts.allow
cat /etc/hosts.deny
```

### 6. **Tunnel Reverse Mal Configuré côté Device**
Le tunnel pourrait pointer vers le mauvais port local.

**À vérifier:**
```bash
# Commande de tunnel utilisée par le device
ssh -R <server_port>:localhost:<local_port> ...
# <local_port> doit être 22 (ou le port SSH du device)
```

### 7. **Configuration SSH Défectueuse**
Une configuration SSH invalide peut provoquer des resets.

**À vérifier:**
```bash
sshd -t  # Test de configuration
journalctl -u ssh -n 50  # Logs SSH
```

---

## Recommended Fixes

### Sur le Device

1. **Vérifier que SSH est démarré:**
```bash
sudo systemctl start ssh
sudo systemctl enable ssh
```

2. **Vérifier la configuration SSH:**
```bash
sudo sshd -t  # Doit retourner sans erreur
```

3. **Autoriser les connexions:**
```bash
# /etc/ssh/sshd_config
ListenAddress 0.0.0.0
PermitRootLogin no
PasswordAuthentication yes
# Supprimer tout AllowUsers/DenyUsers restrictif
```

4. **Vérifier le firewall:**
```bash
sudo ufw allow ssh
# ou
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
```

5. **Vérifier les logs SSH lors d'une tentative de connexion:**
```bash
sudo journalctl -u ssh -f
# Dans un autre terminal, tenter la connexion
```

### Vérification du Tunnel

S'assurer que la commande de tunnel reverse est correcte:
```bash
# Le device devrait exécuter quelque chose comme:
ssh -R 9063:localhost:22 meeting@meeting.ygsoft.fr -p 9922
#         ^           ^
#         |           +-- Port SSH local du device
#         +-- Port attribué par le serveur
```

---

## Test Commands for Developer

```bash
# 1. Vérifier si SSH est actif
systemctl status ssh

# 2. Tester la config
sshd -t

# 3. Voir les logs en temps réel
journalctl -u ssh -f

# 4. Vérifier les connexions actives
ss -tlnp | grep 22

# 5. Tester SSH localement sur le device
ssh localhost

# 6. Vérifier le tunnel actif
ss -tlnp | grep LISTEN

# 7. Voir la commande SSH tunnel en cours
ps aux | grep 'ssh.*-R'
```

---

## Environment Details

| Component | Version/Info |
|-----------|--------------|
| Meeting Server | meeting.ygsoft.fr:9922 |
| Meeting API | https://meeting.ygsoft.fr:9443/api |
| Server SSH | OpenSSH_8.9p1 Ubuntu |
| Client Test | WSL Ubuntu / OpenSSH_8.9p1 |

---

## Attachments

### API Response: Device Details
```json
{
  "device_key": "3316A52EB08837267BF6BD3E2B2E8DC7",
  "device_type": "RTSP-Recorder",
  "name": "raspi-local",
  "ip_address": "192.168.1.4",
  "mac_address": "D8:3A:DD:8D:F9:A8",
  "authorized": 1,
  "last_seen": "2026-02-02 01:41:52",
  "status": "Available"
}
```

### API Response: Tunnel Request
```json
{
  "port": 9063,
  "service": "ssh",
  "device_key": "3316A52EB08837267BF6BD3E2B2E8DC7"
}
```

### Database: tunnel_ports Entry
```
| device_key                         | service | port | expires_at          |
|------------------------------------|---------|------|---------------------|
| 3316A52EB08837267BF6BD3E2B2E8DC7   | ssh     | 9108 | 2026-02-02 01:29:02 |
```

---

## Status

- [ ] Bug confirmed reproducible
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] Fix verified

---

## Notes

Ce bug affecte potentiellement **tous les devices** qui établissent un tunnel reverse mais dont le serveur SSH n'est pas correctement configuré pour accepter les connexions via ce tunnel. Le problème est côté device, pas côté serveur Meeting.
