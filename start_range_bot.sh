#!/bin/bash
# Range Trading Bot - İki terminal başlatıcı

echo "🚀 RANGE TRADING BOT BAŞLATILIYOR..."
echo "======================================"
echo ""
echo "Terminal 1: Range Scanner (pozisyon açar)"
echo "Terminal 2: Position Monitor (kapalı pozisyonları takip eder)"
echo ""
echo "Her ikisi de arka planda çalışacak."
echo "Logları kontrol etmek için:"
echo "  tail -f logs/range_main.log"
echo "  tail -f logs/range_monitor.log"
echo ""

# Logs klasörünü oluştur
mkdir -p logs

# 1. Range Main'i başlat
echo "1️⃣  Range Scanner başlatılıyor..."
nohup python3.11 range_main.py > logs/range_main.log 2>&1 &
MAIN_PID=$!
echo "   ✅ PID: $MAIN_PID"

sleep 2

# 2. Position Monitor'ü başlat
echo "2️⃣  Position Monitor başlatılıyor..."
nohup python3.11 range_position_monitor.py > logs/range_monitor.log 2>&1 &
MONITOR_PID=$!
echo "   ✅ PID: $MONITOR_PID"

echo ""
echo "======================================"
echo "✅ BOTLAR BAŞLATILDI!"
echo "======================================"
echo ""
echo "📊 Durum Kontrolü:"
echo "   ps aux | grep range_"
echo ""
echo "📜 Log Takibi:"
echo "   tail -f logs/range_main.log"
echo "   tail -f logs/range_monitor.log"
echo ""
echo "🛑 Durdurma:"
echo "   kill $MAIN_PID $MONITOR_PID"
echo ""
echo "💾 PID'ler kaydedildi: logs/bot_pids.txt"
echo "$MAIN_PID $MONITOR_PID" > logs/bot_pids.txt
