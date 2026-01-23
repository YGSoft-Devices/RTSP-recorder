OK, ton rapport dit deux choses très claires :

1. **Le système ne voit aucun RTC** (`RTC time: n/a`, `detected: false`, `devices: []`)
2. Ton script/outillage est un peu “à poil” parce que **`hwclock` n’est même pas installé** (`returncode 127`, `hwclock: not found`)

Donc on va procéder comme un humain efficace : d’abord **I²C fonctionne ?**, ensuite **le module répond ?**, ensuite **overlay/kernel**, ensuite **hwclock**.

---

## 0) Installe l’outil manquant (sinon tu voles à l’aveugle)

Sur Raspberry Pi OS :

```bash
sudo apt update
sudo apt install -y util-linux i2c-tools
```

* `hwclock` est dans `util-linux`
* `i2cdetect` est dans `i2c-tools`

---

## 1) Vérifie que l’I²C est activé (vraiment)

### A) Côté config

Sur Trixie (Bookworm/Trixie style), le fichier est bien `/boot/firmware/config.txt`.

Check :

```bash
grep -nE "^(dtparam=i2c_arm=on|dtoverlay=i2c-rtc)" /boot/firmware/config.txt || true
```

Si tu ne vois pas `dtparam=i2c_arm=on`, ajoute-le :

```bash
echo "dtparam=i2c_arm=on" | sudo tee -a /boot/firmware/config.txt
```

Reboot :

```bash
sudo reboot
```

### B) Après reboot : bus I²C présent ?

```bash
ls -l /dev/i2c* || true
```

Tu dois voir **/dev/i2c-1** sur la plupart des Pi.

---

## 2) Scan I²C : est-ce que le DS3231 répond ?

```bash
sudo i2cdetect -y 1
```

Un DS3231 normal apparaît à l’adresse **0x68**.

* Si tu vois `68` → le module est **câblé et vivant**
* Si tu ne vois rien → **câblage / pins / module / bus** (le plus probable)

### Si tu ne vois pas 0x68 : check câblage

Ton module DS3231 a souvent un header 5 pins (genre **GND, VCC, SDA, SCL, SQW**).
Pour le Pi, le montage standard :

* **VCC → 3.3V** (pin 1 ou 17)
* **GND → GND** (pin 6/9/14/20/25/30/34/39)
* **SDA → GPIO2 (SDA1)** (pin 3)
* **SCL → GPIO3 (SCL1)** (pin 5)
* **SQW / 32K** : optionnel, tu le laisses en l’air.

⚠️ **Évite le 5V** (pin 2 ou 4) sauf si tu sais EXACTEMENT ce que ton module fait.
Beaucoup de modules DS3231 sont tolérants, mais certains ont des pull-ups vers VCC → et là tu balances 5V sur SDA/SCL = mauvaise idée.

---

## 3) Si 0x68 est visible : active l’overlay RTC

Ajoute dans `/boot/firmware/config.txt` :

```bash
dtoverlay=i2c-rtc,ds3231
```

Puis reboot :

```bash
sudo reboot
```

Après reboot :

```bash
timedatectl
```

Tu dois voir un truc du genre :

* `RTC time: ...` (plus “n/a”)
  et aussi :

```bash
ls -l /dev/rtc* || true
```

Normalement `/dev/rtc0`.

---

## 4) Si ça marche : éviter que “fake-hwclock” te sabote (selon install)

Sur certains systèmes, un service “fake hwclock” peut interférer.

Check :

```bash
systemctl status fake-hwclock 2>/dev/null | cat
```

Si présent et que tu veux un vrai RTC :

```bash
sudo systemctl disable --now fake-hwclock || true
sudo apt purge -y fake-hwclock || true
```

---

## 5) Test manuel lecture/écriture RTC

Une fois `/dev/rtc0` présent :

Lire l’RTC :

```bash
sudo hwclock -r
```

Écrire l’heure système vers le RTC :

```bash
sudo hwclock -w
```

Ou charger l’heure depuis le RTC :

```bash
sudo hwclock -s
```

---

## 6) Si `i2cdetect` ne voit rien : causes fréquentes (dans l’ordre)

