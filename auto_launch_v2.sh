#!/bin/bash
# Orchestration pipeline enrichissement v2
# 1. 22_ + 24_ (en cours)
# 2. 23b_fix_first_vf
# 3. 28_enrich_anthologies_v2 (NOUVEAU)
# 4. 21b_translators_noosfere
# 5. 27_babelio

LOG="/mnt/user/sf-dp/data/auto_launch_v2.log"
echo "=== Auto-launch v2 démarré $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG"

# Fonction attente fin script
wait_for_script() {
    script_name=$1
    echo "[$(date '+%H:%M:%S')] Attente fin $script_name..." | tee -a "$LOG"
    
    while docker exec sf-dp-tools ps aux | grep -q "[p]ython.*$script_name"; do
        sleep 30
    done
    
    echo "[$(date '+%H:%M:%S')] ✅ $script_name terminé" | tee -a "$LOG"
}

# Étape 1 : Attendre 22_ et 24_
wait_for_script "22_goodreads_search.py"
wait_for_script "24_goodreads_crawl4ai.py"

# Étape 2 : 23b_fix_first_vf (~10s)
echo "[$(date '+%H:%M:%S')] Lancement 23b_fix_first_vf.py..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/23b_fix_first_vf.py >> "$LOG" 2>&1
echo "[$(date '+%H:%M:%S')] ✅ 23b terminé" | tee -a "$LOG"

# Étape 3 : 28_enrich_anthologies_v2 (NOUVEAU - ~10-20min)
echo "[$(date '+%H:%M:%S')] Lancement 28_enrich_anthologies_v2.py..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/28_enrich_anthologies_v2.py >> "$LOG" 2>&1
echo "[$(date '+%H:%M:%S')] ✅ 28 terminé" | tee -a "$LOG"

# Étape 4 : 21b_translators_noosfere (~8h)
echo "[$(date '+%H:%M:%S')] Lancement 21b_translators_noosfere.py..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/21b_translators_noosfere.py >> "$LOG" 2>&1
echo "[$(date '+%H:%M:%S')] ✅ 21b terminé" | tee -a "$LOG"

# Étape 5 : 27_babelio (~12h)
echo "[$(date '+%H:%M:%S')] Lancement 27_babelio.py..." | tee -a "$LOG"
docker exec sf-dp-tools python3 /app/27_babelio.py >> "$LOG" 2>&1
echo "[$(date '+%H:%M:%S')] ✅ 27 terminé" | tee -a "$LOG"

echo "=== Pipeline v2 TERMINÉ $(date '+%Y-%m-%d %H:%M:%S') ===" | tee -a "$LOG"
