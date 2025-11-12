#!/usr/bin/env python3
"""
FULL DATABASE RESET - Tüm pozisyonları ve trade history'yi sil
"""

import sys
import os
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from src.database.models import db_session, OpenPosition, TradeHistory

print("\n" + "="*80)
print("🗑️  FULL DATABASE RESET")
print("="*80)

db = db_session()

try:
    # OpenPosition sayısı
    open_count = db.query(OpenPosition).count()
    print(f"\n📊 Mevcut veriler:")
    print(f"   Açık pozisyonlar: {open_count}")
    
    # TradeHistory sayısı
    history_count = db.query(TradeHistory).count()
    print(f"   Trade history: {history_count}")
    
    if open_count == 0 and history_count == 0:
        print(f"\n✅ Database zaten temiz!")
    else:
        print(f"\n⚠️  Bu işlem GERİ ALINAMAZ!")
        print(f"   Tüm açık pozisyonlar ve trade history silinecek.")
        
        confirm = input("\n❓ Devam etmek istiyor musun? (evet/hayir): ").strip().lower()
        
        if confirm == 'evet':
            # OpenPosition sil
            if open_count > 0:
                db.query(OpenPosition).delete()
                print(f"   ✅ {open_count} açık pozisyon silindi")
            
            # TradeHistory sil
            if history_count > 0:
                db.query(TradeHistory).delete()
                print(f"   ✅ {history_count} trade history silindi")
            
            db.commit()
            
            print(f"\n✅ Database tamamen temizlendi!")
        else:
            print(f"\n❌ İşlem iptal edildi")

except Exception as e:
    print(f"\n❌ Hata: {e}")
    db.rollback()
    import traceback
    traceback.print_exc()
finally:
    db_session.remove()

print("\n" + "="*80 + "\n")
