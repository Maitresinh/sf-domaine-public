#!/bin/bash
# Pipeline complet : 22_+24_ → 23b_fix → 21b_noosfere → 27_babelio

LOG_FILE="/mnt/user/sf-dp/data/auto_launch.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Surveillance 22_ et 24_ démarrée ==="

while true; do
    RUNNING=$(docker exec sf-dp-tools ps aux | grep -E "22_goodreads_search.py|24_goodreads_crawl4ai.py" | grep -v grep | wc -l)
    
    if [ "$RUNNING" -eq 0 ]; then
        log "✅ 22_ et 24_ terminés"
        break
    fi
    
    if [ $(($(date +%s) % 600)) -lt 30 ]; then
        log "⏳ En attente... ($RUNNING script(s) en cours)"
    fi
    
    sleep 30
done

log ""
log "=== Lancement 23b_fix_first_vf.py (fix VF anciennes) ==="
docker exec sf-dp-tools python3 /app/23b_fix_first_vf.py 2>&1 | tee -a /mnt/user/sf-dp/data/23b_fix_first_vf.log
log "✅ 23b_ terminé"

log ""
log "=== Lancement 21b_translators_noosfere.py (traducteurs via noosfere) ==="
docker exec sf-dp-tools python3 /app/21b_translators_noosfere.py 2>&1 | tee -a /mnt/user/sf-dp/data/21b_noosfere.log
log "✅ 21b_ terminé"

log ""
log "=== Lancement 27_babelio.py ==="
docker exec -d sf-dp-tools python3 /app/27_babelio.py

sleep 3

if docker exec sf-dp-tools pgrep -f "27_babelio.py" > /dev/null 2>&1; then
    log "✅ 27_babelio lancé avec succès"
    log "   Durée estimée : 12h30"
    log "   Fin estimée : $(date -d '+12 hours 30 minutes' '+%H:%M:%S')"
else
    log "❌ ERREUR : 27_babelio n'a pas démarré"
fi

log "=== Pipeline terminé ==="
