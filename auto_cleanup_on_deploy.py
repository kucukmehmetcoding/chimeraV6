#!/usr/bin/env python3
"""
Coolify Redeploy Sonrası Otomatik Temizlik Script
Bu script deployment sonrası çalışır ve database/cache temizliği yapar.

Kullanım:
  python auto_cleanup_on_deploy.py
  
Coolify'da:
  Post-deploy command: python auto_cleanup_on_deploy.py
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/deployment_cleanup.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / 'data' / 'chimerabot.db'
BACKUP_DIR = BASE_DIR / 'data' / 'backups'


def create_backup(db_path: Path) -> Path:
    """Database backup oluştur"""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = BACKUP_DIR / f'chimerabot_backup_{timestamp}.db'
        
        import shutil
        shutil.copy2(db_path, backup_path)
        
        logger.info(f"✅ Backup oluşturuldu: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"❌ Backup hatası: {e}")
        return None


def cleanup_old_backups(keep_last: int = 5):
    """Eski backupları temizle"""
    try:
        if not BACKUP_DIR.exists():
            return
        
        backups = sorted(BACKUP_DIR.glob('chimerabot_backup_*.db'), key=os.path.getmtime, reverse=True)
        
        if len(backups) > keep_last:
            for old_backup in backups[keep_last:]:
                old_backup.unlink()
                logger.info(f"🗑️  Eski backup silindi: {old_backup.name}")
    except Exception as e:
        logger.error(f"❌ Backup temizleme hatası: {e}")


def clean_alpha_cache(conn: sqlite3.Connection) -> int:
    """Alpha cache tablosunu temizle"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM alpha_cache")
        count_before = cursor.fetchone()[0]
        
        cursor.execute("DELETE FROM alpha_cache")
        conn.commit()
        
        logger.info(f"✅ Alpha cache temizlendi: {count_before} kayıt silindi")
        return count_before
    except Exception as e:
        logger.error(f"❌ Alpha cache temizleme hatası: {e}")
        return 0


def clean_old_trade_history(conn: sqlite3.Connection, days: int = 90) -> int:
    """90 günden eski trade history kayıtlarını temizle"""
    try:
        cursor = conn.cursor()
        
        # 90 günden eski kayıtları say
        cursor.execute("""
            SELECT COUNT(*) FROM trade_history 
            WHERE close_time < strftime('%s', 'now', '-90 days')
        """)
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Silmeden önce backup al (opsiyonel)
            cursor.execute("""
                DELETE FROM trade_history 
                WHERE close_time < strftime('%s', 'now', '-90 days')
            """)
            conn.commit()
            logger.info(f"✅ Eski trade history temizlendi: {count} kayıt silindi (>90 gün)")
        else:
            logger.info("ℹ️  Silinecek eski trade history yok")
        
        return count
    except Exception as e:
        logger.error(f"❌ Trade history temizleme hatası: {e}")
        return 0


def vacuum_database(conn: sqlite3.Connection):
    """Database VACUUM (optimize et, boş alanları geri al)"""
    try:
        logger.info("🔧 Database optimize ediliyor (VACUUM)...")
        conn.execute("VACUUM")
        logger.info("✅ Database optimize edildi")
    except Exception as e:
        logger.error(f"❌ VACUUM hatası: {e}")


