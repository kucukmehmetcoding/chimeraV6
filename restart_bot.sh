#!/bin/bash
# Bot Yeniden Başlatma Script

echo "🔄 Bot yeniden başlatılıyor..."

# Çalışan bot'u bul ve durdur
PID=$(ps aux | grep "main_orchestrator.py" | grep -v grep | awk '{print $2}')

if [ -n "$PID" ]; then
    echo "   🛑 Mevcut bot durduruluyor (PID: $PID)..."
    kill $PID
    sleep 2
    
    # Hala çalışıyorsa zorla durdur
    if ps -p $PID > /dev/null 2>&1; then
        echo "   ⚠️  Zorla durduruluyor..."
        kill -9 $PID
    fi
    
    echo "   ✅ Bot durduruldu"
else
    echo "   ℹ️  Zaten çalışan bot yok"
fi

echo ""
echo "   🧹 Cache temizleniyor..."
./clear_cache.sh

echo ""
echo "   🚀 Bot başlatılıyor..."
python src/main_orchestrator.py

echo ""
echo "✅ Bot yeniden başlatıldı!"