* **SDA/SCL inversés** (classique)
* Tu es sur le mauvais bus (`i2cdetect -y 0` à tester sur certains cas, mais sur Pi moderne c’est quasi toujours 1)
* **Module alimenté en 5V avec pull-ups 5V** → bus I²C bloqué / dangereux
* Mauvais GND (oui… ça arrive)
* Le module est dead / soudure foireuse / câble dupont en carton

---

### Résumé en une checklist

1. `sudo apt install util-linux i2c-tools`
2. `dtparam=i2c_arm=on` dans `/boot/firmware/config.txt`
3. reboot
4. `ls /dev/i2c-1`
5. `sudo i2cdetect -y 1` → tu dois voir `68`
6. `dtoverlay=i2c-rtc,ds3231`
7. reboot
8. `timedatectl` → RTC time non-n/a
9. `sudo hwclock -r`

---

Ton JSON montre **`i2c_scan: null`** : donc ton outil n’a même pas pu scanner. Ça colle parfaitement avec “I²C pas activé” *ou* “i2c-tools absent”. Tu vas débloquer 80% du problème juste avec les étapes 0→2.

Et si tu veux un diagnostic ultra net : après avoir installé `i2c-tools`, poste juste la sortie de :

```bash
ls -l /dev/i2c*
sudo i2cdetect -y 1
grep -nE "dtparam=i2c_arm|dtoverlay=i2c-rtc" /boot/firmware/config.txt
```


MISE A JOUR : 

Oui, c’est **cohérent** avec Trixie : tu as `util-linux` installé… mais **`hwclock` n’est plus forcément dedans**. Sur Debian 13 / Trixie, `hwclock` a été déplacé et peut se retrouver dans **`util-linux-extra`**, donc tu peux avoir “util-linux OK” et **zéro binaire `hwclock` sur le système**. ([bugs.debian.org][1])

### 1) Récupérer `hwclock` (le vrai)

Fais juste :

```bash
sudo apt update
sudo apt install -y util-linux-extra
command -v hwclock
dpkg -L util-linux-extra | grep -E '/hwclock$' || true
```

À ce stade, tu dois voir un chemin (souvent `/usr/sbin/hwclock` ou `/usr/bin/hwclock` selon l’usrmerge).

### 2) Ton RTC est vu sur l’I2C… mais pas “déclaré” au kernel

Ton scan I2C montre **0x68**, classique DS3231/DS1307 : donc le câblage + I2C sont OK. Mais ton rapport dit aussi **`overlay_configured: false`** et `RTC time: n/a` → le kernel n’a pas créé `/dev/rtc0` parce que l’overlay RTC n’est pas activé.

Dans `/boot/firmware/config.txt`, garde :

```ini
dtparam=i2c_arm=on
```

Et **ajoute** (pour DS3231) :

```ini
dtoverlay=i2c-rtc,ds3231
```

Puis reboot :

```bash
sudo reboot
```

### 3) Vérifs après reboot

```bash
ls -l /dev/rtc*
dmesg | grep -i rtc
timedatectl
```

Tu veux voir un `/dev/rtc0` et `timedatectl` qui affiche une ligne `RTC time: ...` (plus “n/a”).

### 4) Initialiser l’heure du RTC (une fois)

Quand le système est à l’heure (NTP actif, ce qui est ton cas), pousse l’heure système dans le RTC :

```bash
sudo hwclock -w
sudo hwclock -r
```

### 5) Le piège classique sur Raspberry Pi OS : `fake-hwclock`

Si tu as `fake-hwclock`, il peut écraser/perturber le RTC au boot. Check :

```bash
systemctl status fake-hwclock 2>/dev/null || true
```

Si présent, tu peux le couper :

```bash
sudo systemctl disable --now fake-hwclock
```

(Et éventuellement le purger plus tard si tu veux un OS “sec” et que tu assumes le RTC réel.)

---

**Résumé brutal :** ton DS3231 répond bien (0x68), mais il n’est pas branché “logiquement” au kernel tant que tu n’actives pas `dtoverlay=i2c-rtc,ds3231`. Et ton `hwclock` manquant est très probablement juste le split de paquet → `util-linux-extra`. ([bugs.debian.org][1])

[1]: https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1110651&utm_source=chatgpt.com "Calamares fails to run hwclock on debian 13.0.0 LXDE image"
