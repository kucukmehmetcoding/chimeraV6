#!/bin/bash
# Emergency Stop - Tüm trading'i durdur

echo "========================================"
echo "🚨 EMERGENCY STOP AKTIFLEŞTIRILIYOR"
echo "========================================"

# Stop flag dosyası oluştur
touch /Users/macbook/Desktop/ChimeraBot/EMERGENCY_STOP.flag
echo "✅ Emergency stop flag oluşturuldu"

# Bot process'ini durdur
echo "🔴 Bot durdurluyor..."
pkill -f "main_orchestrator.py"

echo ""
echo "========================================"
echo "✅ EMERGENCY STOP TAMAMLANDI!"
echo "========================================"
echo ""
echo "Bot durduruldu ve yeni pozisyon açılmayacak."
echo ""
echo "Devam etmek için:"
echo "  1. rm /Users/macbook/Desktop/ChimeraBot/EMERGENCY_STOP.flag"
echo "  2. python src/main_orchestrator.py"
echo ""
