#!/usr/bin/env python3
"""
Migration: Partial TP-2 Kolonlarını Ekle (v8.1)
Tarih: 9 Kasım 2025
Açıklama: TP2 mekanizması için partial_tp_2_price, partial_tp_2_percent, partial_tp_2_taken kolonları ekleniyor
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text, Column, Float, Boolean
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "chimerabot.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

def run_migration():
    """Partial TP-2 kolonlarını open_positions tablosuna ekle"""
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    with engine.connect() as conn:
        try:
            logger.info("🔧 Migration başlatılıyor: Partial TP-2 kolonları...")
            
            # Kolon var mı kontrol et
            check_query = text("PRAGMA table_info(open_positions)")
            result = conn.execute(check_query)
            existing_columns = {row[1] for row in result}
            
            # partial_tp_2_percent ekle
            if 'partial_tp_2_percent' not in existing_columns:
                logger.info("   ➕ partial_tp_2_percent kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE open_positions ADD COLUMN partial_tp_2_percent FLOAT"))
                conn.commit()
                logger.info("   ✅ partial_tp_2_percent eklendi")
            else:
                logger.info("   ⏭️  partial_tp_2_percent zaten mevcut")
            
            # partial_tp_2_taken ekle
            if 'partial_tp_2_taken' not in existing_columns:
                logger.info("   ➕ partial_tp_2_taken kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE open_positions ADD COLUMN partial_tp_2_taken BOOLEAN DEFAULT 0"))
                conn.commit()
                logger.info("   ✅ partial_tp_2_taken eklendi")
            else:
                logger.info("   ⏭️  partial_tp_2_taken zaten mevcut")
            
            logger.info("🎉 Migration tamamlandı!")
            
        except Exception as e:
            logger.error(f"❌ Migration hatası: {e}", exc_info=True)
            conn.rollback()
            raise

if __name__ == "__main__":
    run_migration()
