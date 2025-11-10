# 🔥 ChimeraBot v9.2 CRITICAL FIXES

**Tarih:** 2025-01-XX  
**Sorun:** XVGUSDT pozisyonu TP1 sonrası yanlış PnL hesaplaması (Ghost position $0.00 PnL)  
**Kullanıcı Talebi:** Minimum 150 USD pozisyon değeri (sinyaller nadir, her sinyal değerli)

---

## 📊 XVGUSDT Vaka Analizi

### Pozisyon Akışı
```
1. AÇILIŞ (02:45:03)
   - Symbol: XVGUSDT
   - Direction: LONG
   - Entry: $0.007667
   - Position: 5892 units
   - Risk: $0.56 USD
   - Leverage: 8x
   - Margin: ~$5.67 USD

2. TP1 HİT (03:51:34) ✅
   - Close Price: $0.007861
   - Closed: 2946 units (50%)
   - PnL: $0.57 USD ✅ DOĞRU
   - Trade History Kaydı: PARTIAL_TP_1

3. GHOST POSITION (08:12:38) ❌
   - DB'de: 5892 units (YANLIŞ - olması gereken: 2946)
   - Binance: 0 units (pozisyon kapalı)
   - Close Price: $0.007667 (entry price - YANLIŞ)
   - PnL: $0.00 USD ❌ YANLIŞ
```

### Kök Sebep
1. **TP1 sonrası DB güncellemesi eksik:** TP1 tetiklendiğinde:
   - ✅ `position_size_units` güncellendi (5892 → 2946)
   - ❌ `final_risk_usd` güncellenmedi (0.56 USD kaldı, 0.28 USD olmalıydı)
   - ❌ `sl_price` break-even'e taşınmadı (risk-free için)

2. **Ghost position yanlış close price:** Binance'de kapatılan pozisyonlar için:
   - ❌ Entry price kullanıldı (fallback)
   - ❌ Gerçek kapanış fiyatı Binance trades history'den çekilmedi

---

## 🛠️ Uygulanan Düzeltmeler

### Fix 1: TP1 Sonrası Pozisyon Güncelleme
**Dosya:** `src/trade_manager/manager.py` (Line 766-777)

**ÖNCE:**
```python
pos_in_db.position_size_units = remaining_units
pos_in_db.remaining_position_size = remaining_units
```

**SONRA:**
```python
# Kalan pozisyon yüzdesini hesapla
remaining_percent = 100.0 - pos_in_db.partial_tp_1_percent

# ✅ FİNAL RİSK GÜNCELLENMESİ
# Örnek: $0.56 risk × 50% kalan = $0.28 risk
pos_in_db.final_risk_usd = pos_in_db.final_risk_usd * (remaining_percent / 100.0)

# ✅ SL TO BREAK-EVEN (Risk-free position)
logger.info(f"   📌 SL güncelleniyor: {pos_in_db.sl_price:.6f} → {pos_in_db.entry_price:.6f} (Break-Even)")
pos_in_db.sl_price = pos_in_db.entry_price

# Pozisyon boyutu güncellemesi
pos_in_db.position_size_units = remaining_units
pos_in_db.remaining_position_size = remaining_units
```

**Etki:**
- TP1 sonrası kalan pozisyon için doğru risk hesabı
- SL break-even'e taşınır → TP1'den sonra risk-free trading
- Ghost position durumunda doğru risk değeri

---

### Fix 2: Ghost Position Gerçek Kapanış Fiyatı
**Dosya:** `src/trade_manager/manager.py` (Line 107-161, 731-757)

**YENİ HELPER FONKSİYON:**
```python
def _get_real_close_price_from_binance(symbol: str, open_time_ms: int, entry_price: float) -> Optional[float]:
    """
    Binance trades history'den pozisyonun gerçek kapanış fiyatını bul.
    
    Mantık:
    1. Son 50 trade'i Binance API'den çek
    2. realizedPnl != 0 olan trade'leri filtrele (pozisyon kapatan)
    3. Pozisyon açılış zamanından sonraki kapanış trade'lerini bul
    4. En son kapanış trade'inin fiyatını döndür
    
    Fallback: None döner, ana kod current price veya entry price kullanır
    """
```

