# Margin-Based TP/SL Implementation (v10.4)

## 📋 Özet
ChimeraBot'a **margin bazlı TP/SL mekanizması** eklendi. Fast mode (15m) pozisyonlar artık fiyat bazlı değil, **margin değeri bazlı** TP/SL kullanıyor.

### Yeni Davranış
- **Başlangıç Margin**: $10
- **TP Threshold**: $14 (Margin $10 → $14 olunca pozisyon kapat)
- **SL Threshold**: $9 (Margin $10 → $9 olunca pozisyon kapat)
- **Risk/Reward Ratio**: 4.0 ($4 kar potansiyeli / $1 zarar riski)

## 🎯 Kullanıcı İsteği
```
Senaryo: 10$ margin ile pozisyon açılıyor
TP: Margin 14$ olduğunda kapat (4$ kar)
SL: Margin 9$ olduğunda kapat (1$ zarar)
```

## ✅ Yapılan Değişiklikler

### 1. Config Parametreleri (`src/config.py`)
```python
# v10.4: Margin-based TP/SL thresholds (fast mode için)
FAST_MODE_TP_MARGIN = 14.0   # TP için margin hedefi ($)
FAST_MODE_SL_MARGIN = 9.0    # SL için margin hedefi ($)

# DEPRECATED: Artık kullanılmıyor (eski yüzde bazlı sistem)
# FAST_MODE_TP_PERCENT = 25.0  # TP hedefi (%)
# FAST_MODE_SL_PERCENT = 5.0   # SL limiti (%)
```

### 2. Database Schema (`src/database/models.py`)
OpenPosition tablosuna 3 yeni kolon eklendi:
```python
class OpenPosition(Base):
    # ...
    initial_margin = Column(Float, nullable=True)   # Başlangıç margin ($10)
    tp_margin = Column(Float, nullable=True)        # TP threshold ($14)
    sl_margin = Column(Float, nullable=True)        # SL threshold ($9)
```

**Migration**: `migrations/add_margin_thresholds.py` çalıştırıldı ✅

### 3. Orchestrator - Entry Logic (`src/main_orchestrator.py`)

#### Fast Mode Sizing (Lines ~1074-1102)
```python
# v10.4: Margin-based TP/SL thresholds
tp_margin = getattr(config, 'FAST_MODE_TP_MARGIN', 14.0)
sl_margin = getattr(config, 'FAST_MODE_SL_MARGIN', 9.0)

sizing_result = {
    'position_size_units': position_size_units,
    'final_risk_usd': final_risk_usd,
    'leverage': fast_leverage,
    'position_value_usd': position_value_usd,
    'initial_margin': margin_usd,  # $10
    'tp_margin': tp_margin,         # $14
    'sl_margin': sl_margin          # $9
}

logger.info(f"   🎯 Margin Thresholds: TP=${tp_margin:.2f}, SL=${sl_margin:.2f} (R:R={(tp_margin-margin_usd)/(margin_usd-sl_margin):.1f})")
```

#### Signal Update (Lines ~1290-1310)
```python
signal.update({
    # ... diğer alanlar ...
    # v10.4: Margin-based TP/SL fields
    'initial_margin': sizing_result.get('initial_margin'),
    'tp_margin': sizing_result.get('tp_margin'),
    'sl_margin': sizing_result.get('sl_margin')
})
```

#### DB Insert (Lines ~1298-1340)
```python
new_db_position = OpenPosition(
    # ... diğer alanlar ...
    initial_margin=sizing_result.get('initial_margin'),  # $10
    tp_margin=sizing_result.get('tp_margin'),            # $14
    sl_margin=sizing_result.get('sl_margin'),            # $9
    status='PENDING'
)
```

### 4. Trade Manager - Monitoring Loop (`src/trade_manager/manager.py`)

#### Position Data Extraction (Lines ~960-975)
```python
positions_data = [
    {
        'id': pos.id,
        'symbol': pos.symbol,
        # ... diğer alanlar ...
        # v10.4: Margin-based TP/SL alanları
        'initial_margin': getattr(pos, 'initial_margin', None),
        'tp_margin': getattr(pos, 'tp_margin', None),
        'sl_margin': getattr(pos, 'sl_margin', None)
    }
    for pos in open_positions
]
```

#### Margin-Based TP/SL Check (Lines ~980-1010)
```python
# v10.4: Margin-based TP/SL kontrolü (fast mode için)
if pos_data.get('initial_margin') is not None and pos_data.get('tp_margin') is not None:
    # Unrealized PnL hesapla
    unrealized_pnl = 0.0
    if pos_data['direction'] == 'LONG':
        unrealized_pnl = pos_data['position_size'] * (current_price - pos_data['entry_price'])
    else:  # SHORT
        unrealized_pnl = pos_data['position_size'] * (pos_data['entry_price'] - current_price)
    
    # Güncel margin hesapla
    current_margin = pos_data['initial_margin'] + unrealized_pnl
    
    # TP kontrolü
    if current_margin >= pos_data['tp_margin']:
        should_close = True
        close_reason = f"TP (Margin: ${current_margin:.2f} >= ${pos_data['tp_margin']:.2f})"
    
    # SL kontrolü
    elif current_margin <= pos_data['sl_margin']:
        should_close = True
        close_reason = f"SL (Margin: ${current_margin:.2f} <= ${pos_data['sl_margin']:.2f})"
else:
    # Eski sistem: Price-based TP/SL (backward compatibility)
    # ... (orijinal kod korundu)
```

