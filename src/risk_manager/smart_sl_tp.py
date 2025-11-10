# src/risk_manager/smart_sl_tp.py
"""
v9.2 SMART SL/TP CALCULATOR
Hibrit sistem: ATR + Swing Levels + Fibonacci + R:R Validation
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def find_swing_levels(df: pd.DataFrame, lookback: int = 50) -> Dict[str, float]:
    """
    Son N mumda swing high/low seviyelerini bulur.
    
    Returns:
        {'swing_high': float, 'swing_low': float, 'pivot_high': float, 'pivot_low': float}
    """
    if df is None or len(df) < lookback:
        logger.warning(f"Swing levels için yetersiz veri: {len(df)} < {lookback}")
        return None
    
    recent = df.iloc[-lookback:]
    
    swing_high = recent['high'].max()
    swing_low = recent['low'].min()
    
    # Pivot points (orta noktadaki en yüksek/düşük)
    mid_point = len(recent) // 2
    pivot_window = recent.iloc[mid_point-10:mid_point+10]  # ±10 mum
    pivot_high = pivot_window['high'].max()
    pivot_low = pivot_window['low'].min()
    
    return {
        'swing_high': swing_high,
        'swing_low': swing_low,
        'pivot_high': pivot_high,
        'pivot_low': pivot_low
    }


def calculate_fibonacci_levels(swing_low: float, swing_high: float) -> Dict[str, float]:
    """
    Fibonacci retracement ve extension seviyelerini hesaplar.
    
    Returns:
        {'fib_0.236': float, 'fib_0.382': float, 'fib_0.5': float, 
         'fib_0.618': float, 'fib_0.786': float, 'ext_1.272': float, 'ext_1.618': float}
    """
    diff = swing_high - swing_low
    
    return {
        # Retracement seviyeleri (geri çekilme)
        'fib_0.236': swing_high - (diff * 0.236),
        'fib_0.382': swing_high - (diff * 0.382),
        'fib_0.5': swing_high - (diff * 0.5),
        'fib_0.618': swing_high - (diff * 0.618),  # Golden ratio
        'fib_0.786': swing_high - (diff * 0.786),
        
        # Extension seviyeleri (hedef)
        'ext_1.272': swing_high + (diff * 0.272),
        'ext_1.618': swing_high + (diff * 0.618),  # Golden extension
        'ext_2.0': swing_high + (diff * 1.0),
    }


def calculate_smart_sl_tp(
    entry_price: float,
    direction: str,
    df: pd.DataFrame,
    config: object,
    atr: float = None
) -> Optional[Dict[str, float]]:
    """
    Akıllı SL/TP hesaplayıcı - Hibrit sistem.
    
    Mantık:
    1. ATR ile başlangıç mesafesi bul (volatilite)
    2. Swing levels bularak destek/direnç tespit et
    3. SL'i en yakın destek/direnç altına/üstüne koy
    4. Fibonacci ile TP hedeflerini belirle
    5. R:R kontrolü yap (minimum 2.0)
    
    Args:
        entry_price: Giriş fiyatı
        direction: 'LONG' veya 'SHORT'
        df: OHLCV dataframe (indicators içermeli)
        config: Config objesi
        atr: ATR değeri (opsiyonel, df'den alınabilir)
    
    Returns:
        {'sl_price': float, 'tp_price': float, 'method': str, 'confidence': float}
    """
    try:
        # ATR al
        if atr is None:
            if 'atr14' in df.columns and not df['atr14'].iloc[-1] is np.nan:
                atr = df['atr14'].iloc[-1]
            else:
                logger.warning("ATR bulunamadı, yüzde bazlı sisteme dönülüyor")
                return None
        
        # Volatilite oranı
        atr_percent = (atr / entry_price) * 100
        
        # Config parametreleri
        min_rr = getattr(config, 'MIN_RR_RATIO', 2.0)
        leverage = getattr(config, 'FUTURES_LEVERAGE', 8)
        atr_sl_multiplier = getattr(config, 'ATR_SL_MULTIPLIER', 2.0)
        atr_tp_multiplier = getattr(config, 'ATR_TP_MULTIPLIER', 4.0)
        
        # 1. ATR bazlı başlangıç mesafeleri
        sl_distance_atr = atr * atr_sl_multiplier
        tp_distance_atr = atr * atr_tp_multiplier
        
        # 2. Swing levels bul
        swing_levels = find_swing_levels(df, lookback=50)
        
        if swing_levels is None:
            # Fallback: Sadece ATR kullan
            logger.info(f"   Swing levels bulunamadı, ATR bazlı hesaplama yapılıyor")
            if direction.upper() == 'LONG':
                sl_price = entry_price - sl_distance_atr
                tp_price = entry_price + tp_distance_atr
            else:
                sl_price = entry_price + sl_distance_atr
                tp_price = entry_price - tp_distance_atr
            
            return {
                'sl_price': sl_price,
                'tp_price': tp_price,
                'method': 'ATR_ONLY',
                'confidence': 0.6,
                'atr_percent': atr_percent
            }
        
        # 3. Fibonacci seviyeleri
        fib_levels = calculate_fibonacci_levels(
            swing_levels['swing_low'],
            swing_levels['swing_high']
        )
        
        # 4. LONG/SHORT'a göre akıllı SL/TP seç
        if direction.upper() == 'LONG':
            # SL: En yakın destek seviyesinin ALTINDA
            # Öncelik: Fibonacci 0.618 > Swing Low > ATR
            
            # Fibonacci 0.618 entry'nin altındaysa kullan
            if fib_levels['fib_0.618'] < entry_price:
                sl_base = fib_levels['fib_0.618']
                sl_method = "FIB_0.618"
            # Yoksa swing low kullan
            elif swing_levels['pivot_low'] < entry_price:
                sl_base = swing_levels['pivot_low']
                sl_method = "PIVOT_LOW"
            else:
                sl_base = entry_price - sl_distance_atr
                sl_method = "ATR"
            
            # SL'i biraz daha aşağıya çek (güvenlik payı %0.3)
            sl_price = sl_base * 0.997
            
            # TP: Fibonacci extension veya swing high
            # Öncelik: Extension 1.618 > Swing High > ATR
            
            if fib_levels['ext_1.618'] > entry_price:
                tp_price = fib_levels['ext_1.618']
                tp_method = "FIB_EXT_1.618"
            elif swing_levels['swing_high'] > entry_price:
                tp_price = swing_levels['swing_high'] * 0.998  # %0.2 önce kapat
                tp_method = "SWING_HIGH"
            else:
                tp_price = entry_price + tp_distance_atr
                tp_method = "ATR"
        
        else:  # SHORT
            # SL: En yakın direnç seviyesinin ÜSTÜNDE
            if fib_levels['fib_0.618'] > entry_price:
                sl_base = fib_levels['fib_0.618']
                sl_method = "FIB_0.618"
            elif swing_levels['pivot_high'] > entry_price:
                sl_base = swing_levels['pivot_high']
                sl_method = "PIVOT_HIGH"
            else:
                sl_base = entry_price + sl_distance_atr
                sl_method = "ATR"
            
            sl_price = sl_base * 1.003  # %0.3 daha yukarı
            
            # TP: Fibonacci extension veya swing low
            if fib_levels['ext_1.618'] < entry_price:
                tp_price = fib_levels['ext_1.618']
                tp_method = "FIB_EXT_1.618"
            elif swing_levels['swing_low'] < entry_price:
                tp_price = swing_levels['swing_low'] * 1.002  # %0.2 önce kapat
                tp_method = "SWING_LOW"
            else:
                tp_price = entry_price - tp_distance_atr
                tp_method = "ATR"
        
        # 5. R:R Kontrolü
        risk_distance = abs(entry_price - sl_price)
        reward_distance = abs(tp_price - entry_price)
        rr = reward_distance / risk_distance if risk_distance > 0 else 0
        
        if rr < min_rr:
            logger.warning(f"   ⚠️ R:R çok düşük ({rr:.2f} < {min_rr}), TP uzatılıyor")
            # TP'yi R:R'yi karşılayacak şekilde uzat
            if direction.upper() == 'LONG':
                tp_price = entry_price + (risk_distance * min_rr)
            else:
                tp_price = entry_price - (risk_distance * min_rr)
            
            rr = min_rr
            tp_method += "_ADJUSTED"
        
        # 6. Güvenilirlik skoru
        confidence = 0.7  # Base
        if "FIB" in sl_method:
            confidence += 0.15
        if "FIB" in tp_method:
            confidence += 0.15
        
        logger.info(f"   🎯 Smart SL/TP: Entry=${entry_price:.6f}, SL=${sl_price:.6f} ({sl_method}), TP=${tp_price:.6f} ({tp_method})")
        logger.info(f"   📊 R:R={rr:.2f}, ATR={atr_percent:.2f}%, Confidence={confidence:.0%}")
        
        return {
            'sl_price': sl_price,
            'tp_price': tp_price,
            'method': f'{sl_method}/{tp_method}',
            'confidence': confidence,
            'rr': rr,
            'atr_percent': atr_percent,
            'swing_levels': swing_levels,
            'fib_levels': fib_levels
        }
        
    except Exception as e:
        logger.error(f"Smart SL/TP hesaplanırken hata: {e}", exc_info=True)
        return None
