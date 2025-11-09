# Otomatik Cache & DB Temizlik Sistemi

## 📋 Genel Bakış

ChimeraBot için 3 farklı temizlik yöntemi:

1. **Manuel Temizlik**: İstendiğinde çalıştırma
2. **Cron Job**: Sistem bazlı scheduled (önerilen)
3. **Python Scheduler**: Python içinde schedule library

---

## 🚀 Kullanım Yöntemleri

### 1️⃣ Manuel Temizlik

```bash
# Varsayılan parametrelerle
python3.11 cleanup_cache_db.py

# Özel parametrelerle
python3.11 cleanup_cache_db.py \
    --cache-days 14 \
    --trade-history-days 180 \
    --alpha-cache-hours 72 \
    --log-days 30 \
    --no-vacuum
```

**Parametreler:**
- `--cache-days`: Backtest cache saklama süresi (default: 7)
- `--trade-history-days`: Trade history saklama süresi (default: 90)
- `--alpha-cache-hours`: Alpha cache saklama süresi (default: 48)
- `--log-days`: Log dosyası saklama süresi (default: 14)
- `--no-vacuum`: SQLite VACUUM yapma

**Shell script alternatifi:**
```bash
./run_cleanup.sh
```

---

### 2️⃣ Cron Job (Önerilen - Sistem Bazlı)

#### macOS/Linux Kurulum

1. **Crontab'ı düzenle:**
```bash
crontab -e
```

2. **Zamanlamayı ekle:**

**Haftalık temizlik (Pazar 03:00):**
```cron
0 3 * * 0 /Users/macbook/Desktop/ChimeraBot/run_cleanup.sh >> /Users/macbook/Desktop/ChimeraBot/logs/cleanup_cron.log 2>&1
```

**Günlük temizlik (Her gün 03:00):**
```cron
0 3 * * * /Users/macbook/Desktop/ChimeraBot/run_cleanup.sh >> /Users/macbook/Desktop/ChimeraBot/logs/cleanup_cron.log 2>&1
```

**Haftalık + Hafta ortası temizlik (Pazar ve Çarşamba):**
```cron
0 3 * * 0,3 /Users/macbook/Desktop/ChimeraBot/run_cleanup.sh >> /Users/macbook/Desktop/ChimeraBot/logs/cleanup_cron.log 2>&1
```

3. **Cron zamanlaması kontrol et:**
```bash
crontab -l
```

#### Cron Zaman Formatı
```
* * * * * komut
│ │ │ │ │
│ │ │ │ └─── Haftanın günü (0-7, 0=Pazar, 7=Pazar)
│ │ │ └───── Ay (1-12)
│ │ └─────── Ayın günü (1-31)
│ └───────── Saat (0-23)
└─────────── Dakika (0-59)
```

**Örnekler:**
- `0 3 * * *` = Her gün 03:00
- `0 3 * * 0` = Her Pazar 03:00
- `0 3 * * 1,4` = Her Pazartesi ve Perşembe 03:00
- `0 */6 * * *` = Her 6 saatte bir
- `30 2 1 * *` = Her ayın 1'i saat 02:30

---

### 3️⃣ Python Scheduler (Background Service)

**Nohup ile arka planda çalıştırma:**
```bash
nohup python3.11 cleanup_scheduler.py > logs/scheduler.log 2>&1 &
```

**Systemd service (production için):**
```bash
sudo nano /etc/systemd/system/chimerabot-cleanup.service
```

```ini
[Unit]
Description=ChimeraBot Cleanup Scheduler
After=network.target

[Service]
Type=simple
User=macbook
WorkingDirectory=/Users/macbook/Desktop/ChimeraBot
ExecStart=/usr/local/bin/python3.11 /Users/macbook/Desktop/ChimeraBot/cleanup_scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable chimerabot-cleanup.service
sudo systemctl start chimerabot-cleanup.service
sudo systemctl status chimerabot-cleanup.service
```

---

## 🔧 Temizlik Detayları

### Backtest Cache
- **Konum:** `data/backtest_cache/*.csv`
- **Temizlik:** `cache_days` günden eski CSV dosyaları silinir
- **Örnek:** 7 günlük ayar → 2025-11-02'den eski dosyalar silinir

### Trade History
- **Konum:** SQLite DB → `trade_history` tablosu
- **Temizlik:** `trade_history_days` günden eski kayıtlar silinir
- **Korunan:** Son 90 gün (default)

### Alpha Cache
- **Konum:** SQLite DB → `alpha_cache` tablosu
- **Temizlik:** `alpha_cache_hours` saatten eski cache silinir
- **Korunan Keyler:**
  - `fear_greed_index` (F&G Index)
  - `correlation_matrix` (Korelasyon matrisi)
  - `futures_symbols_list` (Futures sembol listesi)

