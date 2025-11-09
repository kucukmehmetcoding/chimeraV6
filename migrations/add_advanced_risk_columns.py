"""
OpenPosition tablosuna gelişmiş risk yönetimi kolonları ekler
"""
import sys
import os

# Python path'e proje kök dizinini ekle
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import text
from src.database.connection import engine

def add_advanced_risk_columns():
    """OpenPosition tablosuna yeni kolonlar ekle"""
    
    # SQLite'da tablo isimleri küçük harfle saklanır
    table_name = "open_positions"  # OpenPosition → open_positions
    
    columns_to_add = [
        # Gelişmiş Risk Yönetimi (Trailing Stop & Partial TP)
        ("initial_sl", "REAL"),
        ("trailing_stop_active", "INTEGER DEFAULT 0"),
        ("trailing_stop_price", "REAL"),
        ("trailing_stop_distance", "REAL"),  # EKSİK KOLON
        ("high_water_mark", "REAL"),  # EKSİK KOLON
        
        # Kısmi Kar Alma (Partial TP)
        ("partial_tp_1_price", "REAL"),  # EKSİK KOLON
        ("partial_tp_1_filled", "INTEGER DEFAULT 0"),
        ("partial_tp_2_price", "REAL"),
        ("partial_tp_2_filled", "INTEGER DEFAULT 0"),
        
        # Breakeven & Risk Takibi
        ("breakeven_moved", "INTEGER DEFAULT 0"),
        ("current_risk_percent", "REAL"),
        ("max_favorable_excursion", "REAL DEFAULT 0.0"),
        ("max_adverse_excursion", "REAL DEFAULT 0.0"),
        
        # Risk Optimizasyonu Kolonları (models.py'de var ama DB'de eksik)
        ("volatility_score", "REAL"),
        ("sentiment_alignment", "REAL"),
        ("kelly_percent", "REAL"),
        ("kelly_confidence", "VARCHAR(10)"),
        ("risk_reasoning", "TEXT"),
        
        # Emir Takibi (models.py'de String olarak tanımlı)
        ("entry_order_id", "VARCHAR(50)"),
        ("oco_order_list_id", "VARCHAR(50)"),
        ("order_status", "VARCHAR(20) DEFAULT 'PENDING'")
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in columns_to_add:
            try:
                result = conn.execute(text(
                    f"SELECT COUNT(*) as cnt FROM pragma_table_info('{table_name}') "
                    f"WHERE name='{col_name}'"
                ))
                exists = result.fetchone()[0] > 0
                
                if not exists:
                    conn.execute(text(
                        f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                    ))
                    conn.commit()
                    print(f"✅ '{col_name}' kolonu eklendi")
                else:
                    print(f"ℹ️  '{col_name}' kolonu zaten mevcut")
                    
            except Exception as e:
                print(f"❌ '{col_name}' kolonu eklenirken hata: {e}")
                conn.rollback()

if __name__ == "__main__":
    print("🔄 Migration başlatılıyor...")
    add_advanced_risk_columns()
    print("✨ Migration tamamlandı!")
