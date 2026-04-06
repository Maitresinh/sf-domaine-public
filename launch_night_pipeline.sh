#!/bin/bash
# Attend la fin de 21_, puis lance 22_ et 24_ P5-P8 en parallèle

echo "=== Attente fin 21_translators.py ==="
while docker exec sf-dp-tools pgrep -f "21_translators.py" > /dev/null 2>&1; do
    sleep 5
done

echo ""
echo "✅ 21_ terminé à $(date +%H:%M:%S)"
echo ""
echo "=== Lancement 22_goodreads_search.py (6h) ==="
docker exec -d sf-dp-tools python3 /app/22_goodreads_search.py
sleep 2

echo "=== Lancement 24_goodreads_crawl4ai.py P5-P8 (3h20) ==="
docker exec -d sf-dp-tools python3 /app/24_goodreads_crawl4ai.py
sleep 2

echo ""
echo "✅ Pipeline lancé à $(date +%H:%M:%S)"
echo "   - 22_ : ~4h10 (fin vers 4h20)"
echo "   - 24_ : ~1h50 (fin vers 2h00)"
echo ""
echo "Monitoring :"
echo "  tail -f /mnt/user/sf-dp/data/22_goodreads_search.log"
echo "  tail -f /mnt/user/sf-dp/data/24_goodreads.log"
