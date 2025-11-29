# src/technical_analyzer/range_strategy.py
"""
RANGE TRADING STRATEGY v2.0
============================
Destek/direnç arasında al-sat stratejisi.

✅ Yeni Özellikler:
- 1H timeframe confirmation
- Genişletilmiş SL (%0.8)
- Entry validation (destek/direnç kırılma kontrolü)
- Range quality export
- False breakout tracking

Kurallar:
- Destek yakınında LONG (ama desteğin üstünde!)
- Direnç yakınında SHORT (ama direncin altında!)
- TP: Karşı taraf (%0.8'i)
- SL: Range dışı (%0.8 - genişletildi)
- 1H timeframe de aynı yönde range olmalı
"""

import logging
import pandas as pd
import talib
import numpy as np
from typing import Optional, Dict
from .range_detector import detect_range, is_near_support, is_near_resistance

logger = logging.getLogger(__name__)

# 🆕 VOLATILITY FILTER CONSTANTS
MIN_VOLATILITY_PCT = 1.5  # Minimum %1.5 ATR volatilite (kaldıraçlı işlemler için)
ATR_PERIOD = 14  # ATR hesaplama periyodu

# 🆕 VOLATILITY FILTER CONSTANTS
MIN_VOLATILITY_PCT = 1.5  # Minimum %1.5 ATR volatilite (kaldıraçlı işlemler için)
ATR_PERIOD = 14  # ATR hesaplama periyodu


def calculate_volatility_score(df: pd.DataFrame) -> Optional[float]:
    """
    ATR bazlı volatilite skoru hesapla.
    
    Kaldıraçlı işlemler için coin yeterince hareketli olmalı.
    Düşük volatiliteli coinler skip edilir.
    
    Args:
        df: OHLCV dataframe
    
    Returns:
        Volatilite yüzdesi veya None (hata durumunda)
    """
    try:
        if len(df) < ATR_PERIOD + 5:
            return None
        
        # ATR (Average True Range) hesapla
        atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=ATR_PERIOD)
        
        if atr is None or len(atr) == 0:
            return None
        
        current_atr = atr.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        if pd.isna(current_atr) or pd.isna(current_price) or current_price == 0:
            return None
        
        # ATR'yi fiyatın yüzdesi olarak hesapla
        # Yüksek volatilite = daha fazla hareket = kaldıraç için ideal
        volatility_pct = (current_atr / current_price) * 100
        
        return volatility_pct
        
    except Exception as e:
        logger.debug(f"Volatilite hesaplama hatası: {e}")
        return None


