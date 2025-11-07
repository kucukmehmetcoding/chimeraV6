#!/bin/bash
# Resume Trading - Emergency stop'u kaldır ve botu başlat

echo "========================================"
echo "✅ TRADING DEVAM ETTIRILIYOR"
echo "========================================"

# Stop flag dosyasını sil
if [ -f "/Users/macbook/Desktop/ChimeraBot/EMERGENCY_STOP.flag" ]; then
    rm /Users/macbook/Desktop/ChimeraBot/EMERGENCY_STOP.flag
    echo "✅ Emergency stop flag kaldırıldı"
else
    echo "ℹ️  Emergency stop zaten aktif değil"
fi

echo ""
echo "🚀 Bot başlatılıyor..."
cd /Users/macbook/Desktop/ChimeraBot
nohup python src/main_orchestrator.py > logs/bot.out 2>&1 &

sleep 2
echo ""
echo "========================================"
echo "✅ TRADING BAŞLATILDI!"
echo "========================================"
echo ""
echo "Logları takip etmek için:"
echo "  tail -f logs/chimerabot.log"
echo ""
