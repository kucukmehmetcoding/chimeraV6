# src/technical_analyzer/multi_timeframe_analyzer.py
"""
v10.8: Multi-Timeframe EMA Analysis System
===========================================

15 dakikalık ve 30 dakikalık mumlarda EMA5 x EMA20 kesişimlerini analiz eder.
Daha güçlü trendler için dual-timeframe confirmation sistemi.

Mantık:
1. 15m timeframe'de EMA crossover tespit et
2. 30m timeframe'de trend doğrula
3. Mum kapanış zamanlaması kontrol et (fresh candle)
4. Confidence score hesapla (EMA spread, volume, alignment)
5. Score >= 0.5 ise pozisyon aç

Author: Mehmet Küçük
Date: 2025-11-12
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from src.data_fetcher.binance_fetcher import get_binance_klines
from src.config import (
    PRIMARY_TIMEFRAME,
    SECONDARY_TIMEFRAME,
    HYBRID_EMA_SHORT,
    HYBRID_EMA_LONG,
    CANDLE_FRESHNESS_THRESHOLD,
    MIN_CONFIDENCE_SCORE
)

logger = logging.getLogger(__name__)


def check_15m_crossover(df: pd.DataFrame) -> Optional[str]:
    """
    15 dakikalık mumda EMA5 x EMA20 kesişimi kontrol et
    
    Args:
        df: 15m OHLCV data with EMA5 and EMA20 columns
    
    Returns:
        'LONG': Bullish crossover (EMA5 yukarı kesti EMA20'yi)
        'SHORT': Bearish crossover (EMA5 aşağı kesti EMA20'yi)
        None: Kesişim yok
    """
    if df is None or len(df) < 2:
        return None
    
    if 'ema5' not in df.columns or 'ema20' not in df.columns:
        logger.warning("⚠️ EMA columns missing in DataFrame")
        return None
    
    # Previous and current candle
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    
    # Check for NaN
    if pd.isna(prev['ema5']) or pd.isna(prev['ema20']) or pd.isna(curr['ema5']) or pd.isna(curr['ema20']):
        return None
    
    # Bullish crossover: EMA5 was below, now above
    if prev['ema5'] < prev['ema20'] and curr['ema5'] > curr['ema20']:
        logger.info(f"📈 BULLISH CROSSOVER detected!")
        logger.info(f"   Previous: EMA5={prev['ema5']:.2f} < EMA20={prev['ema20']:.2f}")
        logger.info(f"   Current:  EMA5={curr['ema5']:.2f} > EMA20={curr['ema20']:.2f}")
        return 'LONG'
    
    # Bearish crossover: EMA5 was above, now below
    if prev['ema5'] > prev['ema20'] and curr['ema5'] < curr['ema20']:
        logger.info(f"📉 BEARISH CROSSOVER detected!")
        logger.info(f"   Previous: EMA5={prev['ema5']:.2f} > EMA20={prev['ema20']:.2f}")
        logger.info(f"   Current:  EMA5={curr['ema5']:.2f} < EMA20={curr['ema20']:.2f}")
        return 'SHORT'
    
    return None


def check_30m_trend(df: pd.DataFrame, direction: str) -> bool:
    """
    30 dakikalık mumda trend doğrula
    
    Args:
        df: 30m OHLCV data with EMA5 and EMA20 columns
        direction: 'LONG' or 'SHORT'
    
    Returns:
        True: Trend doğrulandı
        False: Trend zayıf veya ters yönde
    """
    if df is None or len(df) < 2:
        return False
    
    if 'ema5' not in df.columns or 'ema20' not in df.columns:
        return False
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Check for NaN
    if pd.isna(curr['ema5']) or pd.isna(curr['ema20']) or pd.isna(curr['close']) or pd.isna(prev['close']):
        return False
    
    if direction == 'LONG':
        # EMA trend upward AND price trending up
        ema_trend = curr['ema5'] > curr['ema20']
        price_trend = curr['close'] > prev['close']
        
        if ema_trend and price_trend:
            logger.info(f"✅ 30m LONG trend confirmed")
            logger.info(f"   EMA5={curr['ema5']:.2f} > EMA20={curr['ema20']:.2f}")
            logger.info(f"   Price: {prev['close']:.2f} → {curr['close']:.2f}")
            return True
        else:
            logger.warning(f"⚠️ 30m LONG trend NOT confirmed (EMA: {ema_trend}, Price: {price_trend})")
            return False
    
    elif direction == 'SHORT':
        # EMA trend downward AND price trending down
        ema_trend = curr['ema5'] < curr['ema20']
        price_trend = curr['close'] < prev['close']
        
        if ema_trend and price_trend:
            logger.info(f"✅ 30m SHORT trend confirmed")
            logger.info(f"   EMA5={curr['ema5']:.2f} < EMA20={curr['ema20']:.2f}")
            logger.info(f"   Price: {prev['close']:.2f} → {curr['close']:.2f}")
            return True
        else:
            logger.warning(f"⚠️ 30m SHORT trend NOT confirmed (EMA: {ema_trend}, Price: {price_trend})")
            return False
    
    return False


def is_candle_fresh(close_time: int, timeframe: str = '15m') -> bool:
    """
    Mum yeni kapandı mı kontrol et
    
    Args:
        close_time: Candle close timestamp (milliseconds)
        timeframe: '15m' or '30m'
    
    Returns:
        True: Mum yeterince taze (threshold içinde)
        False: Mum çok eski
    """
    now_ms = datetime.now().timestamp() * 1000
    age_ms = now_ms - close_time
    age_seconds = age_ms / 1000
    
    threshold = CANDLE_FRESHNESS_THRESHOLD.get(timeframe, 120)
    
    is_fresh = age_seconds < threshold
    
    if is_fresh:
        logger.info(f"✅ Candle fresh: {age_seconds:.1f}s old (threshold: {threshold}s)")
    else:
        logger.warning(f"⏰ Candle too old: {age_seconds:.1f}s (threshold: {threshold}s)")
    
    return is_fresh


def calculate_confidence(df_15m: pd.DataFrame, df_30m: pd.DataFrame, direction: str) -> float:
    """
    Sinyal güven skoru hesapla (0-1)
    
    Faktörler:
    1. EMA spread (15m): %1+ → 0.3, %0.5-1 → 0.2, <%0.5 → 0.1
    2. Volume: Son mum avg'nin %50+ üzeri → 0.2, üzeri → 0.1
    3. 30m alignment: Aynı yön → 0.3
    4. Price position: Fiyat EMA5'in doğru tarafında → 0.2
    
    Args:
        df_15m: 15m DataFrame
        df_30m: 30m DataFrame
        direction: 'LONG' or 'SHORT'
    
    Returns:
        float: 0-1 arası confidence score
    """
    score = 0.0
    
    curr_15m = df_15m.iloc[-1]
    curr_30m = df_30m.iloc[-1]
    
    # 1. EMA spread on 15m (max 0.3)
    ema5_15m = curr_15m['ema5']
    ema20_15m = curr_15m['ema20']
    spread_pct = abs(ema5_15m - ema20_15m) / ema20_15m * 100
    
    if spread_pct > 1.0:
        score += 0.3
        logger.debug(f"📊 EMA spread: {spread_pct:.2f}% → +0.3 (strong)")
    elif spread_pct > 0.5:
        score += 0.2
        logger.debug(f"📊 EMA spread: {spread_pct:.2f}% → +0.2 (medium)")
    else:
        score += 0.1
        logger.debug(f"📊 EMA spread: {spread_pct:.2f}% → +0.1 (weak)")
    
    # 2. Volume (max 0.2)
    if 'volume' in df_15m.columns and not pd.isna(curr_15m['volume']):
        last_volume = curr_15m['volume']
        avg_volume = df_15m['volume'].rolling(20).mean().iloc[-1]
        
        if not pd.isna(avg_volume) and avg_volume > 0:
            volume_ratio = last_volume / avg_volume
            
            if volume_ratio > 1.5:
                score += 0.2
                logger.debug(f"📊 Volume: {volume_ratio:.2f}x avg → +0.2 (high)")
            elif volume_ratio > 1.0:
                score += 0.1
                logger.debug(f"📊 Volume: {volume_ratio:.2f}x avg → +0.1 (normal)")
    
    # 3. 30m alignment (max 0.3)
    ema5_30m = curr_30m['ema5']
    ema20_30m = curr_30m['ema20']
    
    if direction == 'LONG' and ema5_30m > ema20_30m:
        score += 0.3
        logger.debug(f"📊 30m alignment: LONG → +0.3")
    elif direction == 'SHORT' and ema5_30m < ema20_30m:
        score += 0.3
        logger.debug(f"📊 30m alignment: SHORT → +0.3")
    
    # 4. Price position (max 0.2)
    price = curr_15m['close']
    
    if direction == 'LONG' and price > ema5_15m:
        score += 0.2
        logger.debug(f"📊 Price position: {price:.2f} > EMA5 → +0.2 (bullish)")
    elif direction == 'SHORT' and price < ema5_15m:
        score += 0.2
        logger.debug(f"📊 Price position: {price:.2f} < EMA5 → +0.2 (bearish)")
    
    logger.info(f"🎯 CONFIDENCE SCORE: {score:.2f}/1.0")
    
    return score


def check_multi_timeframe_entry(symbol: str) -> Optional[Dict]:
    """
    Multi-timeframe entry kontrolü (15m + 30m)
    
    Bu fonksiyon:
    1. 15m verileri çeker ve EMA'ları hesaplar
    2. EMA crossover kontrol eder
    3. Mum zamanlaması kontrol eder
    4. 30m verileri çeker ve trend doğrular
    5. Confidence score hesaplar
    6. Score >= MIN_CONFIDENCE_SCORE ise sinyal döner
    
    Args:
        symbol: Trading pair (örn: 'BTCUSDT')
    
    Returns:
        {
            'signal': 'LONG' or 'SHORT',
            'entry_price': float,
            'confidence': float (0-1),
            'timeframes': {
                '15m': {'ema5': X, 'ema20': Y, 'crossover': True},
                '30m': {'ema5': X, 'ema20': Y, 'trend': True}
            }
        }
        or None if no valid signal
    """
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 Multi-Timeframe Analysis: {symbol}")
        logger.info(f"{'='*60}")
        
        # 1. Get 15m data
        logger.info(f"📥 Fetching {PRIMARY_TIMEFRAME} data...")
        df_15m = get_binance_klines(symbol, PRIMARY_TIMEFRAME, limit=50)
        
        if df_15m is None or len(df_15m) < 20:
            logger.warning(f"⚠️ Insufficient 15m data for {symbol}")
            return None
        
        # Calculate EMAs
        df_15m['ema5'] = df_15m['close'].ewm(span=HYBRID_EMA_SHORT, adjust=False).mean()
        df_15m['ema20'] = df_15m['close'].ewm(span=HYBRID_EMA_LONG, adjust=False).mean()
        
        # 2. Check for crossover
        logger.info(f"🔍 Checking {PRIMARY_TIMEFRAME} crossover...")
        signal_15m = check_15m_crossover(df_15m)
        
        if not signal_15m:
            logger.info(f"❌ No crossover detected on {PRIMARY_TIMEFRAME}")
            return None
        
        # 3. Check candle freshness
        last_candle = df_15m.iloc[-1]
        # DataFrame'in index'i timestamp (UTC)
        close_time = df_15m.index[-1].timestamp() * 1000  # milliseconds
        
        logger.info(f"⏰ Checking candle freshness...")
        if not is_candle_fresh(close_time, PRIMARY_TIMEFRAME):
            logger.warning(f"⏰ {symbol} {PRIMARY_TIMEFRAME} candle too old, skipping")
            return None
        
        # 4. Get 30m data and confirm trend
        logger.info(f"📥 Fetching {SECONDARY_TIMEFRAME} data...")
        df_30m = get_binance_klines(symbol, SECONDARY_TIMEFRAME, limit=50)
        
        if df_30m is None or len(df_30m) < 20:
            logger.warning(f"⚠️ Insufficient 30m data for {symbol}")
            return None
        
        # Calculate EMAs
        df_30m['ema5'] = df_30m['close'].ewm(span=HYBRID_EMA_SHORT, adjust=False).mean()
        df_30m['ema20'] = df_30m['close'].ewm(span=HYBRID_EMA_LONG, adjust=False).mean()
        
        # Check trend
        logger.info(f"🔍 Checking {SECONDARY_TIMEFRAME} trend...")
        trend_confirmed = check_30m_trend(df_30m, signal_15m)
        
        if not trend_confirmed:
            logger.warning(f"⚠️ {symbol} {SECONDARY_TIMEFRAME} trend NOT confirmed")
            return None
        
        # 5. Calculate confidence
        logger.info(f"🎯 Calculating confidence score...")
        confidence = calculate_confidence(df_15m, df_30m, signal_15m)
        
        if confidence < MIN_CONFIDENCE_SCORE:
            logger.warning(f"⚠️ Confidence too low: {confidence:.2f} < {MIN_CONFIDENCE_SCORE}")
            return None
        
        # 6. Build signal
        entry_price = last_candle['close']
        
        signal = {
            'signal': signal_15m,
            'entry_price': entry_price,
            'confidence': confidence,
            'timeframes': {
                '15m': {
                    'ema5': df_15m.iloc[-1]['ema5'],
                    'ema20': df_15m.iloc[-1]['ema20'],
                    'crossover': True,
                    'close_time': close_time
                },
                '30m': {
                    'ema5': df_30m.iloc[-1]['ema5'],
                    'ema20': df_30m.iloc[-1]['ema20'],
                    'trend': True
                }
            }
        }
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ VALID SIGNAL FOUND!")
        logger.info(f"{'='*60}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Direction: {signal_15m}")
        logger.info(f"Entry Price: ${entry_price:.2f}")
        logger.info(f"Confidence: {confidence:.2f}/1.0")
        logger.info(f"15m EMA5: {signal['timeframes']['15m']['ema5']:.2f}")
        logger.info(f"15m EMA20: {signal['timeframes']['15m']['ema20']:.2f}")
        logger.info(f"30m EMA5: {signal['timeframes']['30m']['ema5']:.2f}")
        logger.info(f"30m EMA20: {signal['timeframes']['30m']['ema20']:.2f}")
        logger.info(f"{'='*60}\n")
        
        return signal
        
    except Exception as e:
        logger.error(f"❌ Error in multi-timeframe analysis for {symbol}: {e}", exc_info=True)
        return None


def detect_proximity_coins(symbols: list, threshold_percent: float = 1.0) -> Dict[str, Dict]:
    """
    EMA5 ve EMA20 arasındaki mesafe threshold'dan küçük coinleri tespit et
    
    Bu coinler crossover'a çok yakın demektir ve WebSocket ile takip edilmelidir.
    
    Args:
        symbols: Taranacak coin listesi (örn: ['BTCUSDT', 'ETHUSDT', ...])
        threshold_percent: EMA5-EMA20 arası mesafe eşiği (% olarak, default: 1.0)
    
    Returns:
        Dict of {symbol: {
            'distance_percent': float,  # EMA arası mesafe %
            'direction_bias': str,      # 'bullish' veya 'bearish'
            'ema5': float,
            'ema20': float,
            'close': float
        }}
    """
    proximity_coins = {}
    
    logger.info(f"🔍 Proximity scan başlatılıyor: {len(symbols)} coin, threshold: {threshold_percent}%")
    
    for symbol in symbols:
        try:
            # 15m data çek (son 50 mum)
            df = get_binance_klines(symbol, PRIMARY_TIMEFRAME, limit=50)
            
            if df is None or df.empty or len(df) < 2:
                continue
            
            # EMA5 ve EMA20 hesapla
            df['ema5'] = df['close'].ewm(span=HYBRID_EMA_SHORT, adjust=False).mean()
            df['ema20'] = df['close'].ewm(span=HYBRID_EMA_LONG, adjust=False).mean()
            
            # Son değerler
            last_row = df.iloc[-1]
            
            if pd.isna(last_row['ema5']) or pd.isna(last_row['ema20']):
                continue
            
            ema5 = float(last_row['ema5'])
            ema20 = float(last_row['ema20'])
            close = float(last_row['close'])
            
            # Mesafe hesapla (% olarak)
            distance_percent = abs((ema5 - ema20) / ema20 * 100)
            
            # Threshold kontrolü
            if distance_percent <= threshold_percent:
                # Direction bias
                if ema5 > ema20:
                    direction_bias = 'bullish'
                else:
                    direction_bias = 'bearish'
                
                proximity_coins[symbol] = {
                    'distance_percent': round(distance_percent, 4),
                    'direction_bias': direction_bias,
                    'ema5': round(ema5, 2),
                    'ema20': round(ema20, 2),
                    'close': round(close, 2)
                }
                
                logger.debug(
                    f"📍 {symbol}: EMA distance {distance_percent:.4f}% "
                    f"({direction_bias}, close=${close:.2f})"
                )
        
        except Exception as e:
            logger.debug(f"⚠️ {symbol} proximity check error: {e}")
            continue
    
    logger.info(
        f"✅ Proximity scan tamamlandı: {len(proximity_coins)} coin threshold içinde "
        f"({len(symbols)} coin tarandı)"
    )
    
    return proximity_coins


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    test_symbol = 'BTCUSDT'
    logger.info(f"Testing multi-timeframe analyzer for {test_symbol}...")
    
    result = check_multi_timeframe_entry(test_symbol)
    
    if result:
        logger.info(f"\n✅ Test successful!")
        logger.info(f"Signal: {result}")
    else:
        logger.info(f"\n❌ No signal found")