**GHOST HANDLER GÜNCELLEMESİ (Line 731-757):**
```python
elif close_reason == 'BINANCE_CLOSED':
    # Pozisyon zaten Binance'de kapanmış, gerçek kapanış fiyatını bul
    logger.info(f"👻 {pos_in_db.symbol} Binance'de zaten kapanmış, gerçek kapanış fiyatı aranıyor...")
    
    # 1. Önce Binance trades history'den gerçek kapanış fiyatını çek
    real_close_price = _get_real_close_price_from_binance(
        symbol=pos_in_db.symbol,
        open_time_ms=pos_in_db.open_time * 1000,
        entry_price=pos_in_db.entry_price
    )
    
    if real_close_price:
        close_price = real_close_price
        logger.info(f"✅ {pos_in_db.symbol} gerçek kapanış fiyatı bulundu: ${close_price:.6f}")
    else:
        # 2. Trades history'de bulunamazsa, güncel fiyatı kullan
        logger.warning(f"⚠️ {pos_in_db.symbol} trades history'de bulunamadı, güncel fiyat kullanılıyor")
        current_price = realtime_mgr.get_price(pos_in_db.symbol)
        
        if current_price:
            close_price = current_price
        else:
            # 3. Son çare: entry price (en kötü senaryo)
            logger.error(f"❌ {pos_in_db.symbol} için güncel fiyat da alınamadı! Entry price kullanılıyor (fallback)")
            close_price = pos_in_db.entry_price
```

**Fallback Chain:**
1. **Binance Trades History** (en doğru) → `realizedPnl != 0` trade'lerinden kapanış fiyatı
2. **Current Market Price** (orta) → WebSocket veya API'den güncel fiyat
3. **Entry Price** (son çare) → PnL = 0, en kötü senaryo

---

### Fix 3: Minimum Pozisyon Değeri 150 USD
**Dosya:** `src/config.py` (Line 119-125), `src/risk_manager/calculator.py` (Line 303-344)

**CONFIG.PY:**
```python
# 🆕 v9.2 CRITICAL FIX: Minimum ve maksimum pozisyon değeri
# Kullanıcı talebi: "herbir pozisyon toplam açılış değeri 150 usd olabilir"
# "5, 10, 15 usd çarpı kaldıraç ile işlem açılmasını istemiyorum"
MIN_POSITION_VALUE_USD = float(os.getenv('MIN_POSITION_VALUE_USD', '150.0'))  # Minimum $150
MAX_POSITION_VALUE_USD = float(os.getenv('MAX_POSITION_VALUE_USD', '300.0'))  # Maximum $300
```

**CALCULATOR.PY GÜNCELLEMESİ:**
```python
min_position_value = getattr(config, 'MIN_POSITION_VALUE_USD', 150.0)

# ... pozisyon hesaplaması ...

# 🆕 MINIMUM POZİSYON DEĞERİ KONTROLÜ
if position_value_usd < min_position_value:
    logger.info(f"   📈 Pozisyon değeri minimum limit altında: ${position_value_usd:.2f} < ${min_position_value:.2f}")
    logger.info(f"   🔧 Pozisyon boyutu minimum değere ayarlanıyor: ${min_position_value:.2f}")
    
    position_size_units = min_position_value / entry_price
    position_value_usd = min_position_value
    
    # Risk yeniden hesapla (daha yüksek olacak)
    actual_risk = position_size_units * sl_distance_usd
    
    logger.info(f"   ⚠️ Risk artışı nedeniyle: ${fixed_risk_usd:.2f} → ${actual_risk:.2f}")
```

**Mantık:**
- XVGUSDT gibi düşük fiyatlı coinlerde position_value < 150 USD olursa:
  - Position size artırılır → 150 USD değerine ulaşır
  - Risk otomatik yükselir (sabit risk $30 değil, gerçek risk daha yüksek olabilir)
  - Log'da "Risk artışı nedeniyle" uyarısı gösterilir

**Örnek:**
```
XVGUSDT @ $0.007667
Sabit risk: $30.00
Hesaplanan position: 3913 units × $0.007667 = $30 USD ❌ (150'nin altı)

Düzeltme:
Position: 19560 units × $0.007667 = $150 USD ✅
Gerçek risk: $150 × (SL mesafe %) = ~$18 USD (örnek)
```

---

## 🧪 Test Senaryoları

### Senaryo 1: TP1 Tetiklemesi
```python
# 1. Pozisyon açılsın (örn: 5000 units, $50 risk)
# 2. TP1 tetiklensin (50% kapansın)
# 3. Kontroller:
assert open_positions.final_risk_usd == 25.0  # ✅ Risk yarıya düştü
assert open_positions.sl_price == open_positions.entry_price  # ✅ Break-even
assert open_positions.position_size_units == 2500  # ✅ Boyut yarıya düştü

# 4. Trade history kontrolü:
trade = TradeHistory.query.filter_by(close_reason='PARTIAL_TP_1').first()
assert trade.pnl_usd > 0  # ✅ TP1 kârlı
```

