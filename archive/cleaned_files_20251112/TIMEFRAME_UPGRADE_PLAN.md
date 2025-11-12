# 📊 Timeframe Upgrade Plan - 5m → 15m & 30m

## 🎯 Amaç
5 dakikalık mumlardan 15 ve 30 dakikalık mumlara geçerek **daha güçlü trend sinyalleri** yakalamak.

## 🔍 Mevcut Durum Analizi

### Şu Anki Sistem (v10.7.1)
```python
# config.py
HYBRID_TIMEFRAME = '5m'                    # ❌ ÇOK KISA
ADAPTIVE_SCAN_INTERVAL = 120               # 2 dakika scan
WEBSOCKET_KLINE_INTERVAL = "15m"           # WebSocket 15m (kullanılmıyor?)
```

### Sorunlar
1. **5m mumlar çok küçük hareket** → EMA kesişimi zayıf trendlerde
2. **TP=$14 hedefi çok uzak** → 5m'de trend bu kadar uzun sürmüyor
3. **Noise (gürültü) fazla** → Yanlış sinyaller artıyor

## ✅ Yeni Sistem Tasarımı

### 1. Multi-Timeframe Confirmation System

```python
# Primary Timeframe: 15m (Ana sinyal)
PRIMARY_TIMEFRAME = '15m'

# Secondary Timeframe: 30m (Doğrulama)
SECONDARY_TIMEFRAME = '30m'

# Scan interval: 15 dakikada bir (mum kapanışı)
SCAN_INTERVAL = 900  # 15 dakika = 900 saniye
```

### 2. Entry Logic (Giriş Mantığı)

#### Adım 1: 15m EMA Crossover
```python
def check_15m_crossover(df_15m):
    """
    15 dakikalık mumda EMA5 x EMA20 kesişimi
    
    Koşul:
    - Son mum KAPALI olmalı (is_closed=True)
    - Previous candle: EMA5 < EMA20
    - Current candle: EMA5 > EMA20 → BULLISH
    """
    if len(df_15m) < 2:
        return None
    
    prev = df_15m.iloc[-2]
    curr = df_15m.iloc[-1]
    
    # Bullish crossover
    if prev['ema5'] < prev['ema20'] and curr['ema5'] > curr['ema20']:
        return 'LONG'
    
    # Bearish crossover
    if prev['ema5'] > prev['ema20'] and curr['ema5'] < curr['ema20']:
        return 'SHORT'
    
    return None
```

#### Adım 2: 30m Trend Confirmation
```python
def check_30m_trend(df_30m, direction):
    """
    30 dakikalık mumda trend doğrulaması
    
    LONG için:
    - EMA5 > EMA20 (uptrend devam ediyor)
    - Son 2 mum yükseliş eğiliminde
    
    SHORT için:
    - EMA5 < EMA20 (downtrend devam ediyor)
    - Son 2 mum düşüş eğiliminde
    """
    if len(df_30m) < 2:
        return False
    
    curr = df_30m.iloc[-1]
    prev = df_30m.iloc[-2]
    
    if direction == 'LONG':
        # EMA trend + Price trend
        ema_trend = curr['ema5'] > curr['ema20']
        price_trend = curr['close'] > prev['close']
        return ema_trend and price_trend
    
    elif direction == 'SHORT':
        ema_trend = curr['ema5'] < curr['ema20']
        price_trend = curr['close'] < prev['close']
        return ema_trend and price_trend
    
    return False
```

#### Adım 3: Candle Timing Check
```python
def is_candle_fresh(timestamp, timeframe='15m'):
    """
    Mum yeni kapandı mı kontrol et
    
    15m için: Son 2 dakika içinde kapanmış olmalı
    30m için: Son 5 dakika içinde kapanmış olmalı
    
    Bu sayede mum başlangıcında giriş yaparız
    """
    now = datetime.now().timestamp() * 1000  # milliseconds
    candle_close_time = timestamp
    
    if timeframe == '15m':
        threshold = 2 * 60 * 1000  # 2 dakika
    elif timeframe == '30m':
        threshold = 5 * 60 * 1000  # 5 dakika
    else:
        threshold = 60 * 1000  # 1 dakika
    
    return (now - candle_close_time) < threshold
```

