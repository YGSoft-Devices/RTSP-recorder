attention : informations données a titre indicatif, et probablement obsolete pour les dernieres version de raspberrypi os Trixie.


Oui. Depuis **Raspberry Pi OS Bookworm** (et donc aussi Trixie), le vieux réflexe `/boot/config.txt` est devenu un piège à touristes : le fichier “réel” est **dans la partition boot montée sur** **`/boot/firmware/`**. ([Raspberry Pi][1])

### Où est passé `config.txt` ?

* **Avant Bookworm** : `/boot/config.txt`
* **Bookworm/Trixie** : **`/boot/firmware/config.txt`** ([Raspberry Pi][1])
  Sur certaines installs, `/boot/config.txt` existe encore mais sert juste de panneau “NE PAS ÉDITER, c’est ailleurs” (ou un lien symbolique selon versions). ([Forums Raspberry Pi][2])

### Vérifie sur TA machine (2 commandes, pas de poésie)

```bash
ls -la /boot /boot/firmware 2>/dev/null
ls -la /boot/firmware/config.txt /boot/config.txt 2>/dev/null
```

### Du coup, tes réglages (BT off, HDMI off, audio off, LEDs off), c’est ici :

Édite **`/boot/firmware/config.txt`** :

```ini
# --- inutiles pour ton projet ---
dtoverlay=disable-bt
dtparam=audio=off
hdmi_blanking=2

# LEDs off
dtparam=act_led_trigger=none
dtparam=act_led_activelow=on
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=on
```

### Et si tu veux la méthode “officielle” sans te battre avec les chemins

`raspi-config` modifie justement **`/boot/firmware/config.txt`** sur Bookworm. ([Raspberry Pi][3])

---

Bonus nerd (utile) : Raspberry Pi pousse aussi Netplan/cloud-init récemment, donc selon ton image, la partie réseau peut être “plus moderne” qu’avant. Mais pour **désactiver HDMI/audio/BT**, c’est bien `config.txt` côté firmware, donc **`/boot/firmware/config.txt`**. ([Raspberry Pi][1])

[1]: https://www.raspberrypi.com/documentation/computers/config_txt.html?utm_source=chatgpt.com "config.txt - Raspberry Pi Documentation"
[2]: https://forums.raspberrypi.com/viewtopic.php?t=386331&utm_source=chatgpt.com "config.txt moved from /boot to /boot/firmware"
[3]: https://www.raspberrypi.com/documentation/computers/configuration.html?utm_source=chatgpt.com "Configuration - Raspberry Pi Documentation"
