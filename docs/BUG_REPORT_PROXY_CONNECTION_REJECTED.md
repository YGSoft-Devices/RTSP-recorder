# Bug Report: Meeting Proxy Rejette la Connexion du Device

## Résumé
Le proxy Meeting (meeting.ygsoft.fr:9001) ferme immédiatement la connexion après réception du handshake, sans envoyer de réponse.

## Environnement
- **Device:** 192.168.1.4 (Raspberry Pi 3B)
- **Device Key:** 3316A52EB08837267BF6BD3E2B2E8DC7
- **Token:** 41e291
- **Proxy:** meeting.ygsoft.fr:9001 (TLS désactivé)
- **Date:** 2026-02-02 02:57 CET

## Symptômes

### Comportement observé
1. Le tunnel_agent se connecte TCP à meeting.ygsoft.fr:9001 ✅
2. Le tunnel_agent envoie le handshake JSON + newline ✅
3. Le proxy **ferme immédiatement la connexion** (recv retourne 0 bytes) ❌
4. Aucune réponse d'erreur n'est envoyée ❌

### Test brut (socket Python)
```python
import socket, json
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect(("meeting.ygsoft.fr", 9001))
print("Connected to meeting.ygsoft.fr:9001")

handshake = {"token": "41e291", "name": "3316A52EB08837267BF6BD3E2B2E8DC7"}
handshake_line = json.dumps(handshake) + "\n"
print(f"Sending: {repr(handshake_line)}")
sock.sendall(handshake_line.encode("utf-8"))

print("Waiting for response...")
response = sock.recv(1024)
print(f"Received {len(response)} bytes: {repr(response)}")
```

### Résultat
```
Connected to meeting.ygsoft.fr:9001
Sending: '{"token": "41e291", "name": "3316A52EB08837267BF6BD3E2B2E8DC7"}\n'
Waiting for response...
Received 0 bytes: b''
```

## Vérifications Device-Side

### 1. Le device existe et est autorisé ✅
```bash
curl -sk 'https://meeting.ygsoft.fr/api/devices/3316A52EB08837267BF6BD3E2B2E8DC7' \
  -H 'X-Token-Code: 41e291'
```
Retourne:
```json
{
    "device_key": "3316A52EB08837267BF6BD3E2B2E8DC7",
    "authorized": true,
    "services": ["ssh", "scp", "debug"]
}
```

### 2. SSH écoute sur 0.0.0.0:22 ✅
```
ss -tlnp | grep 22
LISTEN 0      128          0.0.0.0:22        0.0.0.0:*
```

### 3. Pas de TCP wrappers ✅
- `/etc/hosts.allow` : vide (commentaires seulement)
- `/etc/hosts.deny` : vide (commentaires seulement)

### 4. SSH config standard ✅
```
Include /etc/ssh/sshd_config.d/*.conf
KbdInteractiveAuthentication no
UsePAM yes
```
Pas de `ListenAddress`, pas de `AllowUsers` restrictifs.

## Handshake Envoyé

Le device envoie exactement :
```
{"token": "41e291", "name": "3316A52EB08837267BF6BD3E2B2E8DC7"}\n
```
(74 bytes, UTF-8, terminé par newline `\n`)

## Questions pour l'équipe Meeting

1. **Le proxy valide-t-il le token/device_key avant d'accepter la connexion ?**
   - Si oui, pourquoi ferme-t-il sans envoyer de message d'erreur ?

2. **Le format du handshake est-il correct ?**
   - Clés attendues : `token` et `name` ?
   - Terminaison par `\n` ?

3. **Logs côté proxy ?**
   - Que montre le proxy quand il reçoit cette connexion ?
   - Y a-t-il une erreur de validation ?

4. **Le device est-il marqué comme "autorisé pour tunnel" ?**
   - L'API retourne `authorized: true` mais le tunnel ne fonctionne pas

## Comportement Attendu

Selon la documentation du protocole :
1. Device envoie `{"token":"...","name":"..."}\n`
2. Proxy répond avec status JSON (OK ou erreur)
3. Si OK, passage en mode frames binaires (N/D/C protocol)

## Impact

- **Critique** : Impossible d'établir un tunnel SSH vers le device
- **Conséquence** : Devices inaccessibles à distance via Meeting

## Suggestions

1. **Ajouter un message d'erreur** quand le proxy rejette une connexion
2. **Logs détaillés** côté proxy pour diagnostic
3. **Vérifier** que le device/token sont bien autorisés pour le service tunnel

---
*Rapport généré le 2026-02-02 03:00 CET*
*Version tunnel_agent: 1.2.0*
