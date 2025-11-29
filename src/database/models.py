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
from contextlib import contextmanager

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
    
    amount = Column(Float, nullable=True)  # ✅ Pozisyon miktarı (coin cinsinden)
    position_size_units = Column(Float)
    position_size = Column(Float, nullable=True)  # Range trading için (coin miktarı)
    final_risk_usd = Column(Float)
    planned_risk_percent = Column(Float)
    
    # --- YENI: Gerçek Zamanlı Değerleme için (Aşama 1) ---
    leverage = Column(Integer, default=2)  # Kullanılan kaldıraç (1x-3x)
    margin = Column(Float, nullable=True)  # Başlangıç margin ($10 gibi)
    # ------------------------------------------------------
    
    # --- 🆕 v10.4: Margin-based TP/SL ---
    initial_margin = Column(Float, nullable=True)  # Başlangıç margin ($10)
    tp_margin = Column(Float, nullable=True)       # TP threshold ($14)
    sl_margin = Column(Float, nullable=True)       # SL threshold ($9)
    
    # --- 🆕 v12.1: Signal Source Tracking ---
    source = Column(String(20), default='scan')  # 'scan' or 'near_miss'
    # Fast mode için: Margin $14'e çıkınca TP, $9'a düşünce SL
    # -----------------------------------------------
    
    correlation_group = Column(String(50))
    open_time = Column(BigInteger, default=lambda: int(time.time()))
    
    # Duygu skorları
    fng_index_at_signal = Column(Integer, nullable=True)
    news_sentiment_at_signal = Column(Float, nullable=True)
    reddit_sentiment_at_signal = Column(Float, nullable=True)
    google_trends_score_at_signal = Column(Float, nullable=True)
    
    # --- YENİ EKLENDİ (Aşama 3: Gelişmiş Risk Yönetimi) ---
    # İlk SL değeri (referans için saklanır)
    initial_sl = Column(Float, nullable=True)
    
    # Trailing Stop
    trailing_stop_active = Column(Boolean, default=False)
    trailing_stop_price = Column(Float, nullable=True)  # Güncel trailing stop fiyatı
    trailing_stop_distance = Column(Float, nullable=True) # Fiyattan ne kadar uzakta olacağı
    high_water_mark = Column(Float, nullable=True)  # En yüksek/düşük fiyat (trailing için)
    
    # Kısmi Kar Alma (Partial TP)
    partial_tp_1_price = Column(Float, nullable=True)  # İlk kısmi TP hedef fiyatı
    partial_tp_1_filled = Column(Boolean, default=False)  # İlk kısmi TP alındı mı?
    partial_tp_2_price = Column(Float, nullable=True)  # İkinci kısmi TP hedef fiyatı
    partial_tp_2_filled = Column(Boolean, default=False)  # İkinci kısmi TP alındı mı?
    
    # Breakeven Hareket
    breakeven_moved = Column(Boolean, default=False)  # SL breakeven'a taşındı mı?
    
    # Risk Takibi
    current_risk_percent = Column(Float, nullable=True)  # Güncel risk yüzdesi
    max_favorable_excursion = Column(Float, default=0.0)  # En yüksek kar (MFE)
    max_adverse_excursion = Column(Float, default=0.0)  # En yüksek zarar (MAE)
    # -----------------------------------------------
    
    # --- v4.0 Enhanced: Partial Profit Taking (ESKİ - yukarıdakilerle birleştirildi) ---
    partial_tp_1_percent = Column(Float, nullable=True)  # İlk kısmi TP'de kapatılacak pozisyon yüzdesi
    partial_tp_1_taken = Column(Boolean, default=False)  # ESKİ isim - partial_tp_1_filled ile aynı
    partial_tp_2_percent = Column(Float, nullable=True)  # v8.1: İkinci kısmi TP'de kapatılacak pozisyon yüzdesi
    partial_tp_2_taken = Column(Boolean, default=False)  # v8.1: İkinci kısmi TP alındı mı?
    remaining_position_size = Column(Float, nullable=True)  # Kalan pozisyon boyutu
    # -----------------------------------------------
    
    # --- v5.0 AUTO-PILOT: Pozisyon Durumu ve Emir Takibi ---
    status = Column(String(20), default='PENDING', index=True)  # PENDING, ACTIVE, CLOSED
    market_order_id = Column(BigInteger, nullable=True)  # Açılış emri ID
    sl_order_id = Column(BigInteger, nullable=True)  # Stop Loss emri ID
    tp_order_id = Column(BigInteger, nullable=True)  # Take Profit emri ID
    # -----------------------------------------------

    # YENİ KOLONLAR - risk optimizasyonu için
    volatility_score = Column(Float, nullable=True, comment="ATR bazlı volatilite skoru (0-1)")
    sentiment_alignment = Column(Float, nullable=True, comment="Sinyal-sentiment uyum skoru (-1 ile 1)")
    kelly_percent = Column(Float, nullable=True, comment="Kelly Criterion yüzdesi")
    kelly_confidence = Column(String(10), nullable=True, comment="Kelly güven seviyesi: HIGH/MEDIUM/LOW/NONE")
    risk_reasoning = Column(Text, nullable=True, comment="Risk hesaplama açıklaması")
    
    # v10.7 Hybrid kolonları
    strategy_source = Column(String(20), nullable=True)  # v10.6, v10.7, etc.
    hybrid_score = Column(Float, nullable=True)  # Confirmation score
    execution_type = Column(String(20), nullable=True)  # market, limit, partial
    
    # 🆕 v11.3: Confluence Scoring System
    confluence_score = Column(Float, nullable=True)  # Multi-timeframe quality score (0-10)
    htf_score = Column(Float, nullable=True)  # HTF (1H) component score
    ltf_score = Column(Float, nullable=True)  # LTF (15M) component score
    
    # Yeni kolonlar
    entry_order_id = Column(String, nullable=True)  # Binance entry order ID
    oco_order_list_id = Column(String, nullable=True)  # Binance OCO list ID
    
    # 🤖 v12.0: AI Trading Signal Fields
    ai_confidence = Column(Integer, nullable=True)  # AI confidence score (0-100)
    ai_source = Column(String(50), nullable=True)  # deepseek, gemini, consensus, etc.
    ai_reasoning = Column(Text, nullable=True)  # AI'ın kararının açıklaması
    tp_order_id = Column(String, nullable=True)  # Take profit order ID
    sl_order_id = Column(String, nullable=True)  # Stop loss order ID
    order_status = Column(String, default='PENDING')  # PENDING, FILLED, CLOSED
    
    # 📊 v13.0: Range Trading Fields
    support_level = Column(Float, nullable=True)  # Destek seviyesi
    resistance_level = Column(Float, nullable=True)  # Direnç seviyesi
    range_width = Column(Float, nullable=True)  # Range genişliği (yüzde)
    
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
    
    # 🆕 v11.3: Confluence Scoring System (history tracking)
    confluence_score = Column(Float, nullable=True)  # Multi-timeframe quality score at entry
    htf_score = Column(Float, nullable=True)  # HTF component score
    ltf_score = Column(Float, nullable=True)  # LTF component score
    
    # 🤖 v12.0: AI Trading Signal Fields
    ai_confidence = Column(Integer, nullable=True)  # AI confidence score (0-100) at entry
    ai_source = Column(String(50), nullable=True)  # deepseek, gemini, consensus, etc.
    ai_reasoning = Column(Text, nullable=True)  # AI'ın kararının açıklaması
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ScannerSignal(Base):
    """
    Scanner tarafından bulunan tüm sinyalleri kaydeder (açılsın veya açılmasın).
    Tarihsel analiz ve performans takibi için kullanılır.
    """
    __tablename__ = "scanner_signals"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    signal_type = Column(String(10), nullable=False)  # bullish/bearish
    
    # Fiyat bilgileri
    price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    
    # Risk yönetimi
    rr_ratio = Column(Float)
    position_size_pct = Column(Float)
    sl_pct = Column(Float)
    tp_pct = Column(Float)
    
    # Kalite metrikleri
    strength = Column(Float)  # Signal strength (0-100)
    alignment = Column(Float)  # Timeframe alignment (0-100)
    quality_grade = Column(String(2))  # A/B/C/D
    quality_score = Column(Float)  # Detailed quality score
    
    # Timeframe data
    daily_trend = Column(String(10))  # bullish/bearish/sideways
    four_h_quality = Column(Float)
    one_h_confirm = Column(Boolean)
    
    # Market data
    market_cap = Column(Float)
    btc_correlation = Column(Float)
    
    # Scanner info
    scanner_version = Column(String(20), default='1h-4h-1d')
    scan_time = Column(DateTime, default=datetime.utcnow)
    
    # Position tracking
    position_opened = Column(Boolean, default=False)  # Bu sinyal için pozisyon açıldı mı?
    position_id = Column(Integer, nullable=True)  # OpenPosition ID (eğer açıldıysa)
    
    # Performance tracking (sonradan güncellenir)
    outcome = Column(String(20), nullable=True)  # 'win', 'loss', 'breakeven', 'pending'
    actual_pnl_pct = Column(Float, nullable=True)  # Gerçekleşen kar/zarar yüzdesi
    max_favorable = Column(Float, nullable=True)  # En yüksek kar noktası
    max_adverse = Column(Float, nullable=True)  # En kötü zarar noktası
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class NearMissSignal(Base):
    """
    Neredeyse geçen ama reddedilen sinyallerin gerçek zamanlı takibi.
    WebSocket ile izlenerek olgunlaştıklarında pozisyon açılır.
    """
    __tablename__ = "near_miss_signals"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    direction = Column(String(5), nullable=False)  # LONG/SHORT
    
    # Range bilgileri
    support = Column(Float, nullable=False)
    resistance = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    range_width_percent = Column(Float, nullable=False)
    
    # Kalite metrikleri
    quality_grade = Column(String(2))  # A/B/C/D
    quality_score = Column(Float)  # Numeric score for prioritization
    
    # Reddetme bilgisi
    rejection_reason = Column(String(100))  # "range_width", "quality", "rr_ratio", etc.
    missing_criteria_percent = Column(Float)  # Ne kadar yakın? (0.95 = %95 geçti)
    
    # HTF confirmation bilgisi
    htf_confirmed = Column(Boolean, default=False)
    htf_overlap_percent = Column(Float, nullable=True)
    
    # Zaman yönetimi
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Durum takibi
    is_active = Column(Boolean, default=True, index=True)
    is_consumed = Column(Boolean, default=False)  # Pozisyon açıldı mı?
    
    # Priority management
    priority_score = Column(Float, index=True)  # Combined score for WebSocket priority queue

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
        # SQLite dosyasının bulunduğu klasörü kontrol et ve oluştur
        if DATABASE_URL.startswith('sqlite:///'):
            db_file_path = DATABASE_URL.replace('sqlite:///', '')
            db_dir = os.path.dirname(db_file_path)
            
            # Klasör yoksa oluştur
            if db_dir and not os.path.exists(db_dir):
                logger.info(f"📁 Veritabanı klasörü oluşturuluyor: {db_dir}")
                os.makedirs(db_dir, exist_ok=True)
            
            # Database dosyası yoksa bilgi ver
            if not os.path.exists(db_file_path):
                logger.info(f"🆕 Yeni veritabanı oluşturuluyor: {db_file_path}")
        
        logger.info("Veritabanı tabloları kontrol ediliyor/oluşturuluyor...")
        Base.metadata.create_all(bind=engine)
        logger.info(f"✅ Veritabanı tabloları hazır: {DATABASE_URL}") # DATABASE_URL'i kullanalım
    except Exception as e:
        logger.critical(f"❌ Veritabanı başlatılamadı! Hata: {e}", exc_info=True)
        # config import hatası olabilir, DATABASE_URL'i loglayalım
        logger.critical(f"   Kullanılan DATABASE_URL: {DATABASE_URL}")
        logger.critical(f"   Lütfen veritabanı yolunu ve dosya izinlerini kontrol edin.")
        sys.exit(1)

@contextmanager
def get_db_session():
    """
    Thread-safe DB session context manager.
    Otomatik cleanup garantisi sağlar.
    
    Usage:
        with get_db_session() as db:
            positions = db.query(OpenPosition).all()
            db.commit()  # Opsiyonel - context manager otomatik commit yapar
    """
    session = db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"DB session error: {e}", exc_info=True)
        raise
    finally:
        db_session.remove()

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