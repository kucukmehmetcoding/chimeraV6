#!/bin/bash
# Coolify DB Migration Script
# Eksik kolonları ekler, veritabanını günceller

set -e  # Hata durumunda dur

echo "=================================================="
echo "ChimeraBot DB Migration - Advanced Risk Columns"
echo "Tarih: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

# Python komutunu bul
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

# Migration çalıştır
echo ""
echo "🔄 Migration başlatılıyor..."
$PYTHON_CMD migrations/add_advanced_risk_columns.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Migration başarılı!"
    echo ""
    echo "📊 DB schema güncellendi. Bot yeniden başlatılabilir."
else
    echo ""
    echo "❌ Migration başarısız (exit code: $EXIT_CODE)"
    echo "Loglara bakın ve manuel olarak düzeltin."
fi

echo "=================================================="
exit $EXIT_CODE
