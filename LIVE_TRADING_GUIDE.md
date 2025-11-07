# 🚀 ChimeraBot - LIVE TRADING KULLANIM KILAVUZU

## ⚠️ TESTNET'TEN LIVE'A GEÇIŞ

### **ADIM 1: .env Dosyasını Düzenle**

```bash
nano .env
```

Değişiklik yapılacak satır:
```bash
# TESTNET mode için:
BINANCE_TESTNET=True

# LIVE mode için (GERÇEK PARA):
BINANCE_TESTNET=False
```

**NOT:** API anahtarları zaten .env'de mevcut:
- ✅ Testnet keys: BINANCE_TESTNET_API_KEY
- ✅ Live keys: BINANCE_API_KEY

---

### **ADIM 2: Botu Başlat**

```bash
python src/main_orchestrator.py
```

**LIVE MODE İSE:**
- 10 saniyelik onay süresi olacak
- Sistem parametreleri ekranda gösterilecek
- Ctrl+C ile iptal edebilirsiniz

---

## 🚨 ACİL DURUM DURDURMA

### **Tüm Trading'i Hemen Durdur:**

```bash
./emergency_stop.sh
```

**Ne Yapar:**
1. Bot process'ini sonlandırır
2. EMERGENCY_STOP.flag dosyası oluşturur
3. Yeni pozisyon açılmasını engeller
4. Mevcut pozisyonlar Binance'de kalır (SL/TP'ler aktif)

---

### **Trading'i Yeniden Başlat:**

```bash
./resume_trading.sh
```

**Ne Yapar:**
1. EMERGENCY_STOP.flag dosyasını siler
2. Botu yeniden başlatır
3. Normal tarama döngüsü devam eder

---

## 📊 MEVCUT SİSTEM PARAMETRELERİ

```
✅ Maksimum Pozisyon: 10
✅ İşlem Başına Risk: %2
✅ Grup Riski Limiti: %50
✅ Dinamik Kaldıraç: 3x-5x-8x (Volatilite bazlı)
✅ Sinyal Kalitesi: A/B/C/D grade sistemi
✅ Binance API: Gerçek PnL/Margin tracking
✅ WebSocket: Real-time fiyat takibi
✅ SL/TP: Otomatik emir yerleştirme
```

**HİÇBİR PARAMETREYİ DEĞİŞTİRMEYİN!**

Sistem optimize edilmiş durumda.

---

## 🎯 GÜNLÜK KONTROL LİSTESİ

### **Her Sabah:**
```bash
# Portföy durumunu kontrol et
tail -100 logs/chimerabot.log | grep "PORTFÖY"

# Açık pozisyonları gör
sqlite3 data/chimerabot.db "SELECT symbol, direction, entry_price, leverage FROM open_positions;"
```

### **Her Akşam:**
```bash
# Performans raporunu gör
tail -200 logs/chimerabot.log | grep "PERFORMANS ÖZETİ" -A 10
```

---

## 📱 TELEGRAM BİLDİRİMLERİ

Bot otomatik olarak şu durumlarda mesaj gönderir:

✅ Yeni pozisyon açıldığında
✅ Pozisyon kapandığında (SL/TP)
✅ Hata oluştuğunda

Telegram bot token zaten .env'de tanımlı.

---

## 🔒 GÜVENLİK ÖNERİLERİ

1. **İlk Hafta:**
   - Her gün logları kontrol edin
   - Açılan pozisyonların kalitesini değerlendirin
   - Win rate'i takip edin

2. **Emergency Stop Kullanımı:**
   - Piyasada anormal hareketler görürseniz
   - Sistem hataları tespit ederseniz
   - Tatile çıkacaksanız

3. **Binance Hesabı:**
   - 2FA (Two-Factor Authentication) aktif olsun
   - API key'lerde "Trade" yetkisi olsun
   - "Withdraw" yetkisi OLMASIN (güvenlik için)

---

## ❓ SORUN GİDERME

**Bot çalışmıyor:**
```bash
# Process kontrolü
ps aux | grep main_orchestrator

# Logları kontrol et
tail -50 logs/chimerabot.log
```

**Emergency Stop kaldırmıyor:**
```bash
# Manuel kaldırma
rm EMERGENCY_STOP.flag
```

**Pozisyon açılmıyor:**
```bash
# Binance bağlantısını test et
python -c "from src.data_fetcher import binance_fetcher; print(binance_fetcher.get_current_price('BTCUSDT'))"
```

---

## 📞 İLETİŞİM

Herhangi bir sorun için:
- Telegram: @YourUsername
- GitHub Issues: [Link]

---

**⚠️ UYARI: Bu bot gerçek para ile trading yapar. Riski anlayıp kabul ettiğinizden emin olun!**
