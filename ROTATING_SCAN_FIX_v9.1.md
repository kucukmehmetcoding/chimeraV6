# 🔄 Rotating Scan System v9.1 - Tüm Futures Coinlerinin Taranması

## 📌 SORUN TANIMI

**Kullanıcı Şikayeti:**
> "Futures'te 534 coin var ama sadece ilk 300 taranıyor. Diğer 234 coin hiç taranmıyor!"

**Root Cause:**
1. ✅ Rotating scan kodu **VARDDI** ama çalışmıyordu
2. ❌ `coin_scan_offset` global değişken restart'ta sıfırlanıyordu (persistence yok)
3. ❌ Coolify'da **ESKİ KOD** çalışıyordu (henüz deploy edilmemişti)

---

## ✅ ÇÖZÜM (v9.1 Enhancement)

### 1. **Offset Persistence Sistemi (DB-based)**

**Önceki Durum (v8.1 - HATALI):**
```python
# Global değişken - restart'ta kayboluyordu!
coin_scan_offset = 0
```

**Yeni Durum (v9.1 - ÇÖZÜLDÜ):**
```python
def get_coin_scan_offset():
    """DB'den yükle, yoksa 0 döndür"""
    cache_record = db.query(AlphaCache).filter(key == 'coin_scan_offset').first()
    return int(cache_record.value) if cache_record else 0

def save_coin_scan_offset(offset):
    """DB'ye kaydet (restart'ta korunur)"""
    # AlphaCache tablosuna kaydet
    
coin_scan_offset = get_coin_scan_offset()  # İlk başlangıçta DB'den yükle
```

### 2. **Her Cycle Sonunda DB'ye Kaydetme**

```python
# Offset artır VE DB'ye kaydet
coin_scan_offset += max_coins
save_coin_scan_offset(coin_scan_offset)  # 🆕 Persist et
logger.info(f"🔄 Yeni offset: {coin_scan_offset} (DB'ye kaydedildi)")
```

---

## 📊 ROTATING SCAN NASIL ÇALIŞIR?

### **Örnek Senaryo:**
- **Toplam Futures Coinleri:** 534 coin
- **MAX_COINS_TO_SCAN:** 300 coin/cycle
- **SCAN_INTERVAL_MINUTES:** 2 dakika

### **Cycle Akışı:**

| Cycle | Offset | Taranan Coinler | Süre |
|-------|--------|-----------------|------|
| **1** | 0 | [0→299] (300 coin) | 0-2dk |
| **2** | 300 | [300→533] (234 coin) | 2-4dk |
| **3** | 534 → 0 (wrap) | [0→299] (300 coin) | 4-6dk |
| **4** | 300 | [300→533] (234 coin) | 6-8dk |

**Sonuç:** 
- **4 dakikada TÜM 534 coin taranır** (2 cycle)
- **Her coin ~4 dakikada bir analiz edilir**
- **Bot restart edilse bile offset DB'de korunur**

---

## 🎯 AVANTAJLAR

### **ÖNCE (v8.1 - Broken):**
```
Restart 1: [0→299] → [0→299] → [0→299] (offset sıfırlanıyor!)
  └─ İlk 300 coin sürekli taranıyor
  └─ Kalan 234 coin HİÇ taranmıyor ❌
```

### **ŞIMDI (v9.1 - Fixed):**
```
Restart 1: [0→299] → [300→533] → [0→299] → [300→533]
Restart 2: [300→533] → [0→299] → [300→533] → [0→299]
  └─ TÜM 534 coin döngüsel taranıyor ✅
  └─ Offset DB'de korunuyor ✅
  └─ Restart'tan sonra kaldığı yerden devam ediyor ✅
```

---

## 📋 YAPILANDIRILMIŞ AYARLAR

### **.env Dosyası:**
```bash
# Rotating scan AKTIF (varsayılan: True)
ENABLE_ROTATING_SCAN=True

# Her cycle'da kaç coin taranacak (varsayılan: 300)
MAX_COINS_TO_SCAN=300

# Tarama sıklığı (varsayılan: 2 dakika)
SCAN_INTERVAL_MINUTES=2
```

### **Performans Hesaplaması:**
```
Toplam Coin: 534
Max Coin/Cycle: 300
Cycle Süresi: 2 dakika

Cycle Sayısı: ceil(534 / 300) = 2 cycle
Toplam Süre: 2 cycle × 2dk = 4 dakika

→ 4 dakikada bir TÜM coinler taranır
→ Her coin ortalama 4dk'da bir analiz edilir
```

