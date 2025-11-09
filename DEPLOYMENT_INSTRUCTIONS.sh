#!/bin/bash
# Coolify Deployment Instructions
# Bu script'i OKUYUN, Coolify'da MANUEL olarak uygulayın

cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║  🚨 COOLIFY DEPLOYMENT - ACİL MÜDAHALE GEREKLİ             ║
╚══════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────┐
│  DURUM: Bot çalışıyor AMA pozisyon açamıyor                 │
│  HATA: "no such column: open_positions.initial_sl"          │
│  ÇÖZÜM: Emergency DB migration (tek komut)                   │
└──────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════

📋 ADIMLAR (5 Dakika)

1️⃣  Coolify Dashboard → chimerabot service → Terminal

2️⃣  Aşağıdaki komutu çalıştır:

    cd /app && ./emergency_db_fix.sh

3️⃣  Beklenen çıktı:

    ✅ HOTFIX BAŞARILI - BOT YENİDEN BAŞLATILABİLİR

4️⃣  Bot'u restart et:

    supervisorctl restart chimerabot
    
    # VEYA Coolify dashboard'dan "Restart" butonuna bas

5️⃣  Logları kontrol et (30 saniye bekle):

    tail -f logs/chimerabot.log

    Beklenen: 
    - ✅ "Scan cycle başladı"
    - ✅ Coin analiz logları
    - ❌ "no such column" hatası YOK

═══════════════════════════════════════════════════════════════

🔍 VERİFİCATION

Eğer migration başarılı olduysa:
- ✅ emergency_db_fix.sh exit code 0
- ✅ "Tüm kritik kolonlar mevcut (5/5)" mesajı
- ✅ Bot restart sonrası scan başladı
- ✅ İlk 10 dakikada DB hatası yok

═══════════════════════════════════════════════════════════════

⚠️  SORUN GİDERME

EĞER migration başarısız olursa:

  Problem: "Permission denied"
  Çözüm:  chmod +x /app/emergency_db_fix.sh

  Problem: "Python not found"
  Çözüm:  which python3 (path'i bulup script'te düzelt)

  Problem: "DB locked"
  Çözüm:  supervisorctl stop chimerabot
          ./emergency_db_fix.sh
          supervisorctl start chimerabot

  Problem: "No such file: migrations/..."
  Çözüm:  Git pull yapıldı mı? ls -la migrations/

═══════════════════════════════════════════════════════════════

📞 TELEGRAM KONTROLÜ

Migration sonrası Telegram'dan şu mesajları bekleyin:

1. "🔄 ChimeraBot başlatıldı" (bot restart sonrası)
2. "📊 BTC Regime: BREAKOUT (ADX=...)" (regime belirleme)
3. "📊 Tarama tamamlandı: X coin analiz edildi" (scan cycle)

Eğer 10 dakika içinde hiç mesaj gelmiyorsa:
- Logs'a bak: "ERROR" ara
- Trade manager thread çalışıyor mu kontrol et

═══════════════════════════════════════════════════════════════

✅ BAŞARILI DEPLOYMENT SONRASI

□ Migration tamamlandı
□ Bot restart edildi
□ Loglar temiz (no DB errors)
□ Telegram notifications geliyor
□ İlk scan cycle tamamlandı (2-10 dakika)
□ Binance API bağlantısı OK (futures symbols çekildi)
□ Alpha cache güncellendi (F&G, news)

═══════════════════════════════════════════════════════════════

🎯 BİR SONRAKİ ADIM

Migration düzeldikten sonra:

1. 24 saat bekle (sistem stabilize olsun)
2. Performance metrics kontrol et:
   - Kaç sinyal üretildi?
   - Kaç pozisyon açıldı?
   - Quality grade dağılımı (A/B/C/D)?
   - Telegram logları incele

3. Profitability Roadmap'e geç (PROFITABILITY_ROADMAP.md):
   - Sprint 1: Quick Wins (1-2 hafta)
   - Quality filter sıkılaştırma
   - TP2 optimization
   - Volatility spike rejection

═══════════════════════════════════════════════════════════════

📚 DOKÜMANTASYON

□ DB_MIGRATION_FIX.md - Bu sorunun detaylı açıklaması
□ COOLIFY_READY.md - Deployment rehberi (migration section eklendi)
□ PROFITABILITY_ROADMAP.md - Kârlılık iyileştirme planı
□ emergency_db_fix.sh - Tek komut hotfix script

═══════════════════════════════════════════════════════════════

💡 İPUCU

Gelecekte benzer sorunları önlemek için:

1. Her deployment öncesi migration kontrol et:
   python3 migrations/add_advanced_risk_columns.py

2. CI/CD pipeline'a ekle (Dockerfile):
   RUN python3 migrations/*.py || true

3. Health check ekle (container startup script):
   Test OpenPosition tablosu → Kritik kolonlar var mı?

═══════════════════════════════════════════════════════════════

🚀 HADİ BAŞLAYALIM!

Coolify terminal'e git ve şu komutu çalıştır:

    cd /app && ./emergency_db_fix.sh

Başarılı olursa buraya dön ve bot'u restart et.

İyi şanslar! 🍀

EOF