### Log Dosyaları
- **Konum:** `logs/*.log`
- **Temizlik:** `log_days` günden eski log dosyaları silinir
- **Örnek:** 14 günlük ayar → 2025-10-26'dan eski loglar silinir

### SQLite VACUUM
- **Amaç:** DB dosya boyutunu optimize et
- **Ne zaman:** Haftalık temizlikte (optional)
- **Etki:** Silinmiş kayıtların disk alanını geri kazanır

---

## 📊 Örnek Çıktı

```
================================================================================
🧹 OTOMATIK TEMİZLİK BAŞLATILIYOR
================================================================================
🧹 Backtest cache temizleniyor (7 günden eski)...
   ✅ 12 dosya silindi, 45.23 MB boşaltıldı
🧹 Trade history temizleniyor (90 günden eski)...
   ✅ 234 kayıt silindi
🧹 Alpha cache temizleniyor (48 saatten eski)...
   ✅ 15 kayıt silindi (3 korunan key atlandı)
🧹 Eski log dosyaları temizleniyor (14 günden eski)...
   ✅ 8 log dosyası silindi, 12.45 MB boşaltıldı
🧹 SQLite veritabanı optimize ediliyor (VACUUM)...
   ✅ VACUUM tamamlandı, 3.21 MB boşaltıldı

================================================================================
✅ TEMİZLİK TAMAMLANDI
================================================================================
📊 Özet:
   Backtest cache: 12 dosya
   Trade history: 234 kayıt
   Alpha cache: 15 kayıt
   Log dosyaları: 8 dosya
   Toplam boşaltılan: 60.89 MB
   Süre: 2.3 saniye
```

---

## ⚠️ Önemli Notlar

1. **Korunan Veriler:**
   - Critical alpha cache keyleri asla silinmez
   - Açık pozisyonlar (`open_positions`) etkilenmez
   - Son N günlük veriler korunur

2. **Disk Alanı:**
   - Temizlik öncesi backup almaya gerek yok (sadece eski veriler silinir)
   - VACUUM önemli alan kazandırır (özellikle uzun süreli kullanımda)

3. **Performans:**
   - Temizlik genellikle <5 saniye sürer
   - Bot çalışırken temizlik yapılabilir (thread-safe)
   - VACUUM sırasında kısa DB kilidi (1-2 saniye)

4. **Log Takibi:**
   - Cron job logları: `logs/cleanup_cron.log`
   - Scheduler logları: `logs/cleanup_scheduler.log`
   - Temizlik detayları loglarda kaydedilir

---

## 🔍 Sorun Giderme

### Cron çalışmıyor
```bash
# Cron service kontrolü
sudo systemctl status cron

# Cron loglarına bak
grep CRON /var/log/syslog

# Script izinlerini kontrol et
ls -la run_cleanup.sh
chmod +x run_cleanup.sh
```

### Python bulunamıyor hatası
```bash
# Which python kullanıyor?
which python3.11

# Cron job'da tam path kullan
0 3 * * 0 /usr/local/bin/python3.11 /tam/path/cleanup_cache_db.py
```

### SQLite locked hatası
- Bot ve temizlik aynı anda DB'ye yazıyor olabilir
- Temizliği bot duruyorken çalıştırın veya farklı saate alın

---

## 📅 Önerilen Zamanlama

**Küçük kullanım (test/development):**
- Haftalık temizlik (Pazar 03:00)
- Parametreler: Default (7 gün cache, 90 gün history)

**Orta kullanım (production):**
- Hafta içi hafif (Çarşamba 03:00, VACUUM yok)
- Hafta sonu ağır (Pazar 04:00, VACUUM dahil)

**Yoğun kullanım (heavy trading):**
- Günlük hafif (Her gün 03:00, VACUUM yok)
- Haftalık ağır (Pazar 04:00, VACUUM dahil)
- Aylık derin temizlik (Her ayın 1'i, daha agresif retention)

---

## 🎯 Hızlı Başlangıç

**En basit yöntem (Cron ile haftalık):**

```bash
# 1. Crontab aç
crontab -e

# 2. Bu satırı ekle (Pazar sabahı 3'te çalışır)
0 3 * * 0 /Users/macbook/Desktop/ChimeraBot/run_cleanup.sh >> /Users/macbook/Desktop/ChimeraBot/logs/cleanup_cron.log 2>&1

# 3. Kaydet ve çık (:wq)

# 4. Kontrol et
crontab -l
```

✅ Tamamdır! Her Pazar sabahı otomatik temizlik yapılacak.
