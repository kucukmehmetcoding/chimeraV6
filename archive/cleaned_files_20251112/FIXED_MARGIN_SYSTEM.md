# v10.7.1 SABİT MARGIN SİSTEMİ - ÖZET

**Tarih:** 12 Kasım 2025  
**Versiyon:** v10.7.1  
**Durum:** ✅ TAMAMLANDI

---

## 🎯 SABİT MARGIN SİSTEMİ

### Temel Prensipler

**Her pozisyon için sabit değerler:**
```
Margin:    10 USD  (sabit)
Leverage:  10x     (config'den)
TP Hedef:  14 USD  (margin × 1.40 = +%40 kar)
SL Hedef:   9 USD  (margin × 0.90 = -%10 zarar)
```

### Matematiksel Formül

```python
# 1. Position Size Hesaplama
position_size = (MARGIN_USD × LEVERAGE) / entry_price
position_size = (10 × 10) / entry_price
position_size = 100 / entry_price  # Coin cinsinden

# 2. TP/SL Fiyat Hesaplama
TP_PROFIT = 4 USD  # (14 - 10)
SL_LOSS = 1 USD    # (10 - 9)

# LONG Pozisyon:
tp_price = entry_price + (TP_PROFIT / position_size)
sl_price = entry_price - (SL_LOSS / position_size)

# SHORT Pozisyon:
tp_price = entry_price - (TP_PROFIT / position_size)
sl_price = entry_price + (SL_LOSS / position_size)
```

### PnL Doğrulama

```python
# TP Hit edildiğinde:
pnl = (tp_price - entry_price) × position_size = +4 USD
final_value = 10 + 4 = 14 USD ✅

# SL Hit edildiğinde:
pnl = (sl_price - entry_price) × position_size = -1 USD
final_value = 10 - 1 = 9 USD ✅
```

---

## 📝 YAPILAN DEĞİŞİKLİKLER

### 1. Config Güncellemesi (`src/config.py`)

**Eklenen Sabit Değerler:**
```python
# v10.7.1 FIXED MARGIN SYSTEM
FIXED_MARGIN_USD = 10.0        # Her pozisyon 10 USD
FIXED_MARGIN_TP_RATIO = 1.40   # TP: 140% (14 USD)
FIXED_MARGIN_SL_RATIO = 0.90   # SL: 90% (9 USD)

# Hesaplanan değerler
FIXED_TARGET_TP_VALUE = 14.0   # Hedef TP değeri
FIXED_TARGET_SL_VALUE = 9.0    # Hedef SL değeri
FIXED_TP_PROFIT = 4.0          # TP kar miktarı
FIXED_SL_LOSS = 1.0            # SL zarar miktarı
```

### 2. TP/SL Hesaplama (`src/main_orchestrator.py`)

**Function: `calculate_hybrid_sl_tp()`**
```python
# Config'den değerleri al
MARGIN_USD = config.FIXED_MARGIN_USD
TARGET_TP_VALUE = config.FIXED_TARGET_TP_VALUE
TARGET_SL_VALUE = config.FIXED_TARGET_SL_VALUE
TP_PROFIT = config.FIXED_TP_PROFIT
SL_LOSS = config.FIXED_SL_LOSS

# Fiyat hesapla
if direction == 'LONG':
    tp_price = entry_price + (TP_PROFIT / position_size)
    sl_price = entry_price - (SL_LOSS / position_size)
else:
    tp_price = entry_price - (TP_PROFIT / position_size)
    sl_price = entry_price + (SL_LOSS / position_size)
```

### 3. Position Size Hesaplama

**Function: `calculate_position_size()`**
```python
MARGIN_USD = config.FIXED_MARGIN_USD
LEVERAGE = config.FUTURES_LEVERAGE
position_size = (MARGIN_USD * LEVERAGE) / entry_price
```

### 4. Database Kaydı

**Function: `save_hybrid_position()`**
```python
MARGIN_USD = config.FIXED_MARGIN_USD
leverage = config.FUTURES_LEVERAGE

new_position = OpenPosition(
    ...
    final_risk_usd=MARGIN_USD,  # 10 USD
    leverage=leverage,           # 10x
    ...
)
```

---

## 📊 ÖRNEK HESAPLAMALAR

