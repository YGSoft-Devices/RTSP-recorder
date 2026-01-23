#!/usr/bin/env bash
# stop_services.sh - Arrête/Démarre les services du projet RTSP-Full
# Version: 1.0.0
#
# Usage:
#   sudo ./stop_services.sh           # Arrêter tous les services
#   sudo ./stop_services.sh --status  # Afficher le status
#   sudo ./stop_services.sh --start   # Démarrer tous les services
#   sudo ./stop_services.sh --restart # Redémarrer tous les services
#
# Utile pour libérer la caméra lors de tests manuels

set -euo pipefail

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Liste des services du projet (dans l'ordre de dépendance)
SERVICES=(
    "rpi-cam-webmanager.service"      # Interface web Flask
    "rpi-av-rtsp-recorder.service"    # Serveur RTSP GStreamer
    "rtsp-recorder.service"           # Enregistrement ffmpeg
    "rtsp-watchdog.service"           # Watchdog haute disponibilité
    "rpi-cam-onvif.service"           # Serveur ONVIF
    "rtsp-camera-recovery.service"    # Récupération caméra
)

# Vérifier les privilèges root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Ce script doit être exécuté en root (sudo)${NC}"
        exit 1
    fi
}

# Afficher le status de tous les services
show_status() {
    echo -e "${CYAN}=== Status des services RTSP-Full ===${NC}"
    echo ""
    
    for service in "${SERVICES[@]}"; do
        # Extraire le nom court (sans .service)
        short_name="${service%.service}"
        
        if systemctl list-unit-files "$service" 2>/dev/null | grep -q "$service"; then
            status=$(systemctl is-active "$service" 2>/dev/null || echo "unknown")
            enabled=$(systemctl is-enabled "$service" 2>/dev/null || echo "unknown")
            
            case $status in
                active)
                    echo -e "  ${GREEN}●${NC} $short_name: ${GREEN}$status${NC} (enabled: $enabled)"
                    ;;
                inactive)
                    echo -e "  ${YELLOW}○${NC} $short_name: ${YELLOW}$status${NC} (enabled: $enabled)"
                    ;;
                failed)
                    echo -e "  ${RED}✗${NC} $short_name: ${RED}$status${NC} (enabled: $enabled)"
                    ;;
                *)
                    echo -e "  ${YELLOW}?${NC} $short_name: $status"
                    ;;
            esac
        else
            echo -e "  ${YELLOW}-${NC} $short_name: ${YELLOW}non installé${NC}"
        fi
    done
    
    echo ""
    
    # Vérifier si la caméra est libre
    echo -e "${CYAN}=== Caméra USB ===${NC}"
    if [[ -e /dev/video0 ]]; then
        # Vérifier si un processus utilise la caméra
        camera_users=$(fuser /dev/video0 2>/dev/null || echo "")
        if [[ -n "$camera_users" ]]; then
            echo -e "  ${YELLOW}⚠${NC}  /dev/video0 utilisée par PID: $camera_users"
            # Afficher le nom du processus
            for pid in $camera_users; do
                pname=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
                echo -e "      └─ $pid: $pname"
            done
        else
            echo -e "  ${GREEN}✓${NC}  /dev/video0 disponible (libre)"
        fi
    else
        echo -e "  ${RED}✗${NC}  /dev/video0 non détectée"
    fi
    
    echo ""
}

# Arrêter tous les services
stop_services() {
    echo -e "${CYAN}=== Arrêt des services RTSP-Full ===${NC}"
    echo ""
    
    for service in "${SERVICES[@]}"; do
        short_name="${service%.service}"
        if systemctl list-unit-files "$service" 2>/dev/null | grep -q "$service"; then
            if systemctl is-active --quiet "$service"; then
                echo -n "  Arrêt de $short_name... "
                if systemctl stop "$service" 2>/dev/null; then
                    echo -e "${GREEN}OK${NC}"
                else
                    echo -e "${RED}ERREUR${NC}"
                fi
            else
                echo -e "  $short_name: ${YELLOW}déjà arrêté${NC}"
            fi
        fi
    done
    
    echo ""
    echo -e "${GREEN}✓ Services arrêtés - Caméra libérée${NC}"
    echo ""
    echo -e "${YELLOW}Tip: Utilisez 'v4l2-ctl --list-devices' pour lister les caméras${NC}"
    echo -e "${YELLOW}     Utilisez 'ffplay /dev/video0' pour tester la caméra${NC}"
}

# Démarrer tous les services
start_services() {
    echo -e "${CYAN}=== Démarrage des services RTSP-Full ===${NC}"
    echo ""
    
    # Démarrer dans l'ordre inverse (dépendances d'abord)
    for service in "${SERVICES[@]}"; do
        short_name="${service%.service}"
        if systemctl list-unit-files "$service" 2>/dev/null | grep -q "$service"; then
            if systemctl is-enabled --quiet "$service" 2>/dev/null; then
                echo -n "  Démarrage de $short_name... "
                if systemctl start "$service" 2>/dev/null; then
                    echo -e "${GREEN}OK${NC}"
                else
                    echo -e "${RED}ERREUR${NC}"
                fi
            else
                echo -e "  $short_name: ${YELLOW}désactivé (skip)${NC}"
            fi
        fi
    done
    
    echo ""
    echo -e "${GREEN}✓ Services démarrés${NC}"
}

# Redémarrer tous les services
restart_services() {
    stop_services
    echo ""
    sleep 2
    start_services
}

# Aide
show_help() {
    echo "Usage: sudo $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  (sans option)  Arrêter tous les services"
    echo "  --status       Afficher le status des services"
    echo "  --start        Démarrer tous les services"
    echo "  --restart      Redémarrer tous les services"
    echo "  --help         Afficher cette aide"
    echo ""
    echo "Services gérés:"
    for service in "${SERVICES[@]}"; do
        echo "  - $service"
    done
}

# Main
main() {
    check_root
    
    case "${1:-}" in
        --status|-s)
            show_status
            ;;
        --start)
            start_services
            ;;
        --restart|-r)
            restart_services
            ;;
        --help|-h)
            show_help
            ;;
        "")
            stop_services
            ;;
        *)
            echo -e "${RED}Option inconnue: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
