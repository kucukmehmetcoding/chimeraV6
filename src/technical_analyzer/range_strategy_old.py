# src/technical_analyzer/range_strategy.py
"""
RANGE TRADING STRATEGY
======================
Destek/direnç arasında al-sat stratejisi.

Kurallar:
- Destek yakınında LONG
- Direnç yakınında SHORT
- TP: Karşı taraf (%0.8'i)
- SL: Range dışı (%0.3)
"""

import logging
import pandas as pd
from typing import Optional, Dict
from .range_detector import detect_range, is_near_support, is_near_resistance

logger = logging.getLogger(__name__)


def analyze_range_signal(df: pd.DataFrame, symbol: str) -> Optional[Dict]:
    """
    Range trading sinyali üret.
    
    Returns:
        Signal dict veya None
    """
    try:
        # Range tespit
        range_data = detect_range(df, symbol, min_width=0.015)
        
        if range_data is None:
            return None
        
        current_price = range_data['current_price']
        
        # ✅ FIX: Yeni range_detector dict döndürüyor, price değerini çıkar
        support_data = range_data['support']
        resistance_data = range_data['resistance']
        
        # Dict ise price değerini al, değilse direkt kullan (backward compatibility)
        support = support_data['price'] if isinstance(support_data, dict) else support_data
        resistance = resistance_data['price'] if isinstance(resistance_data, dict) else resistance_data
        
        # ═══════════════════════════════════════════════════════
        # LONG SİNYALİ (Destek yakınında)
        # ═══════════════════════════════════════════════════════
        if is_near_support(range_data, threshold=0.005):  # %0.5 yakın
            logger.info(f"\n{'🎯' * 30}")
            logger.info(f"✅ {symbol} - RANGE LONG SİNYALİ!")
            logger.info(f"{'🎯' * 30}")
            logger.info(f"   Destek: ${support:.6f}")
            logger.info(f"   Fiyat: ${current_price:.6f} (destek + %{range_data['distance_to_support']*100:.2f})")
            logger.info(f"   TP: ${resistance * 0.992:.6f} (direnç - %0.8)")
            logger.info(f"   SL: ${support * 0.997:.6f} (destek - %0.3)")
            
            return {
                'signal': 'LONG',
                'entry_price': current_price,
                'tp_price': resistance * 0.992,  # Dirence %0.8 kala sat
                'sl_price': support * 0.997,     # Destek %0.3 kırılırsa kes
                'support': support,
                'resistance': resistance,
                'range_width': range_data['range_width'],
                'strategy': 'range_trading',
                'confidence': 0.75
            }
        
        # ═══════════════════════════════════════════════════════
        # SHORT SİNYALİ (Direnç yakınında)
        # ═══════════════════════════════════════════════════════
        elif is_near_resistance(range_data, threshold=0.005):  # %0.5 yakın
            logger.info(f"\n{'🎯' * 30}")
            logger.info(f"✅ {symbol} - RANGE SHORT SİNYALİ!")
            logger.info(f"{'🎯' * 30}")
            logger.info(f"   Direnç: ${resistance:.6f}")
            logger.info(f"   Fiyat: ${current_price:.6f} (direnç - %{range_data['distance_to_resistance']*100:.2f})")
            logger.info(f"   TP: ${support * 1.008:.6f} (destek + %0.8)")
            logger.info(f"   SL: ${resistance * 1.003:.6f} (direnç + %0.3)")
            
            return {
                'signal': 'SHORT',
                'entry_price': current_price,
                'tp_price': support * 1.008,     # Desteğe %0.8 kala kapat
                'sl_price': resistance * 1.003,  # Direnç %0.3 kırılırsa kes
                'support': support,
                'resistance': resistance,
                'range_width': range_data['range_width'],
                'strategy': 'range_trading',
                'confidence': 0.75
            }
        
        else:
            # Fiyat ortada, bekleme pozisyonunda
            logger.debug(f"   {symbol}: Range ortasında, sinyal yok (destek: {range_data['distance_to_support']:.1%}, direnç: {range_data['distance_to_resistance']:.1%})")
            return None
    
    except Exception as e:
        logger.error(f"❌ {symbol} range analiz hatası: {e}", exc_info=True)
        return None
