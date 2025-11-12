#!/usr/bin/env python3
"""
Otomatik Cache ve DB Temizleme Script
- Eski backtest cache dosyalarını temizler
- Eski trade history kayıtlarını temizler
- Alpha cache'i yeniler
- SQLite DB optimize eder (VACUUM)
"""

import os
import sys
import time
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import text

# Proje root'unu path'e ekle
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.database.models import db_session, TradeHistory, AlphaCache
from src.database.connection import engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CacheDBCleaner:
    """Cache ve veritabanı temizleme yöneticisi"""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.data_dir = os.path.join(project_root, 'data')
        self.cache_dir = os.path.join(self.data_dir, 'backtest_cache')
        self.log_dir = os.path.join(project_root, 'logs')
        
    def clean_backtest_cache(self, days_to_keep: int = 7) -> dict:
        """
        Eski backtest cache dosyalarını temizle
        
        Args:
            days_to_keep: Kaç günlük cache saklanacak
        
        Returns:
            dict: Temizlik özeti
        """
        logger.info(f"🧹 Backtest cache temizleniyor ({days_to_keep} günden eski)...")
        
        if not os.path.exists(self.cache_dir):
            logger.info("   Cache klasörü yok, oluşturuluyor...")
            os.makedirs(self.cache_dir)
            return {'deleted_files': 0, 'freed_mb': 0}
        
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        freed_bytes = 0
        
        for filename in os.listdir(self.cache_dir):
            filepath = os.path.join(self.cache_dir, filename)
            
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                
                if file_mtime < cutoff_time:
                    file_size = os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted_count += 1
                    freed_bytes += file_size
                    logger.debug(f"   Silindi: {filename} ({file_size / 1024:.1f} KB)")
        
        freed_mb = freed_bytes / (1024 * 1024)
        logger.info(f"   ✅ {deleted_count} dosya silindi, {freed_mb:.2f} MB boşaltıldı")
        
        return {'deleted_files': deleted_count, 'freed_mb': freed_mb}
    
    def clean_old_trade_history(self, days_to_keep: int = 90) -> dict:
        """
        Eski trade history kayıtlarını temizle
        
        Args:
            days_to_keep: Kaç günlük geçmiş saklanacak
        
        Returns:
            dict: Temizlik özeti
        """
        logger.info(f"🧹 Trade history temizleniyor ({days_to_keep} günden eski)...")
        
        db = db_session()
        try:
            cutoff_timestamp = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())
            
            # Silinecek kayıtları say
            old_count = db.query(TradeHistory).filter(
                TradeHistory.close_time < cutoff_timestamp
            ).count()
            
            if old_count == 0:
                logger.info("   Silinecek eski kayıt yok")
                return {'deleted_records': 0}
            
            # Sil
            deleted = db.query(TradeHistory).filter(
                TradeHistory.close_time < cutoff_timestamp
            ).delete()
            
            db.commit()
            logger.info(f"   ✅ {deleted} trade history kaydı silindi")
            
            return {'deleted_records': deleted}
            
        except Exception as e:
            logger.error(f"   ❌ Trade history temizliği hatası: {e}", exc_info=True)
            db.rollback()
            return {'deleted_records': 0, 'error': str(e)}
        finally:
            db_session.remove()
    
    def clean_alpha_cache(self, hours_to_keep: int = 48) -> dict:
        """
        Eski alpha cache kayıtlarını temizle
        
        Args:
            hours_to_keep: Kaç saatlik cache saklanacak
        
        Returns:
            dict: Temizlik özeti
        """
        logger.info(f"🧹 Alpha cache temizleniyor ({hours_to_keep} saatten eski)...")
        
        db = db_session()
        try:
            cutoff_timestamp = int((datetime.now() - timedelta(hours=hours_to_keep)).timestamp())
            
            # Korunacak key'ler (bunları silme)
            protected_keys = [
                'fear_greed_index',
                'correlation_matrix',
                'futures_symbols_list'
            ]
            
            # Eski kayıtları say
            old_count = db.query(AlphaCache).filter(
                AlphaCache.last_updated < cutoff_timestamp,
                ~AlphaCache.key.in_(protected_keys)
            ).count()
            
            if old_count == 0:
                logger.info("   Silinecek eski cache yok")
                return {'deleted_records': 0}
            
            # Sil
            deleted = db.query(AlphaCache).filter(
                AlphaCache.last_updated < cutoff_timestamp,
                ~AlphaCache.key.in_(protected_keys)
            ).delete(synchronize_session=False)
            
            db.commit()
            logger.info(f"   ✅ {deleted} alpha cache kaydı silindi")
            
            return {'deleted_records': deleted}
            
        except Exception as e:
            logger.error(f"   ❌ Alpha cache temizliği hatası: {e}", exc_info=True)
            db.rollback()
            return {'deleted_records': 0, 'error': str(e)}
        finally:
            db_session.remove()
    
    def clean_old_logs(self, days_to_keep: int = 14) -> dict:
        """
        Eski log dosyalarını temizle
        
        Args:
            days_to_keep: Kaç günlük log saklanacak
        
        Returns:
            dict: Temizlik özeti
        """
        logger.info(f"🧹 Eski log dosyaları temizleniyor ({days_to_keep} günden eski)...")
        
        if not os.path.exists(self.log_dir):
            logger.info("   Log klasörü yok")
            return {'deleted_files': 0, 'freed_mb': 0}
        
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        freed_bytes = 0
        
        for filename in os.listdir(self.log_dir):
            # Ana log dosyasını koru (chimerabot.log)
            if filename == 'chimerabot.log':
                continue
            
            filepath = os.path.join(self.log_dir, filename)
            
            if os.path.isfile(filepath) and filename.endswith('.log'):
                file_mtime = os.path.getmtime(filepath)
                
                if file_mtime < cutoff_time:
                    file_size = os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted_count += 1
                    freed_bytes += file_size
                    logger.debug(f"   Silindi: {filename} ({file_size / 1024:.1f} KB)")
        
        freed_mb = freed_bytes / (1024 * 1024)
        logger.info(f"   ✅ {deleted_count} log dosyası silindi, {freed_mb:.2f} MB boşaltıldı")
        
        return {'deleted_files': deleted_count, 'freed_mb': freed_mb}
    
    def vacuum_database(self) -> dict:
        """
        SQLite veritabanını optimize et (VACUUM)
        
        Returns:
            dict: Optimizasyon özeti
        """
        logger.info("🧹 SQLite veritabanı optimize ediliyor (VACUUM)...")
        
        try:
            # DB dosya boyutunu al (öncesi)
            db_path = str(engine.url).replace('sqlite:///', '')
            size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            
            # VACUUM komutu
            with engine.connect() as conn:
                conn.execute(text("VACUUM"))
                conn.commit()
            
            # DB dosya boyutunu al (sonrası)
            size_after = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            
            freed_mb = (size_before - size_after) / (1024 * 1024)
            logger.info(f"   ✅ VACUUM tamamlandı, {freed_mb:.2f} MB boşaltıldı")
            
            return {
                'size_before_mb': size_before / (1024 * 1024),
                'size_after_mb': size_after / (1024 * 1024),
                'freed_mb': freed_mb
            }
            
        except Exception as e:
            logger.error(f"   ❌ VACUUM hatası: {e}", exc_info=True)
            return {'error': str(e)}
    
    def run_full_cleanup(
        self,
        cache_days: int = 7,
        trade_history_days: int = 90,
        alpha_cache_hours: int = 48,
        log_days: int = 14,
        vacuum: bool = True
    ) -> dict:
        """
        Tam temizlik işlemi
        
        Args:
            cache_days: Backtest cache için gün limiti
            trade_history_days: Trade history için gün limiti
            alpha_cache_hours: Alpha cache için saat limiti
            log_days: Log dosyaları için gün limiti
            vacuum: VACUUM çalıştır
        
        Returns:
            dict: Tüm temizlik özeti
        """
        logger.info("=" * 80)
        logger.info("🧹 OTOMATIK TEMİZLİK BAŞLATILIYOR")
        logger.info("=" * 80)
        
        start_time = time.time()
        results = {}
        
        # 1. Backtest cache
        results['backtest_cache'] = self.clean_backtest_cache(days_to_keep=cache_days)
        
        # 2. Trade history
        results['trade_history'] = self.clean_old_trade_history(days_to_keep=trade_history_days)
        
        # 3. Alpha cache
        results['alpha_cache'] = self.clean_alpha_cache(hours_to_keep=alpha_cache_hours)
        
        # 4. Log dosyaları
        results['logs'] = self.clean_old_logs(days_to_keep=log_days)
        
        # 5. VACUUM
        if vacuum:
            results['vacuum'] = self.vacuum_database()
        
        elapsed = time.time() - start_time
        
        # Özet
        logger.info("\n" + "=" * 80)
        logger.info("✅ TEMİZLİK TAMAMLANDI")
        logger.info("=" * 80)
        
        total_freed_mb = (
            results.get('backtest_cache', {}).get('freed_mb', 0) +
            results.get('logs', {}).get('freed_mb', 0) +
            results.get('vacuum', {}).get('freed_mb', 0)
        )
        
        logger.info(f"📊 Özet:")
        logger.info(f"   Backtest cache: {results.get('backtest_cache', {}).get('deleted_files', 0)} dosya")
        logger.info(f"   Trade history: {results.get('trade_history', {}).get('deleted_records', 0)} kayıt")
        logger.info(f"   Alpha cache: {results.get('alpha_cache', {}).get('deleted_records', 0)} kayıt")
        logger.info(f"   Log dosyaları: {results.get('logs', {}).get('deleted_files', 0)} dosya")
        logger.info(f"   Toplam boşaltılan: {total_freed_mb:.2f} MB")
        logger.info(f"   Süre: {elapsed:.1f} saniye")
        
        results['summary'] = {
            'total_freed_mb': total_freed_mb,
            'elapsed_seconds': elapsed
        }
        
        return results


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ChimeraBot Cache & DB Temizleme')
    parser.add_argument('--cache-days', type=int, default=7, help='Backtest cache için gün limiti')
    parser.add_argument('--trade-history-days', type=int, default=90, help='Trade history için gün limiti')
    parser.add_argument('--alpha-cache-hours', type=int, default=48, help='Alpha cache için saat limiti')
    parser.add_argument('--log-days', type=int, default=14, help='Log dosyaları için gün limiti')
    parser.add_argument('--no-vacuum', action='store_true', help='VACUUM işlemini atla')
    parser.add_argument('--dry-run', action='store_true', help='Sadece rapor ver, silme yapma')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("⚠️ DRY RUN MODE - Hiçbir şey silinmeyecek")
    
    cleaner = CacheDBCleaner(project_root)
    
    if args.dry_run:
        logger.info("Dry run: Temizlik simülasyonu (gerçekte silme yok)")
        # TODO: Implement dry-run mode
        return
    
    results = cleaner.run_full_cleanup(
        cache_days=args.cache_days,
        trade_history_days=args.trade_history_days,
        alpha_cache_hours=args.alpha_cache_hours,
        log_days=args.log_days,
        vacuum=not args.no_vacuum
    )
    
    logger.info("\n✅ Temizlik tamamlandı!")


if __name__ == "__main__":
    main()
