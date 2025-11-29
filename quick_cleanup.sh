#!/bin/bash
# Quick DB & Cache Cleanup Script

cd /Users/macbook/Desktop/ChimeraBot

echo "🧹 Hızlı Temizleme - Tüm database ve cache silinecek!"
echo ""
read -p "Devam edilsin mi? (y/N): " confirm

if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo ""
    python cleanup_db_cache.py << EOF
5
evet
EOF
else
    echo "❌ İptal edildi"
fi
