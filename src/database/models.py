# src/database/models.py
import json
import time
import logging # <--- GÜNCELLENDİ: logging import edildi
from sqlalchemy import create_engine, Column, String, Integer, Float, BigInteger, DateTime, Text, TypeDecorator, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.sql import func
from datetime import datetime
import sys
import os

# Proje kökünü path'e ekle (config'i bulmak için)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path: sys.path.append(project_root)

# Loglamayı ayarla (bu modül için)
logger = logging.getLogger(__name__)

try:
    from src import config
    DATABASE_URL = config.DATABASE_URL # SQLite dosya yolunu al
    logger.info(f"Veritabanı modeli config'i yüklendi. Bağlantı: {DATABASE_URL}")
except ImportError:
    logger.error("models.py: config.py import edilemedi!")
    # Varsayılan olarak proje kökünde bir test DB'si oluştur
    # data klasörünün varlığından emin ol (yoksa init_db'de hata verir)
    data_dir_default = os.path.join(project_root, 'data')
    if not os.path.exists(data_dir_default):
        os.makedirs(data_dir_default)
    DB_FILE_PATH_DEFAULT = os.path.join(data_dir_default, 'default_chimerabot.db')
    DATABASE_URL = f"sqlite:///{DB_FILE_PATH_DEFAULT}"
    logger.warning(f"Varsayılan veritabanı yolu kullanılacak: {DATABASE_URL}")


# --- SQLite için Özel JSON Tipi ---
# SQLite, JSON tipini yerel olarak (PostgreSQL gibi) tam desteklemez.
# SQLAlchemy'nin bunu metin olarak saklamasını ve Python'da JSON olarak işlemesini sağlarız.
class JsonEncodedDict(TypeDecorator):
    """SQLite için JSON'ı string olarak saklamayı sağlar."""
    impl = Text # Arka planda TEXT sütunu olarak sakla
    cache_ok = True # GÜNCELLENDİ: SQLAlchemy 1.4+ için önerilir

    def process_bind_param(self, value, dialect):
        """Python objesini -> Veritabanı (string)"""
        if value is not None:
            return json.dumps(value) # Python dict'i JSON string'ine çevir
        return None

    def process_result_value(self, value, dialect):
        """Veritabanı (string) -> Python objesi"""
        if value is not None:
            try:
                return json.loads(value) # JSON string'ini Python dict'ine çevir
            except json.JSONDecodeError:
                logger.error(f"Cache'de bozuk JSON verisi bulundu: {value[:50]}...")
                return None
        return None

# SQLAlchemy kurulumu
# GÜNCELLENDİ: connect_args SQLite'a özeldir, PostgreSQL'e geçerken kaldırılmalı
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
# SessionLocal, her thread için ayrı bir session oluşturacak (scoped_session daha güvenli)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
# Base.query = db_session.query_property() # Bu şekilde kullanmak daha yaygın

# --- Tablo Modelleri ---

