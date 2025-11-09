#!/bin/bash
# Post-Deployment Verification Checklist
# ChimeraBot v9.1 - Coolify

echo "🔍 ChimeraBot v9.1 Deployment Verification"
echo "=========================================="
echo ""

# 1. Bot çalışıyor mu?
echo "✅ 1. Bot Process Kontrolü:"
if pgrep -f "main_orchestrator.py" > /dev/null; then
    echo "   ✅ Bot çalışıyor!"
    ps aux | grep main_orchestrator.py | grep -v grep
else
    echo "   ❌ Bot çalışmıyor! Başlatılıyor..."
    nohup python3 src/main_orchestrator.py > logs/bot.log 2>&1 &
    sleep 3
    if pgrep -f "main_orchestrator.py" > /dev/null; then
        echo "   ✅ Bot başlatıldı!"
    else
        echo "   ❌ Bot başlatılamadı! logs/bot.log kontrol edin"
        exit 1
    fi
fi
echo ""

# 2. Log kontrolü
echo "✅ 2. Son 20 Log Satırı:"
tail -20 logs/chimerabot.log
echo ""

# 3. Telegram test
echo "✅ 3. Telegram Test:"
python3 test_telegram.py
echo ""

# 4. Database kontrolü
echo "✅ 4. Database Durumu:"
if [ -f "data/chimerabot.db" ]; then
    echo "   Açık Pozisyonlar: $(sqlite3 data/chimerabot.db 'SELECT COUNT(*) FROM open_positions;')"
    echo "   Trade History: $(sqlite3 data/chimerabot.db 'SELECT COUNT(*) FROM trade_history;')"
    echo "   Son Trade:"
    sqlite3 data/chimerabot.db "SELECT symbol, direction, close_reason, pnl_usd, pnl_percent FROM trade_history ORDER BY close_time DESC LIMIT 1;"
else
    echo "   ⚠️ Database bulunamadı!"
fi
echo ""

# 5. v9.1 CRITICAL FIX Kontrolü
echo "✅ 5. v9.1 CRITICAL FIX Kontrolü:"
echo "   (İlk SL/TP tetiklendiğinde manuel kontrol et)"
echo "   → Binance Futures'ta pozisyonu kontrol et"
echo "   → Log'da 'Binance'de kapatıldı!' araması:"
grep -c "Binance'de kapatıldı" logs/chimerabot.log 2>/dev/null || echo "   Henüz SL/TP tetiklenmemiş"
echo ""

# 6. Versiyon kontrolü
echo "✅ 6. Git Versiyon:"
git log --oneline -1
echo ""

# 7. Environment kontrol
echo "✅ 7. Trading Mode:"
if [ -f ".env" ]; then
    echo "   BINANCE_TESTNET=$(grep BINANCE_TESTNET .env | cut -d'=' -f2)"
    echo "   ENABLE_REAL_TRADING=$(grep ENABLE_REAL_TRADING .env | cut -d'=' -f2)"
else
    echo "   ⚠️ .env dosyası bulunamadı!"
fi
echo ""

echo "=========================================="
echo "🎯 DEPLOYMENT VERIFICATION TAMAMLANDI"
echo ""
echo "⚠️  SONRAKİ ADIMLAR:"
echo "   1. İlk 30 dakika log'ları izle:"
echo "      tail -f logs/chimerabot.log"
echo ""
echo "   2. İlk SL/TP tetiklendiğinde (v9.1 FIX):"
echo "      → Binance Futures'ta pozisyonu kontrol et"
echo "      → Pozisyon KAPANMIŞ OLMALI"
echo "      → Log'da 'Binance'de kapatıldı!' görmelisin"
echo ""
echo "   3. İlk 10 trade'i manuel kontrol et"
echo "      → DB'de kapatılmış"
echo "      → Binance'de kapatılmış"
echo "      → PnL doğru hesaplanmış"
echo ""
