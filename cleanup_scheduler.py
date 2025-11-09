#!/usr/bin/env python3
"""
Otomatik Temizlik Scheduler
Günlük veya haftalık olarak otomatik temizlik yapar
"""

import os
import sys
import time
import schedule
import logging
from datetime import datetime

# Proje root'unu path'e ekle
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from cleanup_cache_db import CacheDBCleaner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(project_root, 'logs', 'cleanup_scheduler.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def run_daily_cleanup():
    """Günlük temizlik (hafif)"""
    logger.info("\n" + "=" * 80)
    logger.info(f"📅 GÜNLÜK TEMİZLİK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    cleaner = CacheDBCleaner(project_root)
    
    try:
        results = cleaner.run_full_cleanup(
            cache_days=7,           # 1 haftalık cache
            trade_history_days=90,  # 3 aylık trade history
            alpha_cache_hours=48,   # 2 günlük alpha cache
            log_days=14,            # 2 haftalık log
            vacuum=False            # Günlük VACUUM yapmaya gerek yok
        )
        
        logger.info("✅ Günlük temizlik başarılı")
        return results
        
    except Exception as e:
        logger.error(f"❌ Günlük temizlik hatası: {e}", exc_info=True)
        return None


def run_weekly_cleanup():
    """Haftalık temizlik (ağır - VACUUM dahil)"""
    logger.info("\n" + "=" * 80)
    logger.info(f"📅 HAFTALIK TEMİZLİK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    cleaner = CacheDBCleaner(project_root)
    
    try:
        results = cleaner.run_full_cleanup(
            cache_days=7,           # 1 haftalık cache
            trade_history_days=90,  # 3 aylık trade history
            alpha_cache_hours=48,   # 2 günlük alpha cache
            log_days=14,            # 2 haftalık log
            vacuum=True             # Haftalık VACUUM
        )
        
        logger.info("✅ Haftalık temizlik başarılı")
        return results
        
    except Exception as e:
        logger.error(f"❌ Haftalık temizlik hatası: {e}", exc_info=True)
        return None


def main():
    """Scheduler ana loop"""
    logger.info("🚀 Otomatik Temizlik Scheduler başlatılıyor...")
    logger.info(f"   Günlük temizlik: Her gün 03:00")
    logger.info(f"   Haftalık temizlik: Her Pazar 04:00")
    
    # Günlük temizlik (her gün 03:00)
    schedule.every().day.at("03:00").do(run_daily_cleanup)
    
    # Haftalık temizlik (her Pazar 04:00)
    schedule.every().sunday.at("04:00").do(run_weekly_cleanup)
    
    logger.info("✅ Scheduler aktif, beklemede...")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Her dakika kontrol et
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Scheduler durduruldu (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Scheduler hatası: {e}", exc_info=True)


if __name__ == "__main__":
    main()