def check_open_positions(conn: sqlite3.Connection) -> int:
    """Açık pozisyon sayısını kontrol et"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM open_positions")
        count = cursor.fetchone()[0]
        
        if count > 0:
            logger.warning(f"⚠️  UYARI: {count} açık pozisyon var! Redeploy öncesi kapatılmalıydı.")
            
            # Detayları göster
            cursor.execute("""
                SELECT symbol, direction, entry_price, open_time 
                FROM open_positions 
                ORDER BY open_time DESC
            """)
            positions = cursor.fetchall()
            
            for pos in positions:
                symbol, direction, entry, open_time = pos
                open_date = datetime.fromtimestamp(open_time).strftime('%Y-%m-%d %H:%M')
                logger.warning(f"   - {symbol} {direction} @ ${entry:.6f} (Açılış: {open_date})")
        else:
            logger.info("✅ Açık pozisyon yok")
        
        return count
    except Exception as e:
        logger.error(f"❌ Pozisyon kontrolü hatası: {e}")
        return 0


def get_database_stats(conn: sqlite3.Connection):
    """Database istatistiklerini göster"""
    try:
        cursor = conn.cursor()
        
        # Trade history
        cursor.execute("SELECT COUNT(*), ROUND(SUM(pnl_usd), 2) FROM trade_history")
        trade_count, total_pnl = cursor.fetchone()
        
        # Alpha cache
        cursor.execute("SELECT COUNT(*) FROM alpha_cache")
        cache_count = cursor.fetchone()[0]
        
        # Open positions
        cursor.execute("SELECT COUNT(*) FROM open_positions")
        open_count = cursor.fetchone()[0]
        
        logger.info("📊 Database İstatistikleri:")
        logger.info(f"   - Trade History: {trade_count} kayıt (Total PnL: ${total_pnl})")
        logger.info(f"   - Alpha Cache: {cache_count} kayıt")
        logger.info(f"   - Açık Pozisyonlar: {open_count}")
        
    except Exception as e:
        logger.error(f"❌ İstatistik hatası: {e}")


def main():
    """Ana temizlik işlemi"""
    logger.info("=" * 60)
    logger.info("🚀 COOLIFY REDEPLOY CLEANUP BAŞLATILDI")
    logger.info("=" * 60)
    
    # Database var mı kontrol et
    if not DB_PATH.exists():
        logger.warning(f"⚠️  Database bulunamadı: {DB_PATH}")
        logger.info("ℹ️  İlk deployment olabilir, temizlik atlanıyor")
        return 0
    
    try:
        # 1. Backup al
        logger.info("\n📦 Adım 1: Backup oluşturuluyor...")
        backup_path = create_backup(DB_PATH)
        
        # 2. Database bağlantısı
        logger.info("\n🔌 Adım 2: Database'e bağlanılıyor...")
        conn = sqlite3.connect(DB_PATH)
        
        # 3. Önceki istatistikleri göster
        logger.info("\n📊 Adım 3: Mevcut durum:")
        get_database_stats(conn)
        
        # 4. Açık pozisyon kontrolü
        logger.info("\n🔍 Adım 4: Açık pozisyon kontrolü...")
        open_count = check_open_positions(conn)
        
        # 5. Alpha cache temizliği
        logger.info("\n🧹 Adım 5: Alpha cache temizleniyor...")
        cache_cleaned = clean_alpha_cache(conn)
        
        # 6. Eski trade history temizliği (opsiyonel, yorum satırından çıkarın)
        # logger.info("\n🗂️  Adım 6: Eski trade history temizleniyor...")
        # old_trades = clean_old_trade_history(conn, days=90)
        
        # 7. Database optimize et
        logger.info("\n⚙️  Adım 7: Database optimize ediliyor...")
        vacuum_database(conn)
        
        # 8. Sonrası istatistikler
        logger.info("\n📊 Adım 8: Temizlik sonrası durum:")
        get_database_stats(conn)
        
        # 9. Eski backupları temizle
        logger.info("\n🗑️  Adım 9: Eski backuplar temizleniyor...")
        cleanup_old_backups(keep_last=5)
        
        # Bağlantıyı kapat
        conn.close()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ TEMIZLIK TAMAMLANDI!")
        logger.info("=" * 60)
        logger.info(f"📦 Backup: {backup_path}")
        logger.info(f"🧹 Alpha Cache: {cache_cleaned} kayıt temizlendi")
        logger.info(f"⚠️  Açık Pozisyon: {open_count} (varsa manuel kontrol edin!)")
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ FATAL ERROR: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