---

## 🔍 LOG MESAJLARI

### **Rotating Scan Aktif:**
```
🔄 Rotating Scan: Coins [0→299] / Total Pool (Total: 534 coins)
📊 Bu cycle'da 300 coin taranacak (offset: 0)
🔄 Yeni offset: 300 (DB'ye kaydedildi)
```

### **Sonraki Cycle:**
```
🔄 Rotating Scan: Coins [300→533] / Total Pool (Total: 534 coins)
📊 Bu cycle'da 234 coin taranacak (offset: 300)
🔄 Yeni offset: 534 (DB'ye kaydedildi)
```

### **Wrap-Around (Başa Dönüş):**
```
🔄 Rotating Scan: Coins [0→299] / Total Pool (Total: 534 coins)
📊 Bu cycle'da 300 coin taranacak (offset: 534 → 0)
🔄 Yeni offset: 300 (DB'ye kaydedildi)
```

### **Rotating Scan Kapalı:**
```
⚠️ Liste çok uzun (534), ilk 300 coin seçiliyor (Rotating KAPALI)
```

---

## 🧪 TEST SENARYOSU

### **Manuel Test:**
```bash
# 1. Offset kontrol
python3 -c "
from src.main_orchestrator import get_coin_scan_offset
print(f'Current offset: {get_coin_scan_offset()}')
"

# 2. Bot başlat
python3 src/main_orchestrator.py

# 3. İlk cycle log'unu izle
tail -f logs/chimerabot.log | grep "Rotating Scan"

# Beklenen çıktı:
# 🔄 Rotating Scan: Coins [0→299] / Total Pool (Total: 534 coins)

# 4. 2 dakika sonra (2. cycle)
# Beklenen çıktı:
# 🔄 Rotating Scan: Coins [300→533] / Total Pool (Total: 534 coins)

# 5. 4 dakika sonra (3. cycle - wrap-around)
# Beklenen çıktı:
# 🔄 Rotating Scan: Coins [0→299] / Total Pool (Total: 534 coins)
```

### **Persistence Test (Restart):**
```bash
# 1. Bot çalıştır (1 cycle bekle)
python3 src/main_orchestrator.py
# → Offset: 300 (DB'ye kaydedildi)

# 2. Bot'u durdur
Ctrl+C

# 3. Offset kontrol et
python3 -c "
from src.main_orchestrator import get_coin_scan_offset
print(f'Offset after restart: {get_coin_scan_offset()}')
"
# Beklenen: 300 (DB'den yüklendi)

# 4. Bot'u tekrar başlat
python3 src/main_orchestrator.py

# 5. Log kontrol
tail -f logs/chimerabot.log | grep "offset"
# Beklenen:
# 🔄 Coin scan offset DB'den yüklendi: 300
# 🔄 Rotating Scan: Coins [300→533] / Total Pool
```

---

## 📂 DATABASE SCHEMA

### **AlphaCache Tablosu:**
```sql
CREATE TABLE alpha_cache (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE,  -- 'coin_scan_offset'
    value TEXT,       -- '300', '534', '0', vb.
    last_updated TIMESTAMP
);

-- Örnek kayıt:
INSERT INTO alpha_cache (key, value) VALUES ('coin_scan_offset', '300');
```

### **Manuel Offset Sıfırlama:**
```sql
-- Offset'i manuel sıfırla
UPDATE alpha_cache SET value = '0' WHERE key = 'coin_scan_offset';

-- Veya Python'dan:
from src.main_orchestrator import save_coin_scan_offset
save_coin_scan_offset(0)
```

---

## ⚙️ YÖNETİM KOMUTLARI

### **Offset Durumunu Görüntüle:**
```python
python3 -c "
from src.main_orchestrator import get_coin_scan_offset
print(f'Current offset: {get_coin_scan_offset()}')
"
```

### **Offset'i Manuel Değiştir:**
```python
python3 -c "
from src.main_orchestrator import save_coin_scan_offset
save_coin_scan_offset(300)  # 2. cycle'dan başlat
print('Offset set to 300')
"
```

### **Offset'i Sıfırla (Baştan Başlat):**
```python
python3 -c "
from src.main_orchestrator import save_coin_scan_offset
save_coin_scan_offset(0)
print('Offset reset to 0')
"
```

---

## 🚨 SORUN GİDERME

