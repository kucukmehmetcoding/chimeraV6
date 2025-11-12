#!/usr/bin/env python3
"""
Database Migration: v10.6 Hybrid Strategy Columns
==================================================

OpenPosition tablosuna v10.6 için yeni kolonlar ekler:
- strategy_source: 'v10.6' (yeni sistem için)
- hybrid_score: Confirmation layer score (0-100)
- execution_type: 'market', 'partial', veya 'limit'

Kullanım:
    python migrations/add_v10_6_columns.py
"""

import sys
import os

# Proje root'u path'e ekle
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import text
from src.database.models import engine, db_session


def add_v10_6_columns():
    """OpenPosition tablosuna v10.6 kolonlarını ekle"""
    
    print("=" * 70)
    print("🔧 v10.6 Hybrid Strategy - Database Migration")
    print("=" * 70)
    
    with engine.connect() as conn:
        # Transaction başlat
        trans = conn.begin()
        
        try:
            print("\n📊 Mevcut OpenPosition kolonları kontrol ediliyor...")
            
            # Mevcut kolonları al
            result = conn.execute(text("PRAGMA table_info(open_positions)"))
            existing_columns = {row[1] for row in result}
            
            print(f"   Bulunan kolonlar: {len(existing_columns)}")
            
            # strategy_source kolonu ekle
            if 'strategy_source' not in existing_columns:
                print("\n➕ 'strategy_source' kolonu ekleniyor...")
                conn.execute(text("""
                    ALTER TABLE open_positions 
                    ADD COLUMN strategy_source VARCHAR DEFAULT 'v10.6'
                """))
                print("   ✅ strategy_source eklendi")
            else:
                print("\n   ℹ️  'strategy_source' zaten mevcut")
            
            # hybrid_score kolonu ekle
            if 'hybrid_score' not in existing_columns:
                print("\n➕ 'hybrid_score' kolonu ekleniyor...")
                conn.execute(text("""
                    ALTER TABLE open_positions 
                    ADD COLUMN hybrid_score FLOAT
                """))
                print("   ✅ hybrid_score eklendi")
            else:
                print("\n   ℹ️  'hybrid_score' zaten mevcut")
            
            # execution_type kolonu ekle
            if 'execution_type' not in existing_columns:
                print("\n➕ 'execution_type' kolonu ekleniyor...")
                conn.execute(text("""
                    ALTER TABLE open_positions 
                    ADD COLUMN execution_type VARCHAR
                """))
                print("   ✅ execution_type eklendi")
            else:
                print("\n   ℹ️  'execution_type' zaten mevcut")
            
            # Commit
            trans.commit()
            
            print("\n" + "=" * 70)
            print("✅ Migration başarıyla tamamlandı!")
            print("=" * 70)
            
            # Yeni şemayı göster
            print("\n📋 Güncellenmiş OpenPosition Şeması:")
            result = conn.execute(text("PRAGMA table_info(open_positions)"))
            for row in result:
                col_id, col_name, col_type, not_null, default, pk = row
                nullable = "NOT NULL" if not_null else "NULL"
                default_val = f"DEFAULT {default}" if default else ""
                print(f"   {col_name:20} {col_type:15} {nullable:10} {default_val}")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ Migration hatası: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


def verify_migration():
    """Migration'ın başarılı olduğunu doğrula"""
    
    print("\n🔍 Migration doğrulaması yapılıyor...")
    
    try:
        db = db_session()
        
        # Test query
        result = db.execute(text("""
            SELECT strategy_source, hybrid_score, execution_type 
            FROM open_positions 
            LIMIT 1
        """))
        
        print("   ✅ Yeni kolonlar erişilebilir durumda")
        
        db_session.remove()
        return True
        
    except Exception as e:
        print(f"   ❌ Doğrulama hatası: {e}")
        return False


def main():
    """Ana migration fonksiyonu"""
    
    print("\n🚀 v10.6 Hybrid Strategy Migration Başlatılıyor...\n")
    
    # Database backup önerisi
    print("⚠️  ÖNEMLİ: Migration'dan önce database yedeklemeniz önerilir!")
    print("   Yedek komutu: cp data/chimerabot.db data/chimerabot_backup_$(date +%Y%m%d_%H%M%S).db")
    
    response = input("\nDevam etmek istiyor musunuz? (y/n): ")
    
    if response.lower() != 'y':
        print("\n❌ Migration iptal edildi.")
        return 1
    
    # Migration'ı çalıştır
    if not add_v10_6_columns():
        return 1
    
    # Doğrulama
    if not verify_migration():
        return 1
    
    print("\n" + "=" * 70)
    print("🎉 v10.6 Database Migration Tamamlandı!")
    print("=" * 70)
    print("\nYeni kolonlar:")
    print("  • strategy_source: Hangi sistemden geldiğini takip eder ('v10.6')")
    print("  • hybrid_score: Confirmation layer score (0-100)")
    print("  • execution_type: Order tipi ('market', 'partial', 'limit')")
    print("\nSistem artık v10.6 Hybrid Strategy için hazır! 🚀")
    print("=" * 70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