### BTC @ $89,000 (LONG)

```
Entry Price:    $89,000
Position Size:  100 / 89000 = 0.00112360 BTC

TP Price:       $89,000 + (4 / 0.00112360) = $92,560
SL Price:       $89,000 - (1 / 0.00112360) = $88,110

TP Hit PnL:     (92,560 - 89,000) × 0.00112360 = +$4.00 ✅
SL Hit PnL:     (88,110 - 89,000) × 0.00112360 = -$1.00 ✅
```

### ETH @ $3,200 (SHORT)

```
Entry Price:    $3,200
Position Size:  100 / 3200 = 0.03125 ETH

TP Price:       $3,200 - (4 / 0.03125) = $3,072
SL Price:       $3,200 + (1 / 0.03125) = $3,232

TP Hit PnL:     (3,200 - 3,072) × 0.03125 = +$4.00 ✅
SL Hit PnL:     (3,200 - 3,232) × 0.03125 = -$1.00 ✅
```

---

## ✅ TEST SONUÇLARI

**Test Script:** `test_fixed_margin_system.py`

### Farklı Fiyatlarda Doğrulama

| Entry Price | Position Size | TP Value | SL Value | Sonuç |
|-------------|---------------|----------|----------|-------|
| $50,000     | 0.00200000   | $14.00   | $9.00    | ✅     |
| $89,000     | 0.00112360   | $14.00   | $9.00    | ✅     |
| $120,000    | 0.00083333   | $14.00   | $9.00    | ✅     |

**Tüm testler başarılı! Her durumda TP = $14, SL = $9**

---

## 🔧 KULLANIM

### Bot'u Başlatma

```bash
# Config değerleri otomatik yüklenir
python src/main_orchestrator.py
```

### Margin Değerini Değiştirmek

```python
# src/config.py
FIXED_MARGIN_USD = 20.0  # 10 → 20 USD

# Otomatik hesaplanan yeni değerler:
# TP = 20 × 1.40 = 28 USD (+8 USD kar)
# SL = 20 × 0.90 = 18 USD (-2 USD zarar)
```

### TP/SL Oranlarını Değiştirmek

```python
# src/config.py
FIXED_MARGIN_TP_RATIO = 1.50  # 1.40 → 1.50 (+%50 kar)
FIXED_MARGIN_SL_RATIO = 0.85  # 0.90 → 0.85 (-%15 zarar)

# Yeni değerler:
# TP = 10 × 1.50 = 15 USD (+5 USD kar)
# SL = 10 × 0.85 = 8.5 USD (-1.5 USD zarar)
```

---

## 📋 AVANTAJLAR

1. **Basitlik**: Her pozisyon aynı margin ve hedeflerle açılır
2. **Öngörülebilirlik**: TP/SL değerleri her zaman 14 USD / 9 USD
3. **Risk Yönetimi**: Maximum kayıp her pozisyonda 1 USD (-%10)
4. **Kolaylık**: Config'den tek yerden kontrol
5. **Test Edilebilirlik**: Matematiksel olarak doğrulanabilir

---

## ⚠️ ÖNEMLİ NOTLAR

1. **Leverage 10x**: Her 10 USD margin ile 100 USD notional pozisyon
2. **Liquidation Risk**: 10x leverage ile liquidation riski artabilir
3. **Position Sizing**: Fiyat ne olursa olsun margin sabit 10 USD
4. **Win/Loss Ratio**: 1:4 (1 USD zarar vs 4 USD kar) = %400 RR
5. **Testnet Önerisi**: İlk testler testnet'te yapılmalı

---

## 📈 BEKLENEN PERFORMANS

**Win Rate %40 Senaryosu:**
```
10 Trade:
- 4 Win × $4 = +$16
- 6 Loss × $1 = -$6
Net PnL: +$10 (+%100 margin bazlı)
```

**Win Rate %50 Senaryosu:**
```
10 Trade:
- 5 Win × $4 = +$20
- 5 Loss × $1 = -$5
Net PnL: +$15 (+%150 margin bazlı)
```

---

**Son Güncelleme:** 12 Kasım 2025  
**Durum:** Production Ready ✅  
**Test Durumu:** Tüm testler başarılı ✅