def analyze_range_signal(
    df_15m: pd.DataFrame, 
    df_1h: Optional[pd.DataFrame],
    symbol: str
) -> Optional[Dict]:
    """
    Range trading sinyali üret (multi-timeframe).
    
    Args:
        df_15m: 15 dakikalık OHLCV data
        df_1h: 1 saatlik OHLCV data (confirmation için)
        symbol: Coin sembolü
    
    Returns:
        Signal dict veya None
    """
    try:
        # 🆕 VOLATILITY FILTER: Kaldıraçlı işlemler için yeterli volatilite kontrolü
        volatility = calculate_volatility_score(df_15m)
        
        if volatility is None:
            logger.debug(f"   ⚠️ {symbol} volatilite hesaplanamadı, skip")
            return None
        
        if volatility < MIN_VOLATILITY_PCT:
            logger.debug(f"   ❌ {symbol} volatilite çok düşük ({volatility:.2f}% < {MIN_VOLATILITY_PCT}%), hareketsiz coin, skip")
            return None
        
        logger.debug(f"   ✅ {symbol} volatilite: {volatility:.2f}% (yeterli - kaldıraç için uygun)")
        
        # 🆕 Add indicators to dataframes if not already present
        if 'rsi14' not in df_15m.columns:
            try:
                df_15m['rsi14'] = talib.RSI(df_15m['close'], timeperiod=14)
            except Exception as e:
                logger.debug(f"   RSI calculation failed for {symbol} 15M: {e}")
        
        if df_1h is not None and len(df_1h) >= 50:
            if 'ema5' not in df_1h.columns or 'ema20' not in df_1h.columns:
                try:
                    df_1h['ema5'] = talib.EMA(df_1h['close'], timeperiod=5)
                    df_1h['ema20'] = talib.EMA(df_1h['close'], timeperiod=20)
                except Exception as e:
                    logger.debug(f"   EMA calculation failed for {symbol} 1H: {e}")
        
        # ════════════════════════════════════════════════════════
        # ADIM 1: 15M Range Tespit
        # ════════════════════════════════════════════════════════
        range_data_15m = detect_range(df_15m, symbol, min_width=0.04)  # ✅ %4 minimum
        
        if range_data_15m is None:
            return None
        
        current_price = range_data_15m['current_price']
        
        # Support/resistance değerlerini çıkar
        support_data = range_data_15m['support']
        resistance_data = range_data_15m['resistance']
        
        support_15m = support_data['price'] if isinstance(support_data, dict) else support_data
        resistance_15m = resistance_data['price'] if isinstance(resistance_data, dict) else resistance_data
        
        # Range quality al - FIXED: key is 'quality_grade' not 'quality'
        range_quality_15m = range_data_15m.get('quality_grade', 'D')
        # FIXED: key is 'false_breakout' (dict) not 'false_breakouts' (list)
        false_breakout_info_15m = range_data_15m.get('false_breakout', {})
        # Convert to list for compatibility with existing code
        false_breakouts_15m = [false_breakout_info_15m] if false_breakout_info_15m.get('false_breakout_detected', False) else []
        
        logger.debug(f"   {symbol} 15M: Range quality {range_quality_15m}, False breakouts: {len(false_breakouts_15m)}")
        
        # ════════════════════════════════════════════════════════
        # ADIM 2: 1H Timeframe Confirmation (opsiyonel)
        # ════════════════════════════════════════════════════════
        htf_confirmation = True  # Default: onaylı
        
        if df_1h is not None and len(df_1h) >= 50:
            range_data_1h = detect_range(df_1h, symbol, min_width=0.03)  # 1H için %3 yeterli
            
            if range_data_1h is not None:
                support_1h_data = range_data_1h['support']
                resistance_1h_data = range_data_1h['resistance']
                
                support_1h = support_1h_data['price'] if isinstance(support_1h_data, dict) else support_1h_data
                resistance_1h = resistance_1h_data['price'] if isinstance(resistance_1h_data, dict) else resistance_1h_data
                
                # 1H range, 15M range'i içermeli (nested range)
                # Veya en azından çakışmalı olmalı
                range_overlap = (
                    support_1h <= support_15m and resistance_1h >= resistance_15m  # 1H daha geniş
                    or (support_1h >= support_15m * 0.98 and resistance_1h <= resistance_15m * 1.02)  # Yakın
                )
                
                if range_overlap:
                    logger.info(f"   ✅ {symbol} 1H confirmation: Range overlap detected")
                else:
                    logger.warning(f"   ❌ {symbol} 1H range conflict (1H: ${support_1h:.6f}-${resistance_1h:.6f} vs 15M: ${support_15m:.6f}-${resistance_15m:.6f})")
                    htf_confirmation = False
            else:
                logger.debug(f"   ⚠️ {symbol} 1H no range detected (trending market)")
                # 1H'ta range yoksa trending olabilir, izin ver ama not et
                htf_confirmation = True  # İzin ver ama confidence düşür
        
        # ════════════════════════════════════════════════════════
        # ADIM 3: LONG SİNYALİ (Destek yakınında)
        # ════════════════════════════════════════════════════════
        if is_near_support(range_data_15m, threshold=0.01):  # ✅ %1 yakın (daha makul)
            
            # ✅ ENTRY VALIDATION: Fiyat desteğin ÜSTÜNDE olmalı
            if current_price < support_15m:
                logger.warning(f"   ❌ {symbol} LONG: Fiyat desteğin altında (${current_price:.6f} < ${support_15m:.6f}), skip")
                return None
            
            # 🆕 RANGE POSITION FILTER: Fiyat range'in alt %35'inde olmalı (alt bölge)
            range_size = resistance_15m - support_15m
            position_in_range = (current_price - support_15m) / range_size * 100
            if position_in_range > 35.0:
                logger.warning(f"   ❌ {symbol} LONG: Fiyat range'in ortasında (%{position_in_range:.1f}), alt bölgede değil, skip")
                return None
            
            # 🆕 HTF TREND FILTER: 1H EMA5 > EMA20 olmalı (uptrend)
            if 'ema5' in df_1h.columns and 'ema20' in df_1h.columns:
                ema5_1h = df_1h['ema5'].iloc[-1]
                ema20_1h = df_1h['ema20'].iloc[-1]
                if not pd.isna(ema5_1h) and not pd.isna(ema20_1h):
                    if ema5_1h < ema20_1h:
                        logger.warning(f"   ❌ {symbol} LONG: 1H trend SHORT (EMA5={ema5_1h:.6f} < EMA20={ema20_1h:.6f}), skip")
                        return None
                    else:
                        logger.info(f"   ✅ {symbol} LONG: 1H trend onayı (EMA5={ema5_1h:.6f} > EMA20={ema20_1h:.6f})")
            
            # 🆕 MOMENTUM FILTER: RSI 30-70 arasında olmalı (aşırı bölgede değil)
            if 'rsi14' in df_15m.columns:
                rsi_15m = df_15m['rsi14'].iloc[-1]
                if not pd.isna(rsi_15m):
                    if rsi_15m < 30:
                        logger.warning(f"   ⚠️ {symbol} LONG: RSI aşırı satım ({rsi_15m:.1f} < 30), düşmeye devam edebilir")
                        # İzin ver ama confidence düşür
                    elif rsi_15m > 70:
                        logger.warning(f"   ❌ {symbol} LONG: RSI aşırı alım ({rsi_15m:.1f} > 70), skip")
                        return None
            
            # ✅ HTF confirmation kontrolü
            if not htf_confirmation:
                logger.warning(f"   ❌ {symbol} LONG: 1H timeframe onayı yok, skip")
                return None
            
            logger.info(f"\n{'🎯' * 30}")
            logger.info(f"✅ {symbol} - RANGE LONG SİNYALİ!")
            logger.info(f"{'🎯' * 30}")
            logger.info(f"   Destek: ${support_15m:.6f}")
            logger.info(f"   Fiyat: ${current_price:.6f} (destek + %{range_data_15m['distance_to_support']*100:.2f})")
            logger.info(f"   TP: ${resistance_15m * 0.992:.6f} (direnç - %0.8)")
            logger.info(f"   SL: ${support_15m * 0.992:.6f} (destek - %0.8)")
            
            return {
                'signal': 'LONG',
                'entry_price': current_price,
                'tp_price': resistance_15m * 0.992,
                'sl_price': support_15m * 0.992,  # ✅ %0.8'e genişletildi
                'support': support_15m,
                'resistance': resistance_15m,
                'range_width': range_data_15m['range_width'],
                'range_quality': range_quality_15m,
                'false_breakouts': false_breakouts_15m,
                'htf_confirmation': htf_confirmation,
                'strategy': 'range_trading',
                'confidence': 0.85 if htf_confirmation else 0.65
            }
        
        # ════════════════════════════════════════════════════════
        # ADIM 4: SHORT SİNYALİ (Direnç yakınında)
        # ════════════════════════════════════════════════════════
        elif is_near_resistance(range_data_15m, threshold=0.01):  # ✅ %1 yakın (daha makul)
            
            # ✅ ENTRY VALIDATION: Fiyat direncin ALTINDA olmalı
            if current_price > resistance_15m:
                logger.warning(f"   ❌ {symbol} SHORT: Fiyat direncin üstünde (${current_price:.6f} > ${resistance_15m:.6f}), skip")
                return None
            
            # 🆕 RANGE POSITION FILTER: Fiyat range'in üst %35'inde olmalı (üst bölge)
            range_size = resistance_15m - support_15m
            position_in_range = (current_price - support_15m) / range_size * 100
            if position_in_range < 65.0:
                logger.warning(f"   ❌ {symbol} SHORT: Fiyat range'in ortasında (%{position_in_range:.1f}), üst bölgede değil, skip")
                return None
            
            # 🆕 HTF TREND FILTER: 1H EMA5 < EMA20 olmalı (downtrend)
            if 'ema5' in df_1h.columns and 'ema20' in df_1h.columns:
                ema5_1h = df_1h['ema5'].iloc[-1]
                ema20_1h = df_1h['ema20'].iloc[-1]
                if not pd.isna(ema5_1h) and not pd.isna(ema20_1h):
                    if ema5_1h > ema20_1h:
                        logger.warning(f"   ❌ {symbol} SHORT: 1H trend LONG (EMA5={ema5_1h:.6f} > EMA20={ema20_1h:.6f}), skip")
                        return None
                    else:
                        logger.info(f"   ✅ {symbol} SHORT: 1H trend onayı (EMA5={ema5_1h:.6f} < EMA20={ema20_1h:.6f})")
            
            # 🆕 MOMENTUM FILTER: RSI 30-70 arasında olmalı (aşırı bölgede değil)
            if 'rsi14' in df_15m.columns:
                rsi_15m = df_15m['rsi14'].iloc[-1]
                if not pd.isna(rsi_15m):
                    if rsi_15m > 70:
                        logger.warning(f"   ⚠️ {symbol} SHORT: RSI aşırı alım ({rsi_15m:.1f} > 70), yükselmeye devam edebilir")
                        # İzin ver ama confidence düşür
                    elif rsi_15m < 30:
                        logger.warning(f"   ❌ {symbol} SHORT: RSI aşırı satım ({rsi_15m:.1f} < 30), skip")
                        return None
            
            # ✅ HTF confirmation kontrolü
            if not htf_confirmation:
                logger.warning(f"   ❌ {symbol} SHORT: 1H timeframe onayı yok, skip")
                return None
            
            logger.info(f"\n{'🎯' * 30}")
            logger.info(f"✅ {symbol} - RANGE SHORT SİNYALİ!")
            logger.info(f"{'🎯' * 30}")
            logger.info(f"   Direnç: ${resistance_15m:.6f}")
            logger.info(f"   Fiyat: ${current_price:.6f} (direnç - %{range_data_15m['distance_to_resistance']*100:.2f})")
            logger.info(f"   TP: ${support_15m * 0.992:.6f} (destek - %0.8) 🎯")
            logger.info(f"   SL: ${resistance_15m * 1.008:.6f} (direnç + %0.8) 🛑")
            
            return {
                'signal': 'SHORT',
                'entry_price': current_price,
                'tp_price': support_15m * 0.992,  # ✅ DÜZELTME: Destek - %0.8 (kar al)
                'sl_price': resistance_15m * 1.008,  # ✅ Direnç + %0.8 (zararı kes)
                'support': support_15m,
                'resistance': resistance_15m,
                'range_width': range_data_15m['range_width'],
                'range_quality': range_quality_15m,
                'false_breakouts': false_breakouts_15m,
                'htf_confirmation': htf_confirmation,
                'strategy': 'range_trading',
                'confidence': 0.85 if htf_confirmation else 0.65
            }
        
        else:
            # Fiyat ortada, bekleme pozisyonunda - BUT track as near-miss for potential breakout
            logger.debug(f"   {symbol}: Range ortasında, HOLD sinyali (destek: {range_data_15m['distance_to_support']:.1%}, direnç: {range_data_15m['distance_to_resistance']:.1%})")
            logger.info(f"   🔍 DEBUG: {symbol} HOLD signal quality = {range_quality_15m} (from 15m range)")
            
            # Return HOLD signal so near-miss system can monitor for breakout
            return {
                'signal': 'HOLD',
                'entry_price': current_price,
                'tp_price': resistance_15m,  # Potential breakout target
                'sl_price': support_15m,     # Potential breakdown level
                'support': support_15m,
                'resistance': resistance_15m,
                'range_width': range_data_15m['range_width'],
                'range_quality': range_quality_15m,
                'false_breakouts': false_breakouts_15m,
                'htf_confirmation': htf_confirmation,
                'strategy': 'range_trading',
                'confidence': 0.50  # Lower confidence for HOLD
            }
    
    except Exception as e:
        logger.error(f"❌ {symbol} range analiz hatası: {e}", exc_info=True)
        return None
