#!/usr/bin/env python3
"""
🧹 RANGE TRADING BOT - Cache Temizleyici
=========================================

Range trading bot için tüm cache verilerini temizler:
- Symbol precision cache (bellekte)
- Position mode cache (bellekte)
- Database cache tablolarını temizler (AlphaCache - eğer varsa)
- Backtest cache dosyalarını temizler

Kullanım:
    python clear_range_cache.py

Author: ChimeraBot Team
"""

import os
import sys
import logging
import shutil
from datetime import datetime

# Proje yolunu ekle
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.database.models import db_session, Base, engine
from sqlalchemy import inspect

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_backtest_cache():
    """Backtest cache klasörünü temizle."""
    cache_dir = os.path.join(project_root, 'data', 'backtest_cache')
    
    if not os.path.exists(cache_dir):
        logger.info(f"ℹ️  Backtest cache klasörü bulunamadı: {cache_dir}")
        return
    
    try:
        files = os.listdir(cache_dir)
        if not files:
            logger.info("✅ Backtest cache zaten boş")
            return
        
        for filename in files:
            file_path = os.path.join(cache_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    logger.info(f"   🗑️  Silindi: {filename}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logger.info(f"   🗑️  Klasör silindi: {filename}")
            except Exception as e:
                logger.error(f"   ❌ {filename} silinemedi: {e}")
        
        logger.info(f"✅ Backtest cache temizlendi: {len(files)} dosya")
    
    except Exception as e:
        logger.error(f"❌ Backtest cache temizleme hatası: {e}")


def clear_database_cache():
    """Database'deki AlphaCache tablosunu temizle."""
    db = db_session()
    
    try:
        # Tablonun var olup olmadığını kontrol et
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'alpha_cache' in tables:
            from src.database.models import AlphaCache
            
            # Tüm cache kayıtlarını say
            cache_count = db.query(AlphaCache).count()
            
            if cache_count == 0:
                logger.info("✅ AlphaCache zaten boş")
            else:
                # Tüm kayıtları sil
                db.query(AlphaCache).delete()
                db.commit()
                logger.info(f"✅ AlphaCache temizlendi: {cache_count} kayıt silindi")
        else:
            logger.info("ℹ️  AlphaCache tablosu bulunamadı (range trading için gerekli değil)")
    
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Database cache temizleme hatası: {e}")
    
    finally:
        db_session.remove()


def clear_runtime_cache():
    """Runtime bellekteki cache'leri temizle (sadece bilgi)."""
    logger.info("\nℹ️  Runtime Cache Bilgisi:")
    logger.info("   • SYMBOL_PRECISION_CACHE: Bot yeniden başlatılınca otomatik temizlenir")
    logger.info("   • POSITION_MODE_CHECKED: Bot yeniden başlatılınca otomatik temizlenir")
    logger.info("   💡 Bu cache'ler bellekte tutuluyor, bot yeniden başlatıldığında sıfırlanır")


def main():
    """Ana cache temizleme fonksiyonu."""
    logger.info("\n" + "="*80)
    logger.info("🧹 RANGE TRADING BOT - CACHE TEMİZLEME")
    logger.info("="*80)
    logger.info(f"🕐 Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. Backtest cache temizle
    logger.info("1️⃣  Backtest Cache temizleniyor...")
    clear_backtest_cache()
    
    # 2. Database cache temizle
    logger.info("\n2️⃣  Database Cache temizleniyor...")
    clear_database_cache()
    
    # 3. Runtime cache bilgisi
    logger.info("\n3️⃣  Runtime Cache:")
    clear_runtime_cache()
    
    logger.info("\n" + "="*80)
    logger.info("✅ CACHE TEMİZLEME TAMAMLANDI")
    logger.info("="*80)
    logger.info(f"🕐 Bitiş: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    logger.info("💡 İpucu: Range trading botu için:")
    logger.info("   - Symbol precision cache: İlk API çağrısında otomatik doldurulur")
    logger.info("   - Position mode cache: İlk kontrolde otomatik ayarlanır")
    logger.info("   - Bot yeniden başlatıldığında tüm runtime cache'ler sıfırlanır")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⛔ İşlem iptal edildi")
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}", exc_info=True)
