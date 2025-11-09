#!/bin/bash
# Otomatik temizlik runner script
# Cron job için: 0 3 * * 0 /path/to/ChimeraBot/run_cleanup.sh

cd "$(dirname "$0")"

echo "=================================================="
echo "ChimeraBot Otomatik Temizlik"
echo "Tarih: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

# Python3 bul
PYTHON_CMD=""
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "❌ HATA: Python3 bulunamadı!"
    exit 1
fi

echo "✓ Python: $PYTHON_CMD"

# Temizlik yap
$PYTHON_CMD cleanup_cache_db.py \
    --cache-days 7 \
    --trade-history-days 90 \
    --alpha-cache-hours 48 \
    --log-days 14

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Temizlik başarılı"
else
    echo "❌ Temizlik başarısız (exit code: $EXIT_CODE)"
fi

echo "=================================================="
exit $EXIT_CODE