### Senaryo 2: Ghost Position
```python
# 1. Pozisyon manuel Binance'de kapatılsın
# 2. Bot ghost position'ı tespit etsin
# 3. Kontroller:
assert close_price != entry_price  # ✅ Gerçek kapanış fiyatı kullanıldı
assert "Binance trades history" in logs  # ✅ API çağrısı yapıldı
assert trade_history.pnl_usd != 0.0  # ✅ PnL hesaplandı (0.00 değil)
```

### Senaryo 3: Minimum Position Size
```python
# 1. Düşük fiyatlı coin sinyali gelsin (örn: $0.001)
# 2. Pozisyon hesaplansın
# 3. Kontroller:
assert position_value_usd >= 150.0  # ✅ Minimum değer sağlandı
assert "Pozisyon boyutu minimum değere ayarlanıyor" in logs  # ✅ Log var
assert actual_risk >= fixed_risk_usd  # ⚠️ Risk artabilir (bilgilendirme loglarda)
```

---

## 📈 Beklenen İyileştirmeler

### Önceki Davranış (v9.1)
```
TP1 Hit:
- ✅ %50 pozisyon kapatıldı
- ❌ Kalan %50 için risk yanlış
- ❌ SL hala orijinal seviyede (risk var)

Ghost Position:
- ❌ Entry price kullanıldı → PnL = $0.00
- ❌ Gerçek kâr/zarar kaybedildi

Düşük Fiyatlı Coinler:
- ❌ $5-15 USD pozisyonlar açıldı
- ❌ Sinyaller nadir, ama pozisyonlar küçük
```

### Yeni Davranış (v9.2)
```
TP1 Hit:
- ✅ %50 pozisyon kapatıldı
- ✅ Kalan %50 için risk otomatik güncellendi
- ✅ SL break-even'e taşındı (risk-free)

Ghost Position:
- ✅ Binance trades history'den gerçek close price
- ✅ Fallback: current price → entry price
- ✅ Doğru PnL hesabı

Düşük Fiyatlı Coinler:
- ✅ Minimum $150 pozisyon garantisi
- ✅ Sinyaller nadir → her sinyal değerli
- ✅ Risk otomatik ayarlanıyor
```

---

## 🚀 Deployment Checklist

- [x] **manager.py** (Line 766-777): TP1 position update
- [x] **manager.py** (Line 107-161): Helper function `_get_real_close_price_from_binance()`
- [x] **manager.py** (Line 731-757): Ghost position handler update
- [x] **calculator.py** (Line 303-344): Minimum position value check
- [x] **config.py** (Line 119-125): `MIN_POSITION_VALUE_USD = 150.0`
- [ ] **Test:** TP1 trigger on testnet
- [ ] **Test:** Ghost position cleanup
- [ ] **Test:** Low-price coin position sizing
- [ ] **Git commit:** `git commit -am "v9.2 CRITICAL FIX: TP1 update + Ghost close price + Min 150 USD"`
- [ ] **Deploy:** Coolify redeploy

---

## 📝 Notlar

1. **Binance API Rate Limit:** `futures_account_trades()` çağrısı ağırlık: 5. Ghost position nadir olduğu için sorun olmaz.

2. **Risk Artışı:** Minimum 150 USD pozisyon için risk $30'dan fazla çıkabilir. Loglarda "Risk artışı nedeniyle" mesajı gösterilir.

3. **Trades History Limiti:** Son 50 trade çekiliyor. Pozisyon çok eski ise (50+ trade sonra) bulunamayabilir → fallback current price.

4. **SL Break-Even Faydası:** TP1 sonrası pozisyon risk-free. TP2 veya manuel kapanış bekleniyor, SL break-even'de koruma sağlıyor.

5. **Ghost Position Senaryoları:**
   - Kullanıcı manuel kapatırsa
   - TP2 tetiklenip bot görmezse
   - Binance sistemsel kapanış (margin call vb.)

---

## 🔍 İlgili Dosyalar

- `src/trade_manager/manager.py` - Pozisyon yönetimi ana loop
- `src/risk_manager/calculator.py` - Position sizing hesaplamaları
- `src/config.py` - Global konfigürasyon
- `data/chimerabot.db` - SQLite database (open_positions, trade_history)
- `logs/chimerabot.log` - Bot execution logs

---

**Versiyon:** v9.2 CRITICAL FIXES  
**Durum:** ✅ Implemented, ⏳ Testing Required  
**Öncelik:** 🔥 CRITICAL (Production kullanımda PnL hatası)