### 5. Telegram Notifications (`src/notifications/telegram.py`)

#### Signal Message Format (Lines ~147-187)
```python
def format_signal_message(signal_data: dict) -> str:
    # ... diğer alanlar ...
    
    # v10.4: Margin-based TP/SL alanları
    initial_margin = signal_data.get('initial_margin')
    tp_margin = signal_data.get('tp_margin')
    sl_margin = signal_data.get('sl_margin')
    
    # ... mesaj formatı ...
    
    # Margin threshold gösterimi (fast mode için)
    if initial_margin is not None and tp_margin is not None and sl_margin is not None:
        margin_profit = tp_margin - initial_margin
        margin_loss = initial_margin - sl_margin
        
        message += f"*📊 Margin Threshold (Fast Mode):*\n"
        message += f"  • *Başlangıç:* \\${initial_margin:.2f}\n"
        message += f"  • *TP Threshold:* \\${tp_margin:.2f} (\\+\\${margin_profit:.2f})\n"
        message += f"  • *SL Threshold:* \\${sl_margin:.2f} (\\-\\${margin_loss:.2f})\n\n"
```

**Örnek Telegram Bildirimi:**
```
🚀 Yeni Pozisyon Açıldı: BTC/USDT
━━━━━━━━━━━━━━━━━━
📊 İşlem Detayları:
  • Yön: LONG
  • Strateji: FAST_MODE_15M
  • Kaldıraç: 10x
  • Kalite: A

💰 Fiyat Seviyeleri:
  • Giriş: 100.00
  • Stop Loss: 99.00
  • Take Profit: 104.00
  • Risk/Ödül: 4.00

💵 Pozisyon Büyüklüğü:
  • Notional Değer: $100.00
  • Kullanılan Margin: $10.00

📊 Margin Threshold (Fast Mode):
  • Başlangıç: $10.00
  • TP Threshold: $14.00 (+$4.00)
  • SL Threshold: $9.00 (-$1.00)

📈 Tahmini Sonuçlar:
  • Hedef Kar: $4.00 (40.00%)
  • Maksimum Zarar: $1.00 (10.00%)
━━━━━━━━━━━━━━━━━━
```

## 🧪 Test Sonuçları
```bash
python test_margin_based_tpsl.py
```

**4/4 Test Başarılı:**
- ✅ Margin Threshold Hesaplaması
- ✅ TP Trigger Senaryosu (LONG: $100 → $104)
- ✅ SL Trigger Senaryosu (LONG: $100 → $99)
- ✅ SHORT Pozisyon Hesaplamaları

## 📊 Hesaplama Formülleri

### LONG Pozisyon
```
unrealized_pnl = position_size * (current_price - entry_price)
current_margin = initial_margin + unrealized_pnl

TP Trigger: current_margin >= tp_margin ($14)
SL Trigger: current_margin <= sl_margin ($9)
```

### SHORT Pozisyon
```
unrealized_pnl = position_size * (entry_price - current_price)
current_margin = initial_margin + unrealized_pnl

TP Trigger: current_margin >= tp_margin ($14)
SL Trigger: current_margin <= sl_margin ($9)
```

### R:R Ratio
```
profit_potential = tp_margin - initial_margin  # $14 - $10 = $4
loss_potential = initial_margin - sl_margin    # $10 - $9 = $1
rr_ratio = profit_potential / loss_potential   # $4 / $1 = 4.0
```

## 🔄 Backward Compatibility
Eski pozisyonlar (margin threshold'u olmayan) için **eski price-based sistem** korundu:
```python
if pos_data.get('initial_margin') is not None:
    # YENİ: Margin-based kontrol
else:
    # ESKİ: Price-based kontrol
    if pos_data['direction'] == 'LONG':
        if current_price <= pos_data['sl_price']:
            should_close = True
```

## 🚀 Deployment Hazırlığı
Dosya değişiklikleri:
- ✅ `src/config.py` - Yeni parametreler
- ✅ `src/database/models.py` - Yeni kolonlar
- ✅ `src/main_orchestrator.py` - Entry logic
- ✅ `src/trade_manager/manager.py` - Monitoring logic
- ✅ `src/notifications/telegram.py` - Notification format
- ✅ `migrations/add_margin_thresholds.py` - DB migration
- ✅ `test_margin_based_tpsl.py` - Test suite

**Syntax Check**: 0 errors ✅

## 📝 Kullanım Notları

### Fast Mode Aktif mi?
```python
# config.py
ENABLE_15M_FAST_MODE = True
```

### Margin Threshold'ları Değiştirme
```python
# config.py
FAST_MODE_TP_MARGIN = 20.0   # Daha yüksek TP hedefi
FAST_MODE_SL_MARGIN = 8.0    # Daha dar SL
```

### Migration Tekrar Çalıştırma (Gerekirse)
```bash
python migrations/add_margin_thresholds.py
```

## 🎉 Özet
- **6/6 task tamamlandı**
- **4/4 test başarılı**
- **0 syntax error**
- **Backward compatible**
- **Ready for production** ✅

---
**Version**: v10.4  
**Date**: 2024  
**Feature**: Margin-Based TP/SL System  
**Status**: ✅ Completed & Tested
