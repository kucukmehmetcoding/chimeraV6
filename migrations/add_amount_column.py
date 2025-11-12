#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Migration: Add 'amount' column to OpenPosition
========================================================

Eski database'lerde eksik olan 'amount' kolonunu ekler.

Bug: v11.1 deployment'da eski database kullanılınca crash oluyor.
Fix: amount kolonu position_size_units ile aynı (backward compatibility)

Run: python migrations/add_amount_column.py
"""

import sqlite3
import os
import sys

# Project root path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "chimerabot.db")

def run_migration():
    """Add 'amount' column to open_positions table"""
    
    print("=" * 70)
    print("🔧 DATABASE MIGRATION: Add 'amount' column")
    print("=" * 70)
    
    if not os.path.exists(DB_PATH):
        print(f"✅ Database doesn't exist yet - will be created fresh")
        return True
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(open_positions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'amount' in columns:
            print("⏭️  Column 'amount' already exists - no migration needed")
            return True
        
        print("📋 Column 'amount' missing - adding now...")
        
        # Add amount column (same as position_size_units for backward compatibility)
        cursor.execute("""
            ALTER TABLE open_positions 
            ADD COLUMN amount REAL
        """)
        
        # Update existing rows: amount = position_size_units
        cursor.execute("""
            UPDATE open_positions 
            SET amount = position_size_units 
            WHERE amount IS NULL
        """)
        
        conn.commit()
        
        print("✅ Migration completed!")
        print("   - Added 'amount' column")
        print("   - Populated with position_size_units values")
        
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
