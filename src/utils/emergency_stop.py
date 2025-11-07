"""
Emergency Stop Mekanizması - Kritik durumlarda tüm trading'i durdurur
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Emergency stop flag dosyası
EMERGENCY_STOP_FILE = Path(__file__).parent.parent.parent / "EMERGENCY_STOP.flag"

def create_emergency_stop():
    """Acil durum durdurmayı aktifleştir"""
    try:
        EMERGENCY_STOP_FILE.touch()
        logger.critical("🚨 EMERGENCY STOP ACTIVATED! Tüm trading durduruldu!")
        return True
    except Exception as e:
        logger.error(f"Emergency stop oluşturulamadı: {e}")
        return False

def remove_emergency_stop():
    """Acil durum durdurmayı kaldır"""
    try:
        if EMERGENCY_STOP_FILE.exists():
            EMERGENCY_STOP_FILE.unlink()
            logger.info("✅ Emergency stop kaldırıldı, trading devam edebilir")
            return True
        return False
    except Exception as e:
        logger.error(f"Emergency stop kaldırılamadı: {e}")
        return False

def is_emergency_stop_active() -> bool:
    """Emergency stop aktif mi kontrol et"""
    return EMERGENCY_STOP_FILE.exists()

def check_emergency_stop() -> tuple[bool, str]:
    """
    Trading devam edebilir mi kontrol et
    
    Returns:
        (can_trade, reason)
    """
    if is_emergency_stop_active():
        return False, "EMERGENCY_STOP_ACTIVE"
    
    return True, "OK"
