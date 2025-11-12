#!/usr/bin/env python3
"""
Database Migration: Add v10.7 columns
"""

import sqlite3
import os

DB_PATH = "data/chimerabot.db"

def migrate():
    """Add v10.7 columns to open_positions table"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    print(f"📊 Migrating database for v10.7: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(open_positions)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        new_columns = [
            ("strategy_source", "VARCHAR(20)"),
            ("hybrid_score", "REAL"),
            ("execution_type", "VARCHAR(20)")
        ]
        
        for col_name, col_type in new_columns:
            if col_name in existing_columns:
                print(f"✅ '{col_name}' column already exists")
            else:
                print(f"➕ Adding '{col_name}' column...")
                cursor.execute(f"""
                    ALTER TABLE open_positions 
                    ADD COLUMN {col_name} {col_type}
                """)
                conn.commit()
                print(f"✅ '{col_name}' column added")
        
        print("\n✅ Migration completed!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