### 3. Complete Entry Function

```python
def check_multi_timeframe_entry(symbol):
    """
    Multi-timeframe entry kontrolü
    
    Returns:
        {
            'signal': 'LONG' or 'SHORT' or None,
            'entry_price': float,
            'confidence': float,  # 0-1
            'timeframes': {
                '15m': {'ema5': X, 'ema20': Y, 'crossover': True},
                '30m': {'ema5': X, 'ema20': Y, 'trend': True}
            }
        }
    """
    # 1. 15m data al
    df_15m = get_klines(symbol, '15m', limit=50)
    if df_15m is None or len(df_15m) < 20:
        return None
    
    # Calculate EMAs
    df_15m['ema5'] = df_15m['close'].ewm(span=5, adjust=False).mean()
    df_15m['ema20'] = df_15m['close'].ewm(span=20, adjust=False).mean()
    
    # 2. Check 15m crossover
    signal_15m = check_15m_crossover(df_15m)
    if not signal_15m:
        return None  # Kesişim yok
    
    # 3. Candle timing check
    last_candle = df_15m.iloc[-1]
    if not is_candle_fresh(last_candle['close_time'], '15m'):
        logger.warning(f"⏰ {symbol} 15m mum çok eski, atlanıyor")
        return None
    
    # 4. 30m confirmation
    df_30m = get_klines(symbol, '30m', limit=50)
    if df_30m is None or len(df_30m) < 20:
        return None
    
    df_30m['ema5'] = df_30m['close'].ewm(span=5, adjust=False).mean()
    df_30m['ema20'] = df_30m['close'].ewm(span=20, adjust=False).mean()
    
    trend_confirmed = check_30m_trend(df_30m, signal_15m)
    
    if not trend_confirmed:
        logger.warning(f"⚠️ {symbol} 30m trend doğrulanamadı")
        return None
    
    # 5. Calculate confidence
    confidence = calculate_confidence(df_15m, df_30m, signal_15m)
    
    return {
        'signal': signal_15m,
        'entry_price': last_candle['close'],
        'confidence': confidence,
        'timeframes': {
            '15m': {
                'ema5': df_15m.iloc[-1]['ema5'],
                'ema20': df_15m.iloc[-1]['ema20'],
                'crossover': True
            },
            '30m': {
                'ema5': df_30m.iloc[-1]['ema5'],
                'ema20': df_30m.iloc[-1]['ema20'],
                'trend': True
            }
        }
    }
```

### 4. Confidence Calculation

```python
def calculate_confidence(df_15m, df_30m, direction):
    """
    Sinyal güven skoru hesapla (0-1)
    
    Faktörler:
    1. EMA spread (15m): EMA5 ve EMA20 arası mesafe ne kadar büyükse o kadar güçlü
    2. Volume: Son mum volume ortalamanın üzerinde mi?
    3. 30m alignment: 30m trendi aynı yönde mi?
    4. Price position: Fiyat EMA5'in üzerinde/altında mı? (yönüne göre)
    """
    score = 0.0
    
    # 1. 15m EMA spread (max 0.3)
    ema5_15m = df_15m.iloc[-1]['ema5']
    ema20_15m = df_15m.iloc[-1]['ema20']
    spread_pct = abs(ema5_15m - ema20_15m) / ema20_15m * 100
    
    if spread_pct > 1.0:  # %1'den fazla spread → güçlü
        score += 0.3
    elif spread_pct > 0.5:  # %0.5-1 arası → orta
        score += 0.2
    else:  # %0.5'ten az → zayıf
        score += 0.1
    
    # 2. Volume (max 0.2)
    if 'volume' in df_15m.columns:
        last_volume = df_15m.iloc[-1]['volume']
        avg_volume = df_15m['volume'].rolling(20).mean().iloc[-1]
        if last_volume > avg_volume * 1.5:  # %50 fazla volume
            score += 0.2
        elif last_volume > avg_volume:
            score += 0.1
    
    # 3. 30m alignment (max 0.3)
    ema5_30m = df_30m.iloc[-1]['ema5']
    ema20_30m = df_30m.iloc[-1]['ema20']
    
    if direction == 'LONG' and ema5_30m > ema20_30m:
        score += 0.3
    elif direction == 'SHORT' and ema5_30m < ema20_30m:
        score += 0.3
    
    # 4. Price position (max 0.2)
    price = df_15m.iloc[-1]['close']
    if direction == 'LONG' and price > ema5_15m:
        score += 0.2
    elif direction == 'SHORT' and price < ema5_15m:
        score += 0.2
    
    return score
```

