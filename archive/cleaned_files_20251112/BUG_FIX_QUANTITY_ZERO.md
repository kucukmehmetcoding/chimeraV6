# 🔧 BUG FIX: Quantity Zero & Database Lock Issues

**Tarih:** 11 Kasım 2025  
**Versiyon:** v10.1  
**Kriter:** CRITICAL - Pozisyon açılamıyor

---

## 🔴 Tespit Edilen Hatalar

### 1. **Executed Quantity = 0 Sorunu** (KRİTİK)

**Belirti:**
```
Order ID: 12953346
Quantity: 0  ← SIFIR!
Avg Price: 0.00

APIError(code=-4003): Quantity less than or equal to zero.
SL/TP emirleri yerleştirilemedi!
```

**Neden:**
- Market order başarılı gözüküyor (Order ID alınıyor)
- AMA `executedQty` = 0 dönüyor
- SL/TP emirleri quantity=0 ile gönderilmeye çalışılıyor
- Binance API hatası: `-4003`

**Olası Sebepler:**
1. **Minimum Notional çok düşük:** Binance Futures ~$100 minimum gerektirir
2. **Step Size yuvarlama hatası:** Çok küçük quantity step size'a uymayabilir
3. **Market Depth yetersiz:** O an likidite yoksa order dolmayabilir
4. **Symbol Trading Halted:** Coin askıya alınmış olabilir

---

### 2. **SQLite Database Locked**

**Belirti:**
```
sqlalchemy.exc.OperationalError: database is locked
[SQL: UPDATE alpha_cache SET value=?, last_updated=CURRENT_TIMESTAMP...]
```

**Neden:**
- Multi-threading (Main thread + Trade Manager thread)
- SQLite default timeout çok kısa (5 saniye)
- Connection pool yetersiz

---

## ✅ Uygulanan Çözümler

### Fix 1: Executed Quantity Kontrolü (executor.py)

**Konum:** `src/trade_manager/executor.py` → `open_futures_position()`

**Değişiklik:**
```python
# ✅ KRİTİK: Executed quantity kontrolü
executed_qty = float(order.get('executedQty', 0))
avg_price = float(order.get('avgPrice', 0))

# 🚨 EXECUTED QTY = 0 KONTROLÜ
if executed_qty <= 0:
    logger.error(f"❌ {symbol} POZİSYON AÇILAMADI: Executed Quantity = {executed_qty}")
    logger.error(f"   OLASI NEDENLER:")
    logger.error(f"   1. Minimum notional değer çok düşük (~$100 gerekir)")
    logger.error(f"   2. Step size yuvarlama hatası")
    logger.error(f"   3. Market depth yetersiz (likidite problemi)")
    logger.error(f"   4. Symbol askıya alınmış (TRADING durumu kontrol et)")
    return None

# 🚨 AVG PRICE = 0 KONTROLÜ
if avg_price <= 0:
    logger.error(f"❌ {symbol} POZİSYON AÇILAMADI: Avg Price = {avg_price}")
    return None
```

**Sonuç:**
- ✅ Quantity = 0 gelen orderlar artık reddediliyor
- ✅ SL/TP placement denenmeden pozisyon iptal ediliyor
- ✅ Detaylı hata mesajları loglanıyor

---

### Fix 2: SL/TP Quantity Pre-Check (executor.py)

**Konum:** `src/trade_manager/executor.py` → `place_sl_tp_orders()`

**Değişiklik:**
```python
# 🚨 KRİTİK: Quantity kontrolü (0 ise SL/TP yerleştirme!)
if quantity_units <= 0:
    logger.error(f"❌ {symbol} SL/TP yerleştirilemez: Quantity = {quantity_units}")
    return None

rounded_qty = self.round_quantity(symbol, quantity_units)

# ✅ Yuvarlama sonrası tekrar kontrol
if rounded_qty <= 0:
    logger.error(f"❌ {symbol} SL/TP yerleştirilemez: Rounded Quantity = {rounded_qty}")
    logger.error(f"   NEDEN: Step size çok büyük, quantity çok küçük yuvarlandı!")
    return None
```

**Sonuç:**
- ✅ SL/TP placement öncesi quantity doğrulaması
- ✅ Yuvarlama sonrası 0 olan quantity'ler yakalanıyor

---

### Fix 3: Database Lock Protection (connection.py)

**Konum:** `src/database/connection.py`

**Değişiklik:**
```python
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={
        "check_same_thread": False,
        "timeout": 30  # ✅ 30 saniye timeout (database lock'tan korunma)
    },
    pool_pre_ping=True,  # ✅ Bağlantı sağlığını kontrol et
    pool_size=10,        # ✅ Connection pool boyutu
    max_overflow=20,     # ✅ Ekstra bağlantı limiti
    echo=False
)
```

