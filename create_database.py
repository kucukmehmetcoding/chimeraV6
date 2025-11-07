#!/usr/bin/env python3
"""
Database tablolarını oluştur/güncelle
"""
import sys
import os

project_root = os.path.dirname(__file__)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.append(src_path)

from src.database.models import Base, engine, db_session

print("="*80)
print("DATABASE TABLO OLUŞTURMA")
print("="*80)
print()

try:
    # Tüm tabloları oluştur
    Base.metadata.create_all(bind=engine)
    
    print("✅ Tüm tablolar başarıyla oluşturuldu/güncellendi!")
    print()
    
    # Tabloları listele
    print("📊 Oluşturulan tablolar:")
    for table in Base.metadata.sorted_tables:
        print(f"   - {table.name}")
    
    print()
    print("="*80)
    
except Exception as e:
    print(f"❌ Hata: {e}")
    import traceback
    traceback.print_exc()
