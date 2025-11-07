#!/bin/bash
# testnet_setup.sh - Testnet hazırlık scripti

cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║           BINANCE TESTNET KURULUM KONTROL LİSTESİ            ║
╚══════════════════════════════════════════════════════════════╝

✅ TAMAMLANAN:
  [✓] Executor modülü hazır
  [✓] Capital Manager hazır
  [✓] Database güncellemeleri yapıldı
  [✓] main_orchestrator.py güncellendi
  [✓] trade_manager.py güncellendi
  [✓] BINANCE_TESTNET=True ayarlandı

⚠️ YAPMANZ GEREKENLER:

1️⃣ TESTNET API KEY AL
   → https://testnet.binancefuture.com/
   → GitHub/Google ile giriş yap
   → Profile > API Key > Generate HMAC_SHA256 Key
   
2️⃣ API KEY'LERİ .env'E EKLE
   .env dosyasını aç ve şunları güncelle:
   
   BINANCE_TESTNET_API_KEY=<buraya_api_key_yapıştır>
   BINANCE_TESTNET_SECRET_KEY=<buraya_secret_key_yapıştır>

3️⃣ TEST USDT AL (ÜCRETSİZ!)
   → https://testnet.binancefuture.com/en/futures/BTCUSDT
   → Faucet butonuna tıkla
   → 10,000 USDT ücretsiz al (her gün yenilenebilir)

4️⃣ SİSTEMİ BAŞLAT
   python src/main_orchestrator.py

═══════════════════════════════════════════════════════════════

📊 TESTNET AVANTAJLARI:
  • Gerçek piyasa verileri, gerçek fiyatlar
  • Sıfır risk - test parası kullanılır
  • Sınırsız deneme hakkı
  • Tüm Binance Futures özellikleri aktif
  • API limitleri daha esnek

🎯 TEST ETMENİZ GEREKENLER:
  1. Bot başlatma ve bağlantı
  2. Sinyal bulma ve pozisyon açma
  3. SL/TP emirlerinin yerleşmesi
  4. Trailing Stop çalışması
  5. Pozisyon kapanma ve PnL kaydı
  6. Telegram bildirimleri
  7. Devre kesici (MAX_DRAWDOWN_PERCENT ayarını -10% yapıp test edin)
  8. Capital Manager saatlik kontrol

⚠️ DİKKAT:
  • Testnet bazen bakım için kapatılabilir
  • Testnet API rate limitleri gerçek hesaptan farklıdır
  • Test USDT gerçek değildir, çekilemez!

═══════════════════════════════════════════════════════════════
EOF

# Testnet API key kontrolü
echo ""
echo "🔍 Mevcut Ayarlar Kontrol Ediliyor..."
echo ""

if grep -q "YOUR_TESTNET_API_KEY_HERE" .env; then
    echo "❌ TESTNET API KEY henüz eklenmemiş!"
    echo "   Lütfen .env dosyasını düzenleyin:"
    echo "   BINANCE_TESTNET_API_KEY=<gerçek_key>"
    echo ""
else
    echo "✅ Testnet API Key bulundu"
fi

if grep -q "BINANCE_TESTNET=True" .env; then
    echo "✅ Testnet modu AKTİF"
else
    echo "⚠️ Testnet modu pasif! .env'de BINANCE_TESTNET=True yapın"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "Hazır olduğunuzda şu komutu çalıştırın:"
echo "  python src/main_orchestrator.py"
echo "═══════════════════════════════════════════════════════════════"