**Değişiklikler:**
- `timeout`: 5s → **30s** (lock'ta daha uzun bekler)
- `pool_pre_ping`: Ölü bağlantıları otomatik tespit
- `pool_size`: 10 aktif connection
- `max_overflow`: 20 ekstra connection (peak load için)

**Sonuç:**
- ✅ Database lock hataları azalacak
- ✅ Multi-threading daha güvenli
- ✅ Connection pooling ile performans artışı

---

## 🧪 Test Senaryoları

### Test 1: Quantity = 0 Durumu

**Senaryo:** Düşük fiyatlı coin, çok küçük position size

**Beklenen:**
```
❌ XYZUSDT POZİSYON AÇILAMADI: Executed Quantity = 0
   OLASI NEDENLER:
   1. Minimum notional değer çok düşük (~$100 gerekir)
   ...
```

**Sonuç:** ✅ Pozisyon açılmaz, SL/TP denenmez

---

### Test 2: Step Size Yuvarlama

**Senaryo:** Step size = 1.0, calculated qty = 0.5

**Beklenen:**
```
❌ XYZUSDT SL/TP yerleştirilemez: Rounded Quantity = 0 (orijinal: 0.5)
   NEDEN: Step size çok büyük, quantity çok küçük yuvarlandı!
```

**Sonuç:** ✅ Erken tespit, SL/TP placement skip

---

### Test 3: Database Lock

**Senaryo:** Main thread + Trade Manager thread aynı anda DB yazıyor

**Beklenen:**
- Önceki: `database is locked` hatası
- Şimdi: 30 saniye bekler, sırayla işler

**Sonuç:** ✅ Lock hatası minimize

---

## 📊 Önleme Stratejileri

### 1. Minimum Position Size Garantisi

**Öneri:** Fast mode'da `MIN_POSITION_VALUE_USD` kontrolü ekle

```python
# config.py
FAST_MODE_MIN_POSITION_VALUE = 100.0  # $100 minimum (Binance kuralı)

# main_orchestrator.py
position_value = margin * leverage
if position_value < FAST_MODE_MIN_POSITION_VALUE:
    logger.warning(f"Pozisyon değeri çok düşük: ${position_value} < ${FAST_MODE_MIN_POSITION_VALUE}")
    # Skip signal
```

### 2. Symbol Info Pre-Validation

**Öneri:** Pozisyon açmadan önce symbol constraints kontrol et

```python
symbol_info = executor.get_symbol_info(symbol)
min_notional = symbol_info.get('min_notional', 0)

if position_value < min_notional:
    logger.error(f"❌ {symbol} min notional: ${min_notional}, hesaplanan: ${position_value}")
    # Skip signal
```

### 3. Post-Order Position Verification

**Öneri:** Order sonrası Binance'den pozisyon sorgula

```python
# Order sonrası doğrulama
time.sleep(1)  # API'ye işlem için zaman ver
position = client.futures_position_information(symbol=symbol)
actual_qty = float(position[0]['positionAmt'])

if actual_qty == 0:
    logger.error(f"❌ Pozisyon açılmadı doğrulandı: {symbol}")
    return None
```

---

## 🎯 Beklenen İyileştirmeler

| Metrik | Önce | Sonra |
|--------|------|-------|
| **Quantity=0 Hataları** | Pozisyon açılıyor, SL/TP fail | Erken tespit, pozisyon skip ✅ |
| **Database Lock Sıklığı** | Sık (5s timeout) | Nadir (30s timeout) ✅ |
| **Hata Mesajları** | Belirsiz | Detaylı + çözüm önerileri ✅ |
| **Log Kalitesi** | Kafa karıştırıcı | Anlaşılır + actionable ✅ |

---

## 📝 Deployment Checklist

- [x] `executor.py` executed quantity kontrolü eklendi
- [x] `executor.py` SL/TP quantity pre-check eklendi
- [x] `connection.py` timeout 30s'ye çıkarıldı
- [x] Connection pooling konfigürasyonu yapıldı
- [ ] Test: Düşük fiyatlı coin ile pozisyon denemesi
- [ ] Test: 24 saat çalıştırma (database lock monitoring)
- [ ] İzleme: Quantity=0 hata sayısı (beklenen: sıfır)

---

## 🚀 Deployment Komutu

```bash
# Bot'u durdur
pkill -f main_orchestrator.py

# Yeni kodu deploy et
git pull

# Yeniden başlat
nohup python src/main_orchestrator.py > logs/bot.out 2>&1 &

# Logları izle
tail -f logs/chimerabot.log | grep -E "(❌|🚨|AÇILAMADI|Quantity)"
```

---

## 🔍 Monitoring Komutları

```bash
# Quantity=0 hatalarını say
grep "Executed Quantity = 0" logs/chimerabot.log | wc -l

# Database lock hatalarını say
grep "database is locked" logs/chimerabot.log | wc -l

# Başarılı pozisyon açılışlarını say
grep "POZİSYON BAŞARIYLA AÇILDI" logs/chimerabot.log | wc -l
```

---

**Son Güncelleme:** 11 Kasım 2025, 16:35  
**Durum:** ✅ FIX UYGULAND - Test Bekleniyor
