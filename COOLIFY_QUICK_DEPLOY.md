# 🚀 COOLIFY HIZLI DEPLOYMENT - v9.1

## 📌 DEPLOYMENT ADIMLARI

### ADIM 1: Coolify Dashboard
1. Coolify'a giriş yap
2. ChimeraBot projesini seç
3. Settings → Environment Variables

### ADIM 2: .env Değişkenleri Ekle
**ÖNEMLİ:** Bu 3 değişkeni Coolify'da ekle/güncelle:

```env
ENABLE_ROTATING_SCAN=True
MAX_COINS_TO_SCAN=300
SCAN_INTERVAL_MINUTES=2
```

### ADIM 3: Redeploy
Coolify'da "Redeploy" butonuna tıkla

**VEYA Manuel SSH:**

```bash
# SSH ile bağlan
ssh your_server

# ChimeraBot dizinine git
cd /path/to/ChimeraBot

# Deployment script'ini çalıştır
./COOLIFY_DEPLOYMENT_v9.1.sh
```

---

## ✅ DEPLOYMENT SONRASI KONTROL

### 1. Log İzle (5 dakika)
```bash
tail -f logs/chimerabot.log
```

**Aranacak Mesajlar:**
- ✅ "Trade Manager thread'i başlatıldı"
- ✅ "🔄 Rotating Scan: Coins [X→Y]"
- ✅ "Pre-screening tamamlandı: 300 → XXX"
- ✅ "BREAKOUT v9.0 (6-LAYER) kontrol ediliyor"

### 2. Telegram Test
```bash
python3 test_telegram.py
```

### 3. System Health
```bash
python3 system_health_check.py
```

---

## 🎯 İLK 30 DAKİKA KRİTİK!

**İZLENECEKLER:**
1. **Rotating Scan:** Offset değişiyor mu? (0→300→600→900...)
2. **Pre-screening:** 300 coin → 100-130 arası düşüyor mu?
3. **Multi-layer Filtering:** "Layer 1/2/3..." mesajları görünüyor mu?
4. **Binance Bağlantısı:** "Balance: $XXX" mesajı geliyor mu?

---

## ⚠️ v9.1 CRITICAL FIX TEST

**İLK SL/TP KAPANIŞINI MANUEL KONTROL ET!**

1. İlk pozisyon SL/TP'ye çarptığında log'da ara:
   ```
   🔴 [SYMBOL] Binance'de kapatılıyor...
   ✅ [SYMBOL] Binance'de kapatıldı! Gerçek fiyat: XXXXX
   ```

2. Binance Futures'ta kontrol et:
   - Pozisyon listesinde KAPALI olmalı ✅
   - Order history'de MARKET SELL/BUY görünmeli ✅

3. İlk 10 trade için bu kontrolü tekrarla

---

## 🚨 SORUN ÇIKARSA

### Bot Başlamıyor:
```bash
tail -100 logs/chimerabot.log
./emergency_stop.sh
./restart_bot.sh
```

### Sinyal Gelmiyor:
- **NORMAL!** İlk 2-4 saat sinyal gelmeyebilir
- Multi-layer filtering çok sıkı (istenen davranış)
- Market sideways ise bekle

### Telegram Çalışmıyor:
```bash
# .env kontrol
grep "TELEGRAM" .env
python3 test_telegram.py
```

---

## 📊 BEKLENEN PERFORMANS

**İlk 24 Saat:**
- Sinyal: 3-6 adet (eski: 18-30)
- Win Rate: Henüz ölçülemez
- Ghost Position: 0 adet (v9.1 fix)

**1 Hafta Sonra:**
- Win Rate: %60-75+
- Aylık ROI projeksiyon: %300+

---

**Deployment Tarihi:** 9 Kasım 2025  
**Status:** ✅ READY TO DEPLOY  