class OpenPosition(Base):
    """Mevcut açık pozisyonları takip eden tablo."""
    __tablename__ = "open_positions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    strategy = Column(String(50))
    direction = Column(String(5), nullable=False)
    quality_grade = Column(String(2))

    entry_price = Column(Float, nullable=False)
    sl_price = Column(Float, nullable=False) # Bu, Trailing Stop tarafından güncellenecek
    tp_price = Column(Float, nullable=False)
    rr_ratio = Column(Float)
    
    position_size_units = Column(Float)
    final_risk_usd = Column(Float)
    planned_risk_percent = Column(Float)
    
    # --- YENİ: Gerçek Zamanlı Değerleme için (Aşama 1) ---
    leverage = Column(Integer, default=2)  # Kullanılan kaldıraç (1x-3x)
    # ------------------------------------------------------
    
    correlation_group = Column(String(50))
    open_time = Column(BigInteger, default=lambda: int(time.time()))
    
    # Duygu skorları
    fng_index_at_signal = Column(Integer, nullable=True)
    news_sentiment_at_signal = Column(Float, nullable=True)
    reddit_sentiment_at_signal = Column(Float, nullable=True)
    google_trends_score_at_signal = Column(Float, nullable=True)
    
    # --- YENİ EKLENDİ (Aşama 3: Trailing Stop) ---
    trailing_stop_active = Column(Boolean, default=False)
    trailing_stop_distance = Column(Float, nullable=True) # Fiyattan ne kadar uzakta olacağı
    # Pozisyonun ulaştığı en yüksek/düşük fiyatı (high water mark) saklamak,
    # trailing stop'u doğru hesaplamak için çok önemlidir.
    high_water_mark = Column(Float, nullable=True) 
    # -----------------------------------------------
    
    # --- v4.0 Enhanced: Partial Profit Taking ---
    partial_tp_1_price = Column(Float, nullable=True)  # İlk kısmi TP hedef fiyatı
    partial_tp_1_percent = Column(Float, nullable=True)  # İlk kısmi TP'de kapatılacak pozisyon yüzdesi
    partial_tp_1_taken = Column(Boolean, default=False)  # İlk kısmi TP alındı mı?
    remaining_position_size = Column(Float, nullable=True)  # Kalan pozisyon boyutu
    # -----------------------------------------------
    
    # --- v5.0 AUTO-PILOT: Pozisyon Durumu ve Emir Takibi ---
    status = Column(String(20), default='PENDING', index=True)  # PENDING, ACTIVE, CLOSED
    market_order_id = Column(BigInteger, nullable=True)  # Açılış emri ID
    sl_order_id = Column(BigInteger, nullable=True)  # Stop Loss emri ID
    tp_order_id = Column(BigInteger, nullable=True)  # Take Profit emri ID
    # -----------------------------------------------

    def to_dict(self):
        """Objeyi sözlük formatına çevirir (eski kodla uyumluluk için)."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class TradeHistory(Base):
    """Kapanan tüm işlemleri kaydeden tablo."""
    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    strategy = Column(String(50))
    direction = Column(String(5), nullable=False)
    quality_grade = Column(String(2))

    entry_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    sl_price = Column(Float, nullable=False)
    tp_price = Column(Float, nullable=False)
    
    position_size_units = Column(Float)
    final_risk_usd = Column(Float)
    
    # --- YENİ: Gerçek Zamanlı Değerleme için (Aşama 1) ---
    leverage = Column(Integer, default=2)  # Kullanılan kaldıraç (1x-3x)
    # ------------------------------------------------------
    
    open_time = Column(BigInteger, nullable=False)
    close_time = Column(BigInteger, nullable=False)
    close_reason = Column(String(50)) # (STOP_LOSS, TAKE_PROFIT, MANUAL)
    
    pnl_usd = Column(Float)
    pnl_percent = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AlphaCache(Base):
    """Duygu analizi vb. verileri saklamak için Key-Value tablosu."""
    __tablename__ = "alpha_cache"
    
    key = Column(String(100), primary_key=True, index=True) # Örn: 'fng_index', 'rss_headlines'
    value = Column(JsonEncodedDict) # Özel JSON tipimizi kullanıyoruz
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# --- Veritabanını Başlatma ---
def init_db():
    """Veritabanı tablolarını oluşturur (eğer yoksa)."""
    global engine # init_db'nin global engine'i kullandığından emin olalım
    try:
        logger.info("Veritabanı tabloları kontrol ediliyor/oluşturuluyor...")
        Base.metadata.create_all(bind=engine)
        logger.info(f"✅ Veritabanı tabloları hazır: {DATABASE_URL}") # DATABASE_URL'i kullanalım
    except Exception as e:
        logger.critical(f"❌ Veritabanı başlatılamadı! Hata: {e}", exc_info=True)
        # config import hatası olabilir, DATABASE_URL'i loglayalım
        logger.critical(f"   Kullanılan DATABASE_URL: {DATABASE_URL}")
        logger.critical(f"   Lütfen veritabanı yolunu ve dosya izinlerini kontrol edin.")
        sys.exit(1)

# Bu script doğrudan çalıştırıldığında tabloları oluşturur
if __name__ == "__main__":
    # Test çalıştırması için de temel loglamayı açalım
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')
    print("Veritabanı tabloları oluşturuluyor...")
    
    # config import edilemediyse, DATABASE_URL varsayılan değerde kalmıştır
    if "default_chimerabot.db" in DATABASE_URL:
         print(f"UYARI: Gerçek config yüklenemedi, varsayılan veritabanı kullanılacak: {DATABASE_URL}")
    
    # Engine'i config'den gelen URL ile tekrar oluşturmayı garantileyelim
    # (Eğer config importu __name__ == "__main__" bloğundan önce başarısız olduysa)
    try:
        # Tekrar config'i import etmeyi denemeye gerek yok, en üstte denendi.
        # Sadece init_db'yi çağır.
        init_db()
        print(f"Tablolar {DATABASE_URL} üzerinde başarıyla oluşturuldu/kontrol edildi.")
    except Exception as e:
        print(f"Tablolar oluşturulurken hata oluştu: {e}")
        # Hata durumunda motoru ve URL'yi tekrar logla
        print(f"Kullanılan engine: {engine}")
        print(f"Kullanılan URL: {DATABASE_URL}")