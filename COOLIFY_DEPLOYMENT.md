# Coolify Deployment Configuration
# ChimeraBot v9.2 - Automated Cleanup on Deploy

## 🚀 Deployment Ayarları

### Pre-deploy Commands (Opsiyonel)
```bash
# Bot'u durdur (eğer çalışıyorsa)
pkill -f main_orchestrator.py || true
```

### Build Commands
```bash
# Python bağımlılıklarını yükle
pip install -r requirements.txt
```

### Post-deploy Commands (ÖNEMLİ!)
```bash
# Otomatik temizlik script'ini çalıştır
python auto_cleanup_on_deploy.py

# Bot'u başlat (arka planda)
nohup python src/main_orchestrator.py > logs/bot_output.log 2>&1 &
```

---

## 📋 Temizlik Script Detayları

**Script:** `auto_cleanup_on_deploy.py`

**Yaptığı İşlemler:**
1. ✅ Database backup oluşturur (`data/backups/`)
2. ✅ Açık pozisyonları kontrol eder (varsa UYARI verir)
3. ✅ Alpha cache tablosunu tamamen temizler (eski sentiment verileri)
4. ✅ 90+ günlük eski trade history kayıtlarını siler (opsiyonel)
5. ✅ Database VACUUM (optimize, boş alan geri al)
6. ✅ Eski backupları temizler (son 5'i tutar)
7. ✅ İstatistikleri loglar

**Log Dosyası:** `logs/deployment_cleanup.log`

---

## ⚠️ ÖNEMLİ NOTLAR

### 1. Açık Pozisyonlar
Eğer redeploy sırasında **açık pozisyonlar** varsa:
- Script UYARI verir ama pozisyonları KAPAMAZ!
- Manuel kapatmanız gerekir veya pozisyonlar devam eder
- Öneri: Redeploy öncesi tüm pozisyonları kapatın

### 2. Manuel Kullanım
Script'i manuel çalıştırmak için:
```bash
cd /Users/macbook/Desktop/ChimeraBot
python auto_cleanup_on_deploy.py
```

### 3. Backuplar
- Her deployment'ta otomatik backup
- Backuplar `data/backups/` klasöründe
- Son 5 backup korunur, eskiler silinir
- Backup formatı: `chimerabot_backup_YYYYMMDD_HHMMSS.db`

### 4. Trade History Temizliği
90+ günlük kayıtları silmek için script'te yorum satırını kaldırın:
```python
# Satır 179'u aktif et:
old_trades = clean_old_trade_history(conn, days=90)
```

---

## 🔧 Coolify Dashboard Ayarları

### Environment Variables (.env)
Coolify'da bu değişkenleri set edin:
```env
# Binance API
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Risk Management
MIN_MARGIN_USD=150.0
SL_TP_METHOD=SMART

# Python Environment
PYTHONUNBUFFERED=1
```

### Persistent Storage
Coolify'da bu klasörleri persistent yapın:
- `/app/data` → Database ve backuplar
- `/app/logs` → Log dosyaları

### Health Check
```bash
# Bot'un çalıştığını kontrol et
ps aux | grep main_orchestrator | grep -v grep
```

---

## 📊 Log Monitoring

### Deployment Logs
```bash
tail -f logs/deployment_cleanup.log
```

### Bot Logs
```bash
tail -f logs/chimerabot.log
```

### Son Deployment Özeti
```bash
tail -100 logs/deployment_cleanup.log | grep -E "CLEANUP|✅|❌|⚠️"
```

---

## 🎯 Best Practices

1. **Redeploy Öncesi:**
   - Tüm açık pozisyonları manuel kapat
   - Son backup'ı kontrol et
   - Log dosyalarını incele

2. **Redeploy Sırasında:**
   - Coolify otomatik script'i çalıştırır
   - Deployment log'ları izle
   - Hata varsa rollback yap

3. **Redeploy Sonrası:**
   - Bot'un başladığını doğrula (`ps aux | grep main`)
   - İlk sinyal gelene kadar log'ları izle
   - Database istatistiklerini kontrol et

---

## 🔄 Rollback Prosedürü

Eğer deployment başarısız olursa:

1. **Backup'tan Geri Yükle:**
   ```bash
   cd data/backups
   cp chimerabot_backup_YYYYMMDD_HHMMSS.db ../chimerabot.db
   ```

2. **Önceki Commit'e Dön:**
   ```bash
   git log --oneline -5
   git reset --hard <commit_hash>
   git push -f origin main
   ```

3. **Bot'u Yeniden Başlat:**
   ```bash
   pkill -f main_orchestrator.py
   python src/main_orchestrator.py
   ```

---

## 📞 Sorun Giderme

### Script Çalışmıyor
```bash
# Script'e execute izni ver
chmod +x auto_cleanup_on_deploy.py

# Python3 ile manuel çalıştır
python3 auto_cleanup_on_deploy.py
```

### Database Kilitli
```bash
# Tüm bot processlerini durdur
pkill -f main_orchestrator.py
pkill -f python

# Sonra tekrar dene
python auto_cleanup_on_deploy.py
```

### Backup Klasörü Yok
```bash
mkdir -p data/backups
```

---

## 📝 Changelog

**v9.2 (10 Kasım 2025):**
- ✅ Otomatik deployment cleanup script eklendi
- ✅ Database backup sistemi
- ✅ Alpha cache otomatik temizleme
- ✅ Açık pozisyon uyarı sistemi
- ✅ Database optimization (VACUUM)
- ✅ Eski backup cleanup
