#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database Migration: Margin-based TP/SL Columns
v10.4 - 11 Kasım 2025

Adds:
- initial_margin: Başlangıç margin ($10)
- tp_margin: TP threshold ($14)
- sl_margin: SL threshold ($9)
"""

import sqlite3
import os
import sys

# Project root path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "chimerabot.db")

def run_migration():
    """Add margin threshold columns to open_positions table"""
    
    print("=" * 70)
    print("🔧 DATABASE MIGRATION: Margin-based TP/SL")
    print("=" * 70)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(open_positions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        migrations_done = []
        
        # Add initial_margin column
        if 'initial_margin' not in columns:
            cursor.execute("""
                ALTER TABLE open_positions 
                ADD COLUMN initial_margin REAL
            """)
            migrations_done.append("initial_margin")
            print("✅ Added column: initial_margin")
        else:
            print("⏭️  Column already exists: initial_margin")
        
        # Add tp_margin column
        if 'tp_margin' not in columns:
            cursor.execute("""
                ALTER TABLE open_positions 
                ADD COLUMN tp_margin REAL
            """)
            migrations_done.append("tp_margin")
            print("✅ Added column: tp_margin")
        else:
            print("⏭️  Column already exists: tp_margin")
        
        # Add sl_margin column
        if 'sl_margin' not in columns:
            cursor.execute("""
                ALTER TABLE open_positions 
                ADD COLUMN sl_margin REAL
            """)
            migrations_done.append("sl_margin")
            print("✅ Added column: sl_margin")
        else:
            print("⏭️  Column already exists: sl_margin")
        
        conn.commit()
        
        if migrations_done:
            print(f"\n✅ Migration completed! Added {len(migrations_done)} column(s)")
        else:
            print("\n✅ All columns already exist - no migration needed")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
