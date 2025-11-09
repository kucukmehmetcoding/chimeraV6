#!/bin/bash
# Emergency DB Migration Hotfix
# Coolify'da "no such column" hatasını düzeltir

set -e

echo "=================================================="
echo "🚨 EMERGENCY DB MIGRATION HOTFIX"
echo "=================================================="
echo "Tarih: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

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
echo ""

# DB yolunu kontrol et
DB_PATH="data/chimerabot.db"
if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "✓ DB bulundu: $DB_PATH ($DB_SIZE)"
else
    echo "⚠️  UYARI: DB dosyası bulunamadı: $DB_PATH"
    echo "   Yeni DB oluşturulacak..."
fi

echo ""
echo "🔄 Migration başlatılıyor..."
echo ""

# Migration çalıştır
$PYTHON_CMD migrations/add_advanced_risk_columns.py

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Migration başarılı!"
    echo ""
    
    # Verification
    echo "🔍 Verification yapılıyor..."
    $PYTHON_CMD << 'PYEOF'
from src.database.models import db_session, OpenPosition

critical_cols = ['initial_sl', 'trailing_stop_distance', 'high_water_mark', 
                 'partial_tp_1_price', 'partial_tp_2_price']

db = db_session()
try:
    columns = [c.name for c in OpenPosition.__table__.columns]
    missing = [col for col in critical_cols if col not in columns]
    
    if missing:
        print(f"❌ EKSİK KOLONLAR: {', '.join(missing)}")
        exit(1)
    else:
        print(f"✅ Tüm kritik kolonlar mevcut ({len(critical_cols)}/5)")
        
    count = db.query(OpenPosition).count()
    print(f"✅ OpenPosition tablosu erişilebilir ({count} kayıt)")
    
except Exception as e:
    print(f"❌ Verification hatası: {e}")
    exit(1)
finally:
    db_session.remove()
PYEOF
    
    VERIFY_EXIT=$?
    
    echo ""
    if [ $VERIFY_EXIT -eq 0 ]; then
        echo "=================================================="
        echo "✅ HOTFIX BAŞARILI - BOT YENİDEN BAŞLATILABİLİR"
        echo "=================================================="
        echo ""
        echo "Sonraki adım:"
        echo "  supervisorctl restart chimerabot"
        echo "  # veya Coolify dashboard'dan restart"
        echo ""
    else
        echo "❌ Verification başarısız!"
        echo "Manuel kontrol gerekiyor."
        exit 1
    fi
    
else
    echo "❌ Migration başarısız (exit code: $EXIT_CODE)"
    echo ""
    echo "Troubleshooting:"
    echo "1. DB dosyası var mı? ls -lh data/chimerabot.db"
    echo "2. Write permission var mı? touch data/test.tmp"
    echo "3. Migration loglarına bak (yukarıda)"
    exit 1
fi

echo "=================================================="
exit 0
