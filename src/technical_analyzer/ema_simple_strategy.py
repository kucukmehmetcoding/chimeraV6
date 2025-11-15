# src/technical_analyzer/ema_simple_strategy.py
"""
MEHMET'İN TRADİNGVİEW STRATEJİSİ
================================
Hiçbir ekleme YOK. Sadece 3 koşul:

1. EMA5 x EMA20 yukarı kesişim (ONAYLANMIŞ)
2. RSI > 50
3. MACD histogram > 0 (yeşil momentum)

HEPSİ TRUE → LONG
TP/SL: ATR bazlı
"""

import logging
import pandas as pd
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def analyze_ema_simple_signal(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Mehmet'in 3'lü kombinasyon stratejisi.
    
    Args:
        df: OHLCV + indicators (ema5, ema20, rsi, macd_hist)
        symbol: Coin sembolü
    
    Returns:
        Signal dict veya None
    """
    try:
        # Veri kontrolü
        if df is None or df.empty or len(df) < 2:
            return None
        
        required_cols = ['ema5', 'ema20', 'rsi', 'macd_hist']
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"⚠️ {symbol}: Gerekli indikatörler eksik")
            return None
        
        # Son 2 mum
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # NaN kontrolü
        if pd.isna([current[col] for col in required_cols]).any():
            return None
        if pd.isna([previous['ema5'], previous['ema20']]).any():
            return None
        
        # ═══════════════════════════════════════════════════════
        # 3'LÜ KOMBİNASYON
        # ═══════════════════════════════════════════════════════
        
        # 1️⃣ EMA5 x EMA20 Yukarı Kesişim (ONAYLANMIŞ)
        ema5_was_below = float(previous['ema5']) <= float(previous['ema20'])
        ema5_now_above = float(current['ema5']) > float(current['ema20'])
        ema_crossover_confirmed = ema5_was_below and ema5_now_above
        
        # 2️⃣ RSI > 50
        rsi_bullish = float(current['rsi']) > 50
        
        # 3️⃣ MACD Histogram > 0 (Yeşil momentum)
        macd_green = float(current['macd_hist']) > 0
        
        # ═══════════════════════════════════════════════════════
        # KARAR: HEPSİ TRUE İSE LONG
        # ═══════════════════════════════════════════════════════
        
        if ema_crossover_confirmed and rsi_bullish and macd_green:
            logger.info(f"\n{'🎯' * 30}")
            logger.info(f"✅ {symbol} - MEHMET'İN 3'LÜ KOMBİNASYONU YAKALANDI!")
            logger.info(f"{'🎯' * 30}")
            logger.info(f"   1️⃣ EMA Crossover: ✅ (EMA5={current['ema5']:.6f} > EMA20={current['ema20']:.6f})")
            logger.info(f"   2️⃣ RSI > 50: ✅ ({current['rsi']:.1f})")
            logger.info(f"   3️⃣ MACD Yeşil: ✅ ({current['macd_hist']:.6f})")
            
            return {
                'signal': 'LONG',
                'entry_price': float(current['close']),
                'ema5': float(current['ema5']),
                'ema20': float(current['ema20']),
                'rsi': float(current['rsi']),
                'macd_hist': float(current['macd_hist']),
                'strategy': 'ema_simple_3combo',
                'confidence': 0.7  # %70 başarı oranı (Mehmet'in testi)
            }
        
        else:
            # Debug: Hangi koşul tutmadı
            if not ema_crossover_confirmed:
                logger.debug(f"   {symbol}: ❌ EMA crossover yok (EMA5={current['ema5']:.6f}, EMA20={current['ema20']:.6f})")
            if not rsi_bullish:
                logger.debug(f"   {symbol}: ❌ RSI <= 50 ({current['rsi']:.1f})")
            if not macd_green:
                logger.debug(f"   {symbol}: ❌ MACD histogram <= 0 ({current['macd_hist']:.6f})")
            
            return None
    
    except Exception as e:
        logger.error(f"❌ {symbol} simple EMA analiz hatası: {e}", exc_info=True)
        return None


def calculate_atr_sl_tp(df: pd.DataFrame, entry_price: float, direction: str = 'LONG') -> Dict[str, float]:
    """
    ATR bazlı TP/SL hesaplama.
    
    Mehmet'in kuralı: ATR bazlı
    - SL: Entry - (ATR × 2.0)
    - TP: Entry + (ATR × 4.0)
    - RR: 2:1
    
    Args:
        df: OHLCV data (ATR hesabı için)
        entry_price: Giriş fiyatı
        direction: 'LONG' (sadece long)
    
    Returns:
        {'sl_price', 'tp_price', 'atr'}
    """
    try:
        from src.technical_analyzer.indicators import calculate_atr
        
        # ATR hesapla (14 periyot)
        atr = calculate_atr(df, period=14)
        
        if atr <= 0:
            logger.warning(f"⚠️ ATR=0, fallback kullanılıyor")
            atr = entry_price * 0.01  # %1 fallback
        
        # ATR bazlı seviyeler
        if direction == 'LONG':
            sl_price = entry_price - (atr * 2.0)
            tp_price = entry_price + (atr * 4.0)
        else:
            # SHORT (gelecekte eklenebilir)
            sl_price = entry_price + (atr * 2.0)
            tp_price = entry_price - (atr * 4.0)
        
        logger.info(f"   📊 ATR Bazlı TP/SL:")
        logger.info(f"      ATR(14): ${atr:.6f}")
        logger.info(f"      Entry: ${entry_price:.6f}")
        logger.info(f"      SL: ${sl_price:.6f} (ATR×2.0)")
        logger.info(f"      TP: ${tp_price:.6f} (ATR×4.0)")
        logger.info(f"      Risk/Reward: 2.0:1")
        
        return {
            'sl_price': sl_price,
            'tp_price': tp_price,
            'atr': atr
        }
    
    except Exception as e:
        logger.error(f"❌ ATR TP/SL hesaplama hatası: {e}")
        # Fallback: %1.5 SL, %3 TP
        return {
            'sl_price': entry_price * 0.985,
            'tp_price': entry_price * 1.03,
            'atr': entry_price * 0.01
        }
