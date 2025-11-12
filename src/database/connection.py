"""
Database connection ve engine yapılandırması
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

# Database path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "chimerabot.db")

# Engine oluştur
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={
        "check_same_thread": False,
        "timeout": 30  # ✅ 30 saniye timeout (database lock'tan korunma)
    },
    pool_pre_ping=True,  # ✅ Bağlantı sağlığını kontrol et
    pool_size=10,        # ✅ Connection pool boyutu
    max_overflow=20,     # ✅ Ekstra bağlantı limiti
    echo=False
)

# ✅ KRİTİK: WAL mode aktifleştir (concurrent write için)
# Bu SQLite'ı multi-threading'e uygun hale getirir
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    cursor.execute("PRAGMA synchronous=NORMAL")  # Performans için
    cursor.execute("PRAGMA cache_size=10000")  # Cache boyutu artır
    cursor.execute("PRAGMA temp_store=MEMORY")  # Temp veriler RAM'de
    cursor.close()

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
db_session = scoped_session(SessionLocal)