### **Sorun 1: Hala aynı coinler taranıyor**
```bash
# Kontrol 1: ENABLE_ROTATING_SCAN aktif mi?
grep ENABLE_ROTATING_SCAN .env
# Beklenen: ENABLE_ROTATING_SCAN=True

# Kontrol 2: Log'da rotating mesajı var mı?
grep "Rotating Scan" logs/chimerabot.log | tail -5

# Yoksa:
# → .env'de ENABLE_ROTATING_SCAN=True olduğundan emin ol
# → Bot'u restart et
```

### **Sorun 2: Offset artmıyor**
```bash
# Log kontrol
grep "Yeni offset" logs/chimerabot.log | tail -5

# DB kontrol
sqlite3 data/chimerabot.db "SELECT * FROM alpha_cache WHERE key='coin_scan_offset';"

# Eğer boşsa:
# → save_coin_scan_offset() çağrılmıyor
# → main_orchestrator.py kodunu kontrol et
```

### **Sorun 3: Restart'ta offset sıfırlanıyor**
```bash
# Önceki offset neydi?
sqlite3 data/chimerabot.db "SELECT value FROM alpha_cache WHERE key='coin_scan_offset';"

# Restart sonrası log kontrol
grep "Coin scan offset DB'den yüklendi" logs/chimerabot.log | tail -1

# Eğer "DB'den yüklendi" yoksa:
# → get_coin_scan_offset() hata veriyor
# → DB permission kontrolü yap
```

---

## 📊 PERFORMANS ÖLÇÜMLERİ

### **Önce (Rotating YOK):**
- ✅ İlk 300 coin: 2 dakikada bir taranıyor
- ❌ Kalan 234 coin: HİÇ taranmıyor
- **Coverage:** %56 (300/534)

### **Sonra (Rotating VAR):**
- ✅ İlk 300 coin: 4 dakikada bir taranıyor
- ✅ Kalan 234 coin: 4 dakikada bir taranıyor
- **Coverage:** %100 (534/534)

### **Trade Opportunity Artışı:**
```
Önce: 300 coin × 3 sinyal/gün = ~900 potansiyel sinyal
Sonra: 534 coin × 3 sinyal/gün = ~1,600 potansiyel sinyal

Artış: +78% daha fazla fırsat ✅
```

---

## 🎯 BAŞARI KRİTERLERİ

**Deployment sonrası kontrol et:**

1. ✅ **Log'da rotating mesajı görünüyor mu?**
   ```bash
   tail -f logs/chimerabot.log | grep "Rotating Scan"
   ```

2. ✅ **Offset artıyor mu?**
   ```bash
   watch -n 120 "sqlite3 data/chimerabot.db \"SELECT value FROM alpha_cache WHERE key='coin_scan_offset';\""
   ```

3. ✅ **Farklı coinler taranıyor mu?**
   ```bash
   grep "Analiz Başladı" logs/chimerabot.log | tail -20
   # İlk cycle: AAVEUSDT, ACAUSDT, ...
   # Sonraki cycle: XLMUSDT, XRPUSDT, ZENUSDT, ... (farklı coinler)
   ```

4. ✅ **Restart sonrası offset korunuyor mu?**
   ```bash
   # Restart öncesi offset: 300
   # Restart sonrası offset: 300 (aynı)
   ```

---

## 📝 DEPLOYMENT NOTES

**Coolify'da bu değişiklikler aktif olduğunda:**
- İlk deploy'da offset 0'dan başlar
- Her 2 dakikada 300 coin ilerler
- 4 dakikada tüm 534 coin taranır
- Bot restart edilse bile offset DB'de korunur
- **Beklenen davranış:** Logs'ta "🔄 Rotating Scan: Coins [X→Y]" mesajları

**Eğer hala "⚠️ Liste çok uzun, ilk 300 seçiliyor" görüyorsan:**
→ Coolify'da henüz eski kod çalışıyor demektir
→ Re-deploy yapman gerekir

---

**Değiştirilen Dosyalar:**
- `src/main_orchestrator.py` (+50 lines) - Persistence functions + DB save
- `.env` (+10 lines) - ENABLE_ROTATING_SCAN configuration

**Test Durumu:** ✅ Local test PASSED  
**Production Ready:** ✅ YES  
**Öncelik:** 🔴 HIGH (Tüm coinlerin taranması için kritik)  

---

**Versiyon:** ChimeraBot v9.1 - Rotating Scan Enhancement  
**Tarih:** 9 Kasım 2025  
**Geliştirici:** GitHub Copilot + User Feedback
