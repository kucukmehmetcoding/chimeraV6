# src/technical_analyzer/strategies.py
"""
v10.6 Strategy System

IMPORTANT: v10.6 kullanır HYBRID STRATEGY (15m EMA crossover + 1H confirmation)
Bu dosyadaki eski regime-based stratejiler (pullback, mean_reversion, breakout, scalp)
ARTİK KULLANILMIYOR.

Yeni sistem için:
- websocket_manager: Real-time kline streaming
- ema_manager: Real-time EMA5x20 crossover detection  
- confirmation_layer: 1H trend/strength/momentum/RSI scoring
- smart_executor: Score-based execution (market/partial/limit)

Eski strateji referansı için: archive/strategies_v5.0_backup.py
"""

import logging

logger = logging.getLogger(__name__)

# v10.6 sisteminde bu dosya ARTİK KULLANILMIYOR
logger.info("⚠️  strategies.py yüklendi (v10.6'da kullanılmıyor - legacy reference only)")

# Eğer hala eski sistem çağrılarıyla uyumluluk gerekiyorsa:
def determine_regime(*args, **kwargs):
    """DEPRECATED - v10.6 sistemde kullanılmıyor"""
    logger.warning("⚠️  determine_regime() çağrıldı ama v10.6'da bu fonksiyon kullanılmıyor!")
    return "STOP"

def find_pullback_signal(*args, **kwargs):
    """DEPRECATED - v10.6 sistemde kullanılmıyor"""
    logger.warning("⚠️  find_pullback_signal() çağrıldı ama v10.6'da bu fonksiyon kullanılmıyor!")
    return None

def find_mean_reversion_signal(*args, **kwargs):
    """DEPRECATED - v10.6 sistemde kullanılmıyor"""
    logger.warning("⚠️  find_mean_reversion_signal() çağrıldı ama v10.6'da bu fonksiyon kullanılmıyor!")
    return None

def find_breakout_signal(*args, **kwargs):
    """DEPRECATED - v10.6 sistemde kullanılmıyor"""
    logger.warning("⚠️  find_breakout_signal() çağrıldı ama v10.6'da bu fonksiyon kullanılmıyor!")
    return None

def find_advanced_scalp_signal(*args, **kwargs):
    """DEPRECATED - v10.6 sistemde kullanılmıyor"""
    logger.warning("⚠️  find_advanced_scalp_signal() çağrıldı ama v10.6'da bu fonksiyon kullanılmıyor!")
    return None
