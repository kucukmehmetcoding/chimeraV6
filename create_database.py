#!/usr/bin/env python3
"""
Database Schema Initialization Script
This script creates the necessary database tables using SQLAlchemy models.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def create_database_schema():
    """Create all database tables using SQLAlchemy models"""
    try:
        # Import database components
        from src.database.connection import engine
        from src.database.models import Base
        
        print("🔄 Creating database schema...")
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        print("✅ Database schema created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error creating database schema: {e}")
        return False

if __name__ == "__main__":
    success = create_database_schema()
    sys.exit(0 if success else 1)
