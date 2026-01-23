# TODO (travail en cours)

## ESP32 (dérivé)

- Finaliser le support **OV5640** : identifier le modèle exact + renseigner le pinout dans `esp32/firmware/include/boards/ov5640_template.h`
- Ajouter un mode **AP password** configurable (et/ou affichage sur serial) pour éviter un mot de passe unique en production
- Ajouter une option **OTA update** (si besoin)
- Ajouter une option **RTSP** (si un flux RTSP est requis sur ESP32)
- Meeting: confirmer si l’API exige une authentification (token/header) pour `POST /api/devices/{device_key}/online` en dehors d’un cluster privé

## Debug tools

- `debug_tools/debug_tools_gui.ps1` : ajouter des presets de commandes (status services, logs webmanager, etc.) + bouton “Open logs folder” après `collect`
- `debug_tools/config_tool.ps1` : ajouter un mode "bulk set" a partir d'un fichier key=value
- `debug_tools/debug_tools_gui.ps1` : ajouter un filtre/recherche dans la mémoire devices + badge couleur online/offline

## Web manager / CSI

- Refactor `web-manager/static/js/app.js` en modules incrementaux (navigation, home, services, reseau, logs, fichiers, debug), sans changer l'API publique; maintenir le script smoke.
- Identifier des valeurs fiables pour `AwbEnable` et `AeFlickerPeriod` (Picamera2 retourne `null` dans `/controls`)
- Valider visuellement le bouton ghost-fix sur le flux CSI (effet ghost disparu)
- Vérifier sur device que les nouveaux champs UI (Meeting local, ONVIF RTSP/identifiants, WiFi check_interval, CAMERA_DEVICE/CSI/USB, MAX_DISK_MB) se sauvegardent correctement
- Tester le flux Backup/Restore (avec et sans logs) + reboot automatique apres restauration
- Tester "Update from file" avec un package genere depuis `debug_tools/package_update.ps1`
- Tester "Update depuis repo" (modale + force/reset settings)
- Verifier que les scripts `/usr/local/bin` restent executables apres update depuis fichier
- Tester la validation `required_packages` (ex: `i2c-tools`, `util-linux-extra`) lors d’un update par fichier
- Valider scheduler profils (USB/CSI) au reboot + statut "Actif" dans l'UI
- Verifier que AE/AWB actifs dans un profil CSI ne forcent pas les valeurs manuelles
- Tester la prise en charge RTC DS3231 (auto/enable/disable) + reboot
- Tester "Appliquer" audio (restart RTSP) + validation des sources de logs etendues
- Valider l'export logs et les nouveaux indicateurs stockage dans l'onglet fichiers
- Tester la génération thumbnails v2.32.50 (charge CPU) + vérifier qu'un refresh affiche les miniatures sans tempête `ffmpeg`
- Confirmer que PipeWire/WirePlumber masqués n'impactent pas la capture ALSA (USB audio) sur Pi 3B+


## A corriger.idées diverses : 

- parametres failover wifi et ip unifiée wlan ne sont plus affichés.
- meeting > configuration locale à deplacer dans debug.
- video > parametres camera legacy ne doit plus etre utilisé. les fonctions auto camera CSI et auto camera USB est remplacé par "type de camera".
- deplacer le cadre apercu dans les parametres avancés cameras, en mode CSI et USB.
- scheduler profils > serait il pas mieux d'enregistrer dans la base sql utilisée par les miniatures?
- mettre en place le systeme d'update.
- en cas d'absence de config : ne doit pas bloquer, et le frontend doit afficher un assistant "premier demarrage" qui saluera l'utilisateur poliment (un peu comme sur les iphones, ou android, avec une animation sympa et le mot bienvenu dans plusieurs langue ... enfin un truc cool), ainsi que sa langue (pour l'instant, Francais, tant que le systeme de traduction n'est pas en place.).next, le type de camera detectée (ou une alerte si pas de camera disponible), next, ca demande la devicekey et le token pour meeting (qu'on peux skip, et qui est ignoré si le device est deja provisionné). Si l'utilisateur entre une devicekey et un token, on check sur meeting si un backup est dispo et on propose de le restaurer (placeholder, meeting non pret) ou s'il veut restaurer un backup. pour finir, on demande a l'utilisateur de creer un identifiant/password admin pour la login page a venir, on souhaite a l'utilisateur de bien s'amuser !
