#!/bin/bash
LOG="/mnt/user/sf-dp/data/auto_launch_v3.log"
echo "=== Auto-launch v3 démarré $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG"

wait_for_script() {
    script_name=$1
    echo "[$(date '+%H:%M:%S')] Attente fin $script_name..." | tee -a "$LOG"
    while docker exec sf-dp-tools ps aux | grep -q "[p]ython.*$script_name"; do
        sleep 30
    done
    echo "[$(date '+%H:%M:%S')] ✅ $script_name terminé" | tee -a "$LOG"
}

# 1. Attendre 22_ (si tourne)
if docker exec sf-dp-tools ps aux | grep -q "[p]ython.*22_goodreads"; then
    wait_for_script "22_goodreads_search.py"
fi

# 2. Fix first_vf
echo "[$(date '+%H:%M:%S')] 23b_fix_first_vf..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/23b_fix_first_vf.py >> "$LOG" 2>&1

# 3. Enrichir anthologies
echo "[$(date '+%H:%M:%S')] 28_enrich_anthologies_v2..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/28_enrich_anthologies_v2.py >> "$LOG" 2>&1

# 4. Reviews anthologies
echo "[$(date '+%H:%M:%S')] 29_anthology_reviews_v2..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/29_anthology_reviews_v2.py >> "$LOG" 2>&1

# 5. Traducteurs
echo "[$(date '+%H:%M:%S')] 21b_translators_noosfere..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/21b_translators_noosfere.py >> "$LOG" 2>&1

# 6. Babelio
echo "[$(date '+%H:%M:%S')] 27_babelio..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/27_babelio.py >> "$LOG" 2>&1

echo "=== Pipeline v3 TERMINÉ $(date '+%Y-%m-%d %H:%M:%S') ===" | tee -a "$LOG"