## 📅 Implementation Steps

### Step 1: Config Updates
```python
# src/config.py

# v10.8: Multi-Timeframe System
PRIMARY_TIMEFRAME = '15m'        # Ana sinyal timeframe'i
SECONDARY_TIMEFRAME = '30m'      # Doğrulama timeframe'i
SCAN_INTERVAL = 900              # 15 dakika (mum kapanışı ile sync)

# Candle freshness check
CANDLE_FRESHNESS_THRESHOLD = {
    '15m': 120,  # 2 dakika (saniye)
    '30m': 300   # 5 dakika
}

# Minimum confidence score
MIN_CONFIDENCE_SCORE = 0.5  # 0-1 arası, 0.5+ sinyaller alınır
```

### Step 2: New Module Creation
```bash
# Yeni modül: src/technical_analyzer/multi_timeframe_analyzer.py
# İçerik:
- check_15m_crossover()
- check_30m_trend()
- is_candle_fresh()
- check_multi_timeframe_entry()
- calculate_confidence()
```

### Step 3: main_orchestrator.py Updates
```python
# Scan cycle'da değişiklik:

def adaptive_scan_cycle():
    """
    15 dakikada bir çalışan scan
    """
    from src.technical_analyzer.multi_timeframe_analyzer import check_multi_timeframe_entry
    
    for symbol in ROTATING_COIN_POOL:
        # Multi-timeframe check
        entry_signal = check_multi_timeframe_entry(symbol)
        
        if entry_signal and entry_signal['confidence'] >= MIN_CONFIDENCE_SCORE:
            # Position aç
            execute_position(symbol, entry_signal)
```

### Step 4: Testing Script
```python
# test_multi_timeframe.py

# Test senaryoları:
1. BTCUSDT 15m + 30m EMA analizi
2. Geçmiş 7 günlük veri ile backtest
3. Confidence score dağılımı
4. TP=$14 hedefine ulaşma oranı
```

## 🎯 Beklenen Sonuçlar

### Mevcut Sistem (5m)
- ❌ Çok fazla sinyal (gürültü)
- ❌ Zayıf trendler
- ❌ TP hedefine düşük ulaşma

### Yeni Sistem (15m + 30m)
- ✅ Daha az ama **kaliteli** sinyaller
- ✅ Güçlü trendler (EMA spread büyük)
- ✅ TP hedefine yüksek ulaşma
- ✅ Mum başlangıcında giriş → En erken pozisyon

## 📊 Metrikler

Track edilecek:
1. **Signal count**: Günlük sinyal sayısı
2. **Win rate**: TP'ye ulaşma oranı
3. **Avg confidence**: Ortalama güven skoru
4. **Avg trade duration**: Pozisyon açık kalma süresi
5. **TP hit time**: TP'ye ulaşma süresi (dakika)

## 🚀 Next Steps

1. ✅ Plan tamamlandı
2. ⏳ Config updates
3. ⏳ multi_timeframe_analyzer.py oluştur
4. ⏳ main_orchestrator.py entegrasyonu
5. ⏳ Test script
6. ⏳ Live test
