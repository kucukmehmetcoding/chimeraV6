#!/usr/bin/env python3
"""
Database Migration: Add 'amount' column to OpenPosition
"""

import sqlite3
import os

DB_PATH = "data/chimerabot.db"

def migrate():
    """Add amount column to open_positions table"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    print(f"📊 Migrating database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(open_positions)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'amount' in columns:
            print("✅ 'amount' column already exists")
        else:
            print("➕ Adding 'amount' column...")
            cursor.execute("""
                ALTER TABLE open_positions 
                ADD COLUMN amount REAL
            """)
            conn.commit()
            print("✅ 'amount' column added successfully")
        
        # Verify
        cursor.execute("PRAGMA table_info(open_positions)")
        print("\n📋 Updated table structure:")
        for col in cursor.fetchall():
            print(f"   {col[1]} ({col[2]})")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    print("\n✅ Migration completed!")


if __name__ == "__main__":
    migrate()
