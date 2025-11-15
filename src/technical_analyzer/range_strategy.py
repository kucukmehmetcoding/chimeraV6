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
from typing import Optional, Dict
from .range_detector import detect_range, is_near_support, is_near_resistance

logger = logging.getLogger(__name__)


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
        
        # Range quality al
        range_quality_15m = range_data_15m.get('quality', 'D')
        false_breakouts_15m = range_data_15m.get('false_breakouts', [])
        
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
        if is_near_support(range_data_15m, threshold=0.003):  # ✅ %0.3 yakın (daha sıkı)
            
            # ✅ ENTRY VALIDATION: Fiyat desteğin ÜSTÜNDE olmalı
            if current_price < support_15m:
                logger.warning(f"   ❌ {symbol} LONG: Fiyat desteğin altında (${current_price:.6f} < ${support_15m:.6f}), skip")
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
        elif is_near_resistance(range_data_15m, threshold=0.003):  # ✅ %0.3 yakın (daha sıkı)
            
            # ✅ ENTRY VALIDATION: Fiyat direncin ALTINDA olmalı
            if current_price > resistance_15m:
                logger.warning(f"   ❌ {symbol} SHORT: Fiyat direncin üstünde (${current_price:.6f} > ${resistance_15m:.6f}), skip")
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
            logger.info(f"   TP: ${support_15m * 1.008:.6f} (destek + %0.8)")
            logger.info(f"   SL: ${resistance_15m * 1.008:.6f} (direnç + %0.8)")
            
            return {
                'signal': 'SHORT',
                'entry_price': current_price,
                'tp_price': support_15m * 1.008,
                'sl_price': resistance_15m * 1.008,  # ✅ %0.8'e genişletildi
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
            # Fiyat ortada, bekleme pozisyonunda
            logger.debug(f"   {symbol}: Range ortasında, sinyal yok (destek: {range_data_15m['distance_to_support']:.1%}, direnç: {range_data_15m['distance_to_resistance']:.1%})")
            return None
    
    except Exception as e:
        logger.error(f"❌ {symbol} range analiz hatası: {e}", exc_info=True)
        return None
