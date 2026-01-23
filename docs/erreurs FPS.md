# Compte rendu d’analyse — erreurs `jpegdec` / frames perdues (GStreamer + RTSP)

## Constat (symptômes)
Le log indique une boucle d’erreurs au niveau du décodeur MJPEG :

- `jpegdec ... Decode error #68: Unsupported marker type 0x..`
- `jpegdec ... Failed to decode JPEG image`
- `v4l2src ... lost frames detected`

Interprétation directe :
- `jpegdec` reçoit des images MJPEG **corrompues / tronquées / désynchronisées** (pas un “JPEG exotique valide”).
- La mention `lost frames` confirme des **drops** côté capture (USB/driver/charge) qui peuvent produire des buffers incomplets, que `jpegdec` n’arrive plus à décoder.

---

## Cause la plus probable
### 1) Manque de tamponnage AVANT `jpegdec`
Dans le pipeline USB MJPEG, la structure actuelle est :

- `v4l2src ! image/jpeg ! jpegdec ! videoconvert`

La `queue` “anti-variations USB” est ajoutée **plus loin** (après overlay, juste avant l’encodeur).  
Or la corruption se produit **avant** `jpegdec`. Résultat : `jpegdec` prend de plein fouet les variations / trous / buffers partiels.

➡️ Conclusion : il faut **absorber / lisser / jeter** proprement des frames **avant** le décodeur MJPEG.

---

## Problèmes secondaires relevés (risque de pipeline incohérent)
### 2) Bug logique : détection “H264 direct” incorrecte
La fonction actuelle considère que la source “sort du H264” si la webcam **supporte** le H264, même si le pipeline choisi est MJPEG.

Conséquence possible :
- le script peut sélectionner `h264parse` (sans encode) alors que le flux a été décodé en raw (`jpegdec ! videoconvert`), ce qui rend la chaîne incohérente.

➡️ Conclusion : “source outputs H264” doit refléter **le choix réel du pipeline**, pas une capacité listée par `v4l2-ctl`.

---

## Correctifs recommandés (priorité)
### A) Ajouter une `queue` AVANT `jpegdec` (critique)
Objectif : préférer “perdre une frame” plutôt que “casser une frame”.

Exemple de chaîne USB MJPEG plus robuste :

- `v4l2src ! image/jpeg ! queue leaky=downstream ! jpegdec ! videoconvert`

Paramètres conseillés :
- `leaky=downstream`
- petite queue (2–3 buffers max) pour éviter la latence

### B) Ajouter `jpegparse` si disponible (recommandé)
`jpegparse` peut aider à resynchroniser/valider le flux MJPEG avant décodage :

- `... ! queue ... ! jpegparse ! jpegdec ! ...`

Fallback si `jpegparse` absent : revenir au flux avec `jpegdec` directement.

### C) Fallback décodeur : `avdec_mjpeg` si `jpegdec` est trop strict (optionnel)
Certaines webcams sortent un MJPEG “sale” : `jpegdec` est strict.  
`avdec_mjpeg` (FFmpeg) peut parfois être plus tolérant :

- `... ! avdec_mjpeg ! ...`

---

## Correction du bug “H264 direct” (important)
Remplacer la logique “la caméra supporte H264 => la source est H264” par une logique basée sur :
- le format réellement choisi par `build_video_source` (flag/variable interne).

Principe :
- Si le pipeline construit est `video/x-h264` → `SOURCE_IS_H264=1`
- Sinon `SOURCE_IS_H264=0`
- L’encodeur ne saute l’étape d’encodage que si `SOURCE_IS_H264=1`

---

## Tests rapides pour isoler la cause
### Test 1 — Vérifier si la source MJPEG est stable (sans décoder)
But : savoir si la corruption vient déjà de la capture USB.

- `v4l2src ! image/jpeg ! fakesink`

Si erreurs/drops visibles ici :
- problème USB/cam/câble/hub/charge système.

### Test 2 — Vérifier si c’est le décodeur qui souffre
- `v4l2src ! image/jpeg ! queue leaky=downstream ! jpegdec ! fakesink`

Si Test 1 OK mais Test 2 casse :
- souci de décodage/caps/format MJPEG borderline.

---

## Remarques pratiques (Pi 3B+ / charge)
- Réduire FPS/résolution stabilise souvent le flux (déjà bien : 640x480@15).
- Hub USB non alimenté/câble long = suspects classiques.
- Si la webcam sort du H264 natif et que la priorité est perf :
  - utiliser H264 direct (mais overlay implique alors re-encode si tu veux l’afficher).

---

## Conclusion
Le log correspond à un flux MJPEG qui arrive **abîmé** au décodeur (`jpegdec`), très probablement car le pipeline manque de **tamponnage et stratégie de drop avant décodage**.  
En parallèle, la logique “H264 direct” doit être corrigée car elle peut rendre le pipeline incohérent selon la caméra et le format réellement utilisé.
