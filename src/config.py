# src/config.py

import os
from dotenv import load_dotenv
import logging

# --- .env Dosyasını Yükle ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    print("Config: .env dosyası yüklendi.")
else:
    print(f"Config Uyarı: .env dosyası bulunamadı: {dotenv_path}")

# --- BOT Ayarları ---
BOT_VERSION = "11.5.0-AI" # v11.5 Gemini AI Integration - AI-Enhanced Signal Validation

# --- API Anahtarları ---
# Testnet moduna göre key seçimi
# GÜNCELLENDİ (8 Kasım 2025): Varsayılan False (LIVE MODE)
# Güvenlik: .env'de açıkça "True" yazılmadıkça LIVE mode kullanılır
BINANCE_TESTNET_RAW = os.getenv("BINANCE_TESTNET", "False")
BINANCE_TESTNET = BINANCE_TESTNET_RAW.lower() in ["true", "1", "yes"]

# Debug log - Trading mode kontrolü
print(f"🔍 Config Debug: BINANCE_TESTNET_RAW='{BINANCE_TESTNET_RAW}' → BINANCE_TESTNET={BINANCE_TESTNET}")
if BINANCE_TESTNET:
    print("⚠️  TESTNET MODE AKTIF - Test parası kullanılıyor")
else:
    print("🔴 LIVE MODE AKTIF - GERÇEK PARA KULLANILIYOR!")

if BINANCE_TESTNET:
    # Testnet mode - testnet keys kullan
    BINANCE_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "YOUR_TESTNET_API_KEY_HERE")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_TESTNET_SECRET_KEY", "YOUR_TESTNET_SECRET_KEY_HERE")
    print(f"🔍 Config Debug: TESTNET MODE - API Key başlangıcı: {BINANCE_API_KEY[:10]}...")
else:
    # Live mode - real keys kullan
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "YOUR_BINANCE_API_KEY_PLACEHOLDER")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "YOUR_BINANCE_SECRET_KEY_PLACEHOLDER")
    print(f"🔍 Config Debug: LIVE MODE - API Key başlangıcı: {BINANCE_API_KEY[:10]}...")

# --- Binance Futures Trading Ayarları (v5.0) ---
FUTURES_LEVERAGE = int(os.getenv("FUTURES_LEVERAGE", 10))  # Sabit kaldıraç (tüm pozisyonlar) - 10x
FUTURES_MARGIN_TYPE = os.getenv("FUTURES_MARGIN_TYPE", "ISOLATED")  # ISOLATED veya CROSS
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER")

# --- Reddit API ---
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", None)
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", None)
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", None)
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", None)
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "ChimeraBotSentiment/0.1 (by u/UnknownUser)")

# ============================================================================
# 🤖 MULTI-AI SYSTEM (v11.6: DeepSeek + Groq + Gemini)
# ============================================================================

# --- AI Provider Priority (Fallback Chain) ---
# 1. DeepSeek (crypto-trained, detailed)
# 2. Groq (fast, llama 3.1 70B)
# 3. Gemini (Google, backup)
AI_ENABLED = os.getenv("AI_ENABLED", "True").lower() == "true"  # Master AI switch
AI_PRIMARY_PROVIDER = os.getenv("AI_PRIMARY_PROVIDER", "deepseek")  # deepseek, groq, or gemini

# --- DeepSeek API (Primary - Crypto-Friendly) ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", None)
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")  # deepseek-chat or deepseek-coder
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MAX_TOKENS = int(os.getenv("DEEPSEEK_MAX_TOKENS", 2000))
DEEPSEEK_TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", 0.7))

# --- Groq API (Fast Fallback) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", None)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")  # Updated: 3.1 deprecated, using 3.3
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", 2000))
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", 0.7))

# --- Google Gemini API (Legacy Backup) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENABLED = os.getenv("GEMINI_ENABLED", "True").lower() == "true"

# --- AI Features (Universal) ---
AI_NEWS_ANALYSIS = os.getenv("AI_NEWS_ANALYSIS", "True").lower() == "true"  # Deep news sentiment
AI_SIGNAL_VALIDATION = os.getenv("AI_SIGNAL_VALIDATION", "True").lower() == "true"  # Pre-signal approval
AI_MARKET_CONTEXT = os.getenv("AI_MARKET_CONTEXT", "True").lower() == "true"  # BTC market regime
AI_TP_SL_OPTIMIZER = os.getenv("AI_TP_SL_OPTIMIZER", "False").lower() == "true"  # Dynamic TP/SL (experimental)

# --- AI Rate Limiting ---
AI_MAX_REQUESTS_PER_MINUTE = int(os.getenv("AI_MAX_REQUESTS_PER_MINUTE", 30))  # Combined limit
AI_REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", 30))  # seconds
AI_RETRY_ATTEMPTS = int(os.getenv("AI_RETRY_ATTEMPTS", 2))

# --- AI Cache Settings ---
AI_NEWS_CACHE_MINUTES = int(os.getenv("AI_NEWS_CACHE_MINUTES", 30))  # Cache news analysis
AI_MARKET_CONTEXT_CACHE_MINUTES = int(os.getenv("AI_MARKET_CONTEXT_CACHE_MINUTES", 15))  # Cache market regime

# ============================================================================
# 📰 AUTOMATED NEWS ANALYZER (v11.7: DeepSeek Market Sentiment)
# ============================================================================

# --- News Analyzer Settings ---
NEWS_ANALYZER_ENABLED = os.getenv("NEWS_ANALYZER_ENABLED", "True").lower() == "true"  # Master switch
NEWS_CHECK_INTERVAL_HOURS = int(os.getenv("NEWS_CHECK_INTERVAL_HOURS", 4))  # How often to analyze market
NEWS_MAX_ARTICLES = int(os.getenv("NEWS_MAX_ARTICLES", 30))  # Articles per analysis

# News feeds are already defined below as SENTIMENT_RSS_FEEDS (8 sources)
# Fear & Greed API: https://api.alternative.me/fng/ (no auth required)

# --- AI Response Thresholds ---
AI_MIN_CONFIDENCE_FOR_APPROVAL = float(os.getenv("AI_MIN_CONFIDENCE_FOR_APPROVAL", 6.0))  # 0-10 scale
AI_REJECTION_THRESHOLD = float(os.getenv("AI_REJECTION_THRESHOLD", 4.0))  # Below this = reject signal

# ============================================================================
# 🤖 AI TRADING SIGNAL GENERATION (v12.0: DeepSeek + Gemini Hybrid)
# ============================================================================

# --- AI Trading Mode ---
AI_TRADING_ENABLED = os.getenv("AI_TRADING_ENABLED", "False").lower() == "true"  # Master switch for AI signals
AI_TRADING_MODE = os.getenv("AI_TRADING_MODE", "HYBRID")  # FULL (AI only), HYBRID (AI + traditional), ASSIST (AI validates traditional)

# --- AI Signal Confidence Thresholds ---
MIN_AI_CONFIDENCE_SCORE = int(os.getenv("MIN_AI_CONFIDENCE_SCORE", 70))  # Minimum confidence to open position (0-100)
AI_FALLBACK_THRESHOLD = int(os.getenv("AI_FALLBACK_THRESHOLD", 60))  # Below this, ask Gemini for second opinion
AI_CONSENSUS_BOOST = int(os.getenv("AI_CONSENSUS_BOOST", 15))  # Confidence boost when both AIs agree

# --- Gemini Fallback Settings ---
AI_FALLBACK_ENABLED = os.getenv("AI_FALLBACK_ENABLED", "True").lower() == "true"  # Use Gemini as fallback
MAX_DAILY_GEMINI_CALLS = int(os.getenv("MAX_DAILY_GEMINI_CALLS", 30))  # Cost control (Flash: ~$0.10/call = $3/day)

# --- AI Models for Trading ---
DEEPSEEK_TRADING_MODEL = os.getenv("DEEPSEEK_TRADING_MODEL", "deepseek-chat")  # Free, unlimited
GEMINI_TRADING_MODEL = os.getenv("GEMINI_TRADING_MODEL", "gemini-2.5-flash")  # Fast, cheap ($0.10/1M tokens)

# --- AI Signal Validation ---
AI_VALIDATE_RR_RATIO = os.getenv("AI_VALIDATE_RR_RATIO", "True").lower() == "true"  # Check risk/reward logic
AI_MIN_RR_RATIO = float(os.getenv("AI_MIN_RR_RATIO", 1.5))  # Minimum R:R for AI signals (1.5 = 1:1.5)
AI_MAX_PRICE_DEVIATION_PERCENT = float(os.getenv("AI_MAX_PRICE_DEVIATION_PERCENT", 5.0))  # Entry price vs current (sanity check)

# --- AI vs Traditional Strategy ---
TRADITIONAL_STRATEGIES_ENABLED = os.getenv("TRADITIONAL_STRATEGIES_ENABLED", "True").lower() == "true"  # Keep traditional strategies active
AI_OVERRIDE_TRADITIONAL = os.getenv("AI_OVERRIDE_TRADITIONAL", "False").lower() == "true"  # AI signals override traditional if conflict

# Legacy Gemini backward compatibility
GEMINI_NEWS_ANALYSIS = AI_NEWS_ANALYSIS
GEMINI_SIGNAL_VALIDATION = AI_SIGNAL_VALIDATION
GEMINI_MARKET_CONTEXT = AI_MARKET_CONTEXT
GEMINI_TP_SL_OPTIMIZER = AI_TP_SL_OPTIMIZER
GEMINI_MAX_REQUESTS_PER_MINUTE = AI_MAX_REQUESTS_PER_MINUTE
GEMINI_REQUEST_TIMEOUT = AI_REQUEST_TIMEOUT
GEMINI_RETRY_ATTEMPTS = AI_RETRY_ATTEMPTS
GEMINI_NEWS_CACHE_MINUTES = AI_NEWS_CACHE_MINUTES
GEMINI_MARKET_CONTEXT_CACHE_MINUTES = AI_MARKET_CONTEXT_CACHE_MINUTES
GEMINI_MIN_CONFIDENCE_FOR_APPROVAL = AI_MIN_CONFIDENCE_FOR_APPROVAL
GEMINI_REJECTION_THRESHOLD = AI_REJECTION_THRESHOLD

# --- Dosya Yolları ve Dizinler ---
DATA_DIR = os.path.join(project_root, 'data')
LOG_DIR = os.path.join(project_root, 'logs')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# --- Veritabanı Ayarları (SQLite) ---
DB_FILE_NAME = "chimerabot.db"
DB_FILE_PATH = os.path.join(DATA_DIR, DB_FILE_NAME) 
DATABASE_URL = f"sqlite:///{DB_FILE_PATH}"

# --- Loglama Ayarları ---
LOG_FILE = os.path.join(LOG_DIR, 'chimerabot.log')
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
if LOG_LEVEL not in valid_log_levels:
    print(f"Config Uyarı: Geçersiz LOG_LEVEL '{LOG_LEVEL}'. 'INFO' kullanılacak.")
    LOG_LEVEL = 'INFO'

# --- Tarama Ayarları ---
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", 2))  # GÜNCELLENDİ: 5dk → 2dk (v4.0 Enhancement)
# Near-full futures coverage: allow higher ceiling (Binance USDT perpetuals ~> 350-500 range over time)
MAX_COINS_TO_SCAN = int(os.getenv("MAX_COINS_TO_SCAN", 600))  # 300 → 600 (daha geniş kapsam)
# Hafif artan gecikme (rate limit güvenliği) fakat toplam kapsam daha büyük
SCAN_DELAY_SECONDS = float(os.getenv("SCAN_DELAY_SECONDS", 0.7))  # 0.5 → 0.7

# 🆕 v10.0 MEHMET KÜÇÜK STRATEJİSİ - 15m Fast Trading Mode (DEPRECATED - use 1H EMA mode)
# True: Sadece 15m timeframe, Mehmet Küçük stratejisi, sabit SL/TP/Leverage
# False: Eski multi-timeframe sistem (1D/4H/1H) ve tüm stratejiler
ENABLE_15M_FAST_MODE = os.getenv("ENABLE_15M_FAST_MODE", "False").lower() == "true"

# 15m Fast Mode Parametreleri (sadece ENABLE_15M_FAST_MODE=True ise kullanılır)
FAST_MODE_TIMEFRAME = "15m"  # Sabit 15 dakika
FAST_MODE_TP_PERCENT = 25.0  # TP: Entry'den +%25 (DEPRECATED - margin-based kullan)
FAST_MODE_SL_PERCENT = 5.0   # SL: Entry'den -%5 (DEPRECATED - margin-based kullan)
FAST_MODE_LEVERAGE = 10      # Sabit 10x kaldıraç
FAST_MODE_BASE_SIZE_USD = 10.0  # Base position size: 10 USD (margin = 10 × leverage = 100 USD position)

# 🆕 v10.4: Margin-based TP/SL (unrealized PnL ile margin tracking)
FAST_MODE_TP_MARGIN = 14.0   # TP: Margin $10 → $14 olunca kapat (+$4 kar)
FAST_MODE_SL_MARGIN = 9.0    # SL: Margin $10 → $9 olunca kapat (-$1 zarar)
# R:R Ratio: 4.0 ($4 kar / $1 zarar)

# 🆕 v10.5: 1H EMA CROSSOVER MODE - EMA5 x EMA20 kesişim stratejisi
# True: 1 saatlik EMA crossover aktif (15m devre dışı kalır)
# False: Eski sistemler aktif
ENABLE_1H_EMA_MODE = os.getenv("ENABLE_1H_EMA_MODE", "True").lower() == "true"

# 1H EMA Mode Parametreleri
EMA_MODE_TIMEFRAME = "1h"           # Sabit 1 saat
EMA_MODE_LEVERAGE = 10              # Kaldıraç (10x)
EMA_MODE_BASE_SIZE_USD = 10.0       # Base margin ($10)
EMA_MODE_TP_MARGIN = 14.0           # TP: Margin $10 → $14 olunca kapat (+$4 kar)
EMA_MODE_SL_MARGIN = 9.0            # SL: Margin $10 → $9 olunca kapat (-$1 zarar)
# R:R Ratio: 4.0 ($4 kar / $1 zarar)

# 🆕 v10.6: WEBSOCKET REAL-TIME MONITORING - Phase 1
# 🔥 v11.6.2: STRICT LAST-CANDLE CROSSOVER CHECK
# WebSocket için kline stream interval (crossover detection için)
WEBSOCKET_KLINE_INTERVAL = "15m"    # 15 dakikalık mumlar (real-time monitoring)
WEBSOCKET_ENABLED = os.getenv("WEBSOCKET_ENABLED", "True").lower() == "true"  # WebSocket aktif/pasif
WEBSOCKET_STRICT_CROSSOVER = os.getenv("WEBSOCKET_STRICT_CROSSOVER", "True").lower() == "true"  # Sadece SON MUMDA crossover kabul

# 🎯 CROSSOVER DETECTION LOGIC:
# True (STRICT):  Sadece son mumda EMA5 x EMA20 kesişimi → Taze sinyaller
# False (RELAXED): Son 3-5 mum içinde kesişim → Trend kaçırma riski!
# ÖNERİLEN: True (strict mode) - trend kaçırma yerine doğruluk öncelikli

# v8.1: Rotating Scan (tüm coinlerin döngüsel taranması)
ENABLE_ROTATING_SCAN = os.getenv("ENABLE_ROTATING_SCAN", "True").lower() == "true"  # True: Rotating mode, False: İlk N coin
SCAN_CHUNK_SIZE = int(os.getenv("SCAN_CHUNK_SIZE", 120))  # Her cycle taranacak alt küme (örn. 120 coin)
ADAPTIVE_CHUNK_ENABLED = os.getenv("ADAPTIVE_CHUNK_ENABLED", "True").lower() == "true"  # Hacim / volatilite önceliklendirme
CHUNK_HIGH_VOLUME_THRESHOLD_USD = float(os.getenv("CHUNK_HIGH_VOLUME_THRESHOLD_USD", 5_000_000))  # 24h USDT hacmi eşiği
CHUNK_HIGH_VOLATILITY_THRESHOLD = float(os.getenv("CHUNK_HIGH_VOLATILITY_THRESHOLD", 0.08))  # ATR/price oranı
CHUNK_RECENT_SIGNAL_BOOST_HOURS = int(os.getenv("CHUNK_RECENT_SIGNAL_BOOST_HOURS", 6))  # Son X saatte sinyal alan coin öncelik artışı
CHUNK_PRIORITY_LOG_INTERVAL = int(os.getenv("CHUNK_PRIORITY_LOG_INTERVAL", 3600))  # Öncelik dump süresi (sn)

# --- v4.0 Enhanced: Dinamik Coin Listesi ---
# 'MANUAL': CORRELATION_GROUPS içindeki coinleri kullan (106 coin)
# 'AUTO_FUTURES': Binance Futures'tan tüm USDT çiftlerini otomatik çek (~300+ coin)
COIN_LIST_MODE = os.getenv("COIN_LIST_MODE", "AUTO_FUTURES")  # v4.0: Otomatik mod varsayılan
AUTO_FUTURES_UPDATE_HOURS = int(os.getenv("AUTO_FUTURES_UPDATE_HOURS", 24))  # Liste güncelleme sıklığı
# ------------------------------------------------------

# --- YENİ EKLENDİ: Hızlı Ön Filtreleme Ayarları (v4.0 Enhancement) ---
# v9.0 PRECISION MODE: Kaliteli sinyal için sıkı filtreler
# Taramaya dahil etmek için minimum 24 saatlik USDT hacmi
PRE_SCREEN_MIN_VOLUME_USD = float(os.getenv("PRE_SCREEN_MIN_VOLUME_USD", 300_000)) # 3M → 300K (daha geniş kapsam)
# Taramaya dahil etmek için minimum 24 saatlik mutlak fiyat değişimi yüzdesi (düşürüldü)
PRE_SCREEN_MIN_PRICE_CHANGE_PERCENT = float(os.getenv("PRE_SCREEN_MIN_PRICE_CHANGE_PERCENT", 0.7)) # 2.5% → 0.7%
# Filtreleme modu: geniş kapsam için OR (hacim ya da momentum yeterli ise dahil et)
PRE_SCREEN_FILTER_MODE = os.getenv("PRE_SCREEN_FILTER_MODE", "OR")  # AND → OR

# v9.0: Stablecoin ve düşük volatilite coinleri blacklist (taramadan çıkar)
BLACKLISTED_SYMBOLS = {
    # Stablecoinler
    'USDCUSDT', 'BUSDUSDT', 'TUSDUSDT', 'USDPUSDT', 'DAIUSDT', 'FDUSDUSDT', 'PAXGUSDT',
    # Düşük volatilite / wrapped tokenlar
    'WBTCUSDT', 'STETHUSDT', 'WETHUSDT', 'RENBTCUSDT', 
    # Legacy düşük performans coinler (isteğe bağlı ekleyin)
    'XEMUSDT', 'SCUSDT', 'BTTCUSDT', 'WINUSDT', 'HOTUSDT', 'DENTUSDT',
}
# -----------------------------------------------------------

# --- Risk Yönetimi (v8.0 HİBRİT SİSTEM) ---
USE_FIXED_RISK_USD = True  # True: Sabit risk ($), False: Portföy yüzdesi
FIXED_RISK_USD = float(os.getenv("FIXED_RISK_USD", 20.0))  # Sabit risk miktarı (USD)
# v12.0 RESTORED: Minimum RR oranı discipline restore edildi
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", 1.2))  # 0.95 → 1.2 (balanced, was 1.5)
MIN_RR_RATIO_GRADE_A = float(os.getenv("MIN_RR_RATIO_GRADE_A", 1.0))  # A-grade için relaxed
MIN_RR_RATIO_GRADE_B = float(os.getenv("MIN_RR_RATIO_GRADE_B", 1.2))  # B-grade için standard
MIN_RR_RATIO_GRADE_C = float(os.getenv("MIN_RR_RATIO_GRADE_C", 1.5))  # C-grade için strict
USE_REAL_BALANCE = os.getenv("USE_REAL_BALANCE", "True").lower() == "true"  # Gerçek bakiyeyi Binance'den al

# 🎯 v9.0 PRECISION MODE: KALİTELİ SİNYALLERE YÜKSEK POZİSYON
# Mantık: Az ama ÇOK KALİTELİ sinyaller → Her sinyal için YÜKSEK risk al
# Filtreleme: %90'ı filtrelenecek → Geriye kalan %10 sinyaller ALTIN değerinde
# Strateji: 1-2 sinyal/gün ama her biri $30-50 risk (normal: $15)
FIXED_RISK_USD = float(os.getenv('FIXED_RISK_USD', '30.0'))  # $15 → $30 (2x artış - kaliteli sinyaller)

# 🆕 v9.2 CRITICAL FIX: Minimum MARGIN (kullanılan sermaye)
# Kullanıcı talebi: "Günde 1-2 pozisyon, kullanılan margin çok düşük (5 USD)"
# ÖNEMLİ: Bu değer MARGIN (teminat), position value DEĞİL!
# Örnek: 150 USD margin × 8x kaldıraç = 1200 USD position value
MIN_MARGIN_USD = float(os.getenv('MIN_MARGIN_USD', '5.0'))   # Minimum kullanılan margin - 5x kaldıraç ile 25$ pozisyon
MAX_MARGIN_USD = float(os.getenv('MAX_MARGIN_USD', '5.0'))   # Maksimum kullanılan margin - sabit 5$

# Eski değerler (yedek - artık kullanılmıyor)
MIN_POSITION_VALUE_USD = MIN_MARGIN_USD * 10  # Geriye dönük uyumluluk için (10x kaldıraç)
MAX_POSITION_VALUE_USD = MAX_MARGIN_USD * 10  # Geriye dönük uyumluluk için (10x kaldıraç)

BASE_RISK_PERCENT = 1.0  # Varsayılan %1 risk (dinamik sistem kapalıysa)

# v12.0 BALANCED: Pozisyon limitleri balanced restore
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 15))  # 30 → 15 (over-diversification önleme)
MAX_RISK_PER_GROUP = float(os.getenv("MAX_RISK_PER_GROUP", 15.0))  # 30.0 → 15.0 (risk yoğunlaşması önleme)
USE_KELLY_ADJUSTMENT = os.getenv("USE_KELLY_ADJUSTMENT", "True").lower() == "true"  # Kelly Criterion aktif
# 🆕 v9.3: Kelly maksimum fraksiyon limiti (ek güvenlik)
KELLY_MAX_FRACTION = float(os.getenv("KELLY_MAX_FRACTION", 0.15))  # Kelly yüzdesi üst sınırı (örn. %15)
# v12.0 RESTORED: MIN RR oranı discipline restore edildi (strategy-specific overrides)
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", 1.2))  # 0.95 → 1.2 balanced restore
MAX_POSITIONS_PER_SYMBOL = int(os.getenv("MAX_POSITIONS_PER_SYMBOL", 1))

# v12.0 NEW: Quality grade-based position sizing multipliers
QUALITY_MARGIN_MULTIPLIERS = {
    'A': float(os.getenv("QUALITY_MULTIPLIER_A", 1.5)),  # A-grade sinyaller için 1.5x margin
    'B': float(os.getenv("QUALITY_MULTIPLIER_B", 1.0)),  # B-grade standart
    'C': float(os.getenv("QUALITY_MULTIPLIER_C", 0.6)),  # C-grade azaltılmış
    'D': float(os.getenv("QUALITY_MULTIPLIER_D", 0.0))   # D-grade hiç pozisyon açma
}

# 🆕 v11.3: CONFLUENCE SCORING SYSTEM
# Multi-timeframe kalite skoru: HTF (1H) + LTF (15M) + Sentiment
# Max score: ~8.6/10 → Minimum 3.5 gerekli (basitleştirilmiş, daha fazla sinyal)
MIN_CONFLUENCE_SCORE = float(os.getenv("MIN_CONFLUENCE_SCORE", 3.5))  # v11.4: 5.0 → 3.5 basitleştirme

# 🔄 BREAKOUT L1 scalp fallback toggle
ENABLE_BREAKOUT_SCALP_FALLBACK = os.getenv("ENABLE_BREAKOUT_SCALP_FALLBACK", "True").lower() == "true"
# Semi / Extended squeeze ek sıkılaştırma configleri
BREAKOUT_SEMI_EXT_BBW_PERCENTILE_MAX = float(os.getenv("BREAKOUT_SEMI_EXT_BBW_PERCENTILE_MAX", 18.0))
# Ek hacim/body/distance tighten farkları (config ile override edilebilir)
BREAKOUT_SEMI_EXT_VOLUME_EXTRA = float(os.getenv("BREAKOUT_SEMI_EXT_VOLUME_EXTRA", 0.15))
BREAKOUT_EXT_VOLUME_EXTRA = float(os.getenv("BREAKOUT_EXT_VOLUME_EXTRA", 0.25))
BREAKOUT_SEMI_EXT_BODY_EXTRA = float(os.getenv("BREAKOUT_SEMI_EXT_BODY_EXTRA", 3.0))
BREAKOUT_EXT_BODY_EXTRA = float(os.getenv("BREAKOUT_EXT_BODY_EXTRA", 5.0))
BREAKOUT_SEMI_EXT_DISTANCE_EXTRA = float(os.getenv("BREAKOUT_SEMI_EXT_DISTANCE_EXTRA", 0.03))
BREAKOUT_EXT_DISTANCE_EXTRA = float(os.getenv("BREAKOUT_EXT_DISTANCE_EXTRA", 0.05))

# 🔧 Dinamik Minimum Margin: En az (MIN_MARGIN_USD, MIN_PER_LEVERAGE_USD × leverage)
# Not: Mutlak 10–30$ aralığını korumak için kaldıraç bazlı minimumu kapatıyoruz (0.0)
MIN_PER_LEVERAGE_USD = float(os.getenv("MIN_PER_LEVERAGE_USD", 0.0))

# --- v5.0 AUTO-PILOT: Sermaye Yönetimi (Capital Manager) ---
MAX_DRAWDOWN_PERCENT = float(os.getenv("MAX_DRAWDOWN_PERCENT", -50.0))  # Devre kesici limiti (%)
PROFIT_TARGET_PERCENT = float(os.getenv("PROFIT_TARGET_PERCENT", 40.0))  # Kâr realizasyonu hedefi (%)
# v11.1 LIVE MODE: Otomatik kapanma AKTİF (maksimum zararda bot durur)
AUTO_CLOSE_ON_CIRCUIT_BREAKER = os.getenv("AUTO_CLOSE_ON_CIRCUIT_BREAKER", "True").lower() == "true"  # ✅ GÜVENLİK
AUTO_TRANSFER_PROFIT = os.getenv("AUTO_TRANSFER_PROFIT", "False").lower() == "true"  # Otomatik kâr transferi
# 🆕 v9.3 PORTFÖY GÜVENLİĞİ: Günlük risk bütçesi ve devre kesici
MAX_DAILY_RISK_PERCENT = float(os.getenv("MAX_DAILY_RISK_PERCENT", 5.0))  # Günlük toplam yeni risk bütçesi (% portföy)
MAX_DAILY_DRAWDOWN_PERCENT = float(os.getenv("MAX_DAILY_DRAWDOWN_PERCENT", 5.0))  # Günlük max DD (yeni pozisyonları durdur)
# -----------------------------------------------------------

# --- v8.0 DİNAMİK Kaldıraç Sistemi ---
# Dinamik kaldıraç AKTİF - SL mesafesine göre otomatik ayarlama

# v8.0 UPDATED: Dinamik kaldıraç sistemi aktif
DYNAMIC_LEVERAGE_ENABLED = os.getenv("DYNAMIC_LEVERAGE_ENABLED", "True").lower() == "true"

# Varsayılan kaldıraç (dinamik sistem kapalıysa kullanılır)
# Dinamik sistemde bu değer referans olarak kullanılır
FUTURES_LEVERAGE = int(os.getenv("FUTURES_LEVERAGE", 10))  # Varsayılan 10x kaldıraç

# DİNAMİK SİSTEM: SL mesafesine göre kaldıraç seçimi
# Örnek: SL %1 dar → 10x kaldıraç, SL %10 geniş → 3x kaldıraç
LEVERAGE_BY_SL_DISTANCE = {
    0.010: 10,  # SL mesafesi %1'den dar ise → 10x kaldıraç
    0.018: 8,   # SL mesafesi %1.8'den dar ise → 8x kaldıraç  
    0.030: 5,   # SL mesafesi %3'den dar ise → 5x kaldıraç
    0.050: 4,   # SL mesafesi %5'den dar ise → 4x kaldıraç
    0.100: 3    # SL mesafesi %10'dan geniş ise → 3x kaldıraç
}
MINIMUM_SAFETY_MARGIN = 0.08  # SL ile tasfiye arası minimum %8 mesafe

# VOLATİLİTE BAZLI YEDEK SİSTEM (dinamik sistem kapalıysa)
LEVERAGE_LOW_VOLATILITY = 8   # Düşük volatilite (ATR/Price < %5)
LEVERAGE_MID_VOLATILITY = 5   # Orta volatilite (ATR/Price %5-15)
LEVERAGE_HIGH_VOLATILITY = 3  # Yüksek volatilite (ATR/Price > %15)
# ----------------------------------------------------------------

# SL/TP Hesaplama Ayarları
SL_LOOKBACK_PERIOD = int(os.getenv("SL_LOOKBACK_PERIOD", 50))
SL_BUFFER_PERCENT = float(os.getenv("SL_BUFFER_PERCENT", 0.5))
TP_BUFFER_PERCENT = float(os.getenv("TP_BUFFER_PERCENT", 0.5))

# --- YENİ EKLENDİ: Portföy Korelasyon Ayarları (Aşama 4) ---
# Yeni bir pozisyon açmak için portföydeki diğer pozisyonlarla izin verilen max korelasyon
# v5.0: 0.75 → 0.80 (daha fazla pozisyon için)
MAX_CORRELATION_ALLOWED = float(os.getenv("MAX_CORRELATION_ALLOWED", 0.80))
# Korelasyon matrisi ne sıklıkla güncellenecek (saniye) - 24 saat
CORRELATION_UPDATE_INTERVAL_SECONDS = 3600 * 24
# Korelasyon hesaplaması için kaç günlük 1D veri kullanılacak
CORRELATION_CALCULATION_DAYS = 30
# -----------------------------------------------------------

# --- v4.0 Enhanced: Volatilite Bazlı Position Sizing ---
VOLATILITY_ADJUSTMENT_ENABLED = True  # Volatilite skoru ile pozisyon boyutunu ayarla
VOLATILITY_LOW_THRESHOLD = 0.05  # ATR/Price < 5% = Düşük volatilite
VOLATILITY_HIGH_THRESHOLD = 0.15  # ATR/Price > 15% = Yüksek volatilite
VOLATILITY_LOW_MULTIPLIER = 1.2  # Düşük volatilitede pozisyon boyutunu %20 artır
VOLATILITY_HIGH_MULTIPLIER = 0.7  # Yüksek volatilitede pozisyon boyutunu %30 azalt
# ---------------------------------------------------------

# --- v6.0 SIMPLIFIED: Yüzde Tabanlı SL/TP Sistemi (7 Kasım 2025) ---
# v9.2 UPDATED: 3 SL/TP Sistemi seçeneği

# SL/TP Hesaplama Yöntemi Seçimi:
# 'PERCENTAGE': Sabit yüzde bazlı (basit, hızlı, tutarlı)
# 'ATR': Volatilite bazlı (adaptif, her coin için farklı)
# 'SMART': Hibrit (ATR + Fibonacci + Swing Levels) - EN İYİ! 🎯
SL_TP_METHOD = os.getenv("SL_TP_METHOD", "SMART")  # PERCENTAGE, ATR, veya SMART

# Geriye dönük uyumluluk için (eski kod hala USE_PERCENTAGE_SL_TP kullanıyor)
USE_PERCENTAGE_SL_TP = (SL_TP_METHOD == "PERCENTAGE")

# 🔧 HİBRİT SİSTEM İÇİN OPTİMİZE
# Stop Loss: Pozisyon değerinin %10 zararında
SL_PERCENT = float(os.getenv("SL_PERCENT", 10.0))  # %10 zarar (pozisyon değeri bazında)

# 🆕 v9.2 PLAN A: Partial TP Kapalı - Tek TP Sistemi
# Neden? Küçük pozisyonlarda 3 işlem komisyonu çok fazla!
# Önceki: Açılış + TP1 + TP2/SL = 3 işlem (komisyon: $0.036)
# Yeni: Açılış + TP/SL = 2 işlem (komisyon: $0.024) → %33 tasarruf!

PARTIAL_TP_ENABLED = False  # ❌ KAPALI - Tek TP kullanılacak
TP_PROFIT_PERCENT = 30.0  # Tek TP: Pozisyon değerinin %30 karı (3.0 R:R)

# Eski partial TP ayarları (yedek - kullanılmıyor)
PARTIAL_TP_1_PERCENT = 50.0  # (Devre dışı)
PARTIAL_TP_1_PROFIT_PERCENT = 20.0  # (Devre dışı)
PARTIAL_TP_2_PROFIT_PERCENT = 40.0  # (Devre dışı)

# Hesaplama Örneği (v9.2 TEK TP SİSTEMİ):
# Min Margin: $150 (MIN_MARGIN_USD)
# Kaldıraç: 8x → Pozisyon Değeri: $1200
# SL: -$120 (pozisyon değerinin %10'u) = Maksimum kayıp
# TP: +$360 (pozisyon değerinin %30'u) = R:R = 3.0
# 
# Komisyon Karşılaştırması ($1200 pozisyon):
# • Partial TP Açık: 3 işlem × 0.04% = $1.44 komisyon
# • Partial TP Kapalı: 2 işlem × 0.04% = $0.96 komisyon
# • Tasarruf: $0.48/trade (%33 azalma)
# 
# v9.2 SİSTEM ÖZELLİKLERİ:
# • Min Margin: $150 (önceki: $5)
# • Pozisyon Değeri: $1200 (8x kaldıraç)
# • SL: -$120 (10% zarar)
# • TP: +$360 (30% kâr, 3.0 R:R)
# • Komisyon: %33 daha düşük
# • Basit, güvenilir, test edilmiş
# ---------------------------------------------------------

# --- v7.0: Korelasyon Bazlı Rejim Seçimi ---
BTC_CORRELATION_THRESHOLD = float(os.getenv("BTC_CORRELATION_THRESHOLD", 0.5))
# 0.5'den yüksek korelasyonlu coinler BTC'nin rejimini takip eder
# 0.5'den düşük olanlar kendi ADX/BBW verilerine göre karar verir
# Grup bazlı eşikler için CORRELATION_THRESHOLDS kullanılabilir

# Strateji Filtre Ayarları
MAX_ATR_PERCENT = float(os.getenv("MAX_ATR_PERCENT", 5.0))
# 🆕 v9.3: Rejim yumuşatma ve sentiment tazelik eşikleri
REGIME_SMOOTHING_WINDOW = int(os.getenv("REGIME_SMOOTHING_WINDOW", 5))  # En son N rejimden çoğunluk oyu
STALE_SENTIMENT_MINUTES = int(os.getenv("STALE_SENTIMENT_MINUTES", 180))  # 3 saatten eski sentiment verisi cezalandırılır
# ... (dosyanın geri kalanı aynı) ...

# --- v5.0 ULTRA-OPTIMIZED: Kalite Notu Risk Çarpanları ---
# GÜNCELLENDİ (6 Kasım 2025): C-grade pozisyon boyutu problemi çözüldü
# v8.4 AGGRESSIVE: Quality multipliers agresifleştirildi
# A: %100 bonus (çok güçlü sinyaller - 2x pozisyon)
# B: %50 bonus (iyi sinyaller - 1.5x pozisyon)
# C: Ceza yok (orta seviye - normal pozisyon)
# D: Veto (zayıf sinyaller - hiç pozisyon açılmaz)
# --- Quality Grade Sistemi (v9.0 PRECISION) ---
# Sadece A ve B grade sinyaller kabul edilir (C ve D reddedilir)
# v9.0 UPDATED: Kaliteli sinyallere DAHA FAZLA risk (A grade için 1.3x bonus)
QUALITY_MULTIPLIERS = {
    'A': 1.25,  # Aynı
    'B': 1.0,
    'C': 0.6,   # Minimal gevşetme paketi: C şimdilik korunuyor (gerekirse 0.7 yapılabilir)
    'D': 0.1
}

# --- Minimal Gevşetme: Fear & Greed eşikleri ---
# LONG için aşırı korku alt limiti (contrarian pozitif), önceki: 25
FNG_LONG_EXTREME_LOW = int(os.getenv("FNG_LONG_EXTREME_LOW", 28))

# --- Secondary R:R Tier (Daha fazla sinyal yakalamak için) ---
# Birincil eşik yine MIN_RR_RATIO (dosyada daha üstte tanımlı)
# İkincil eşik: Daha düşük fakat risk çarpanı düşürülmüş şekilde kabul edilir.
MIN_RR_SECONDARY = float(os.getenv("MIN_RR_SECONDARY", 0.85))  # 0.85 - 0.99 arası kabul
SECONDARY_RISK_MULTIPLIER = float(os.getenv("SECONDARY_RISK_MULTIPLIER", 0.55))  # Birincil riskin %55'i
MIN_RR_SECONDARY_RELAXED = float(os.getenv("MIN_RR_SECONDARY_RELAXED", 0.80))

# C ve D grade için mikro risk kullanımını global aç/kapat
ENABLE_MICRO_RISK_LOW_GRADES = bool(int(os.getenv("ENABLE_MICRO_RISK_LOW_GRADES", 1)))

# --- NaN Toleransı ---
# Belirli sayıda eksik indikatör varsa tamamen reddetme; ceza uygula
NAN_TOLERANCE_ENABLED = bool(int(os.getenv("NAN_TOLERANCE_ENABLED", 1)))
MAX_NAN_INDICATORS_ALLOWED = int(os.getenv("MAX_NAN_INDICATORS_ALLOWED", 2))  # Örn: 2 kolona kadar eksik tolerans
NAN_PENALTY_PER_INDICATOR = float(os.getenv("NAN_PENALTY_PER_INDICATOR", 0.15))  # Kalite skorundan düşülecek
MAX_NAN_INDICATORS_ALLOWED_RELAXED = int(os.getenv("MAX_NAN_INDICATORS_ALLOWED_RELAXED", 3))

# --- Rejim Adaptif Eşikler ---
# Rejime göre efektif RR ve hacim eşiklerini ayarla (ör: BREAKOUT modunda hacim gereksinimi yüksek)
ADAPTIVE_THRESHOLDS_ENABLED = bool(int(os.getenv("ADAPTIVE_THRESHOLDS_ENABLED", 1)))
RR_THRESHOLDS_BY_REGIME = {
    'PULLBACK': float(os.getenv("RR_THRESHOLD_PULLBACK", 1.0)),
    'MEAN_REVERSION': float(os.getenv("RR_THRESHOLD_MEAN_REVERSION", 0.95)),
    'BREAKOUT': float(os.getenv("RR_THRESHOLD_BREAKOUT", 1.05)),
    'STOP': float(os.getenv("RR_THRESHOLD_STOP", 999))  # STOP modunda trade yok
}
VOLUME_RATIO_MIN_BY_REGIME = {
    'PULLBACK': float(os.getenv("VOL_RATIO_MIN_PULLBACK", 1.0)),
    'MEAN_REVERSION': float(os.getenv("VOL_RATIO_MIN_MEAN_REVERSION", 1.1)),
    'BREAKOUT': float(os.getenv("VOL_RATIO_MIN_BREAKOUT", 1.3)),
    'STOP': float(os.getenv("VOL_RATIO_MIN_STOP", 999))
}

# --- Two-Stage Pipeline ---
ENABLE_TWO_STAGE_PIPELINE = bool(int(os.getenv("ENABLE_TWO_STAGE_PIPELINE", 1)))
# Near-full kapsam modunda Stage-1 filtreleri gevşetildi / neredeyse pasif hale getirildi
STAGE1_MIN_VOL_RATIO = float(os.getenv("STAGE1_MIN_VOL_RATIO", 0.95))  # 1.05 → 0.95 (hafifçe altına izin)
STAGE1_MIN_MOMENTUM_SCORE = float(os.getenv("STAGE1_MIN_MOMENTUM_SCORE", 0.0))  # 0.4 → 0.0 (momentum bariyeri kaldırıldı)
STAGE1_MAX_CANDIDATES = int(os.getenv("STAGE1_MAX_CANDIDATES", 400))  # 25 → 1000 (fiilen sınırsız ~ tüm futures)
STAGE1_MIN_VOL_RATIO_RELAXED = float(os.getenv("STAGE1_MIN_VOL_RATIO_RELAXED", 0.92))  # Hafif gevşeme
STAGE1_MAX_CANDIDATES_RELAXED = int(os.getenv("STAGE1_MAX_CANDIDATES_RELAXED", 500))

# --- Breakout Micro-Relaxation Toggles (Safe defaults) ---
BREAKOUT_ADX_DELTA_TOLERANCE = float(os.getenv("BREAKOUT_ADX_DELTA_TOLERANCE", 0.5))  # ADX >= prevADX-0.5 kabul
BREAKOUT_ENABLE_MACD_RELAXED = bool(int(os.getenv("BREAKOUT_ENABLE_MACD_RELAXED", 1)))  # Hafif gevşeme: Açık başla
BREAKOUT_MACD_RELAXED_MIN_INCREASING = int(os.getenv("BREAKOUT_MACD_RELAXED_MIN_INCREASING", 2))
# RSI core/extended bantları (LONG)
BREAKOUT_RSI_CORE_LOW = int(os.getenv("BREAKOUT_RSI_CORE_LOW", 52))
BREAKOUT_RSI_CORE_HIGH = int(os.getenv("BREAKOUT_RSI_CORE_HIGH", 68))
BREAKOUT_RSI_EXT_LOW = int(os.getenv("BREAKOUT_RSI_EXT_LOW", 48))
BREAKOUT_RSI_EXT_HIGH = int(os.getenv("BREAKOUT_RSI_EXT_HIGH", 72))
# RSI core/extended bantları (SHORT)
BREAKOUT_RSI_CORE_SHORT_LOW = int(os.getenv("BREAKOUT_RSI_CORE_SHORT_LOW", 30))
BREAKOUT_RSI_CORE_SHORT_HIGH = int(os.getenv("BREAKOUT_RSI_CORE_SHORT_HIGH", 50))
BREAKOUT_RSI_EXT_SHORT_LOW = int(os.getenv("BREAKOUT_RSI_EXT_SHORT_LOW", 28))
BREAKOUT_RSI_EXT_SHORT_HIGH = int(os.getenv("BREAKOUT_RSI_EXT_SHORT_HIGH", 52))
BREAKOUT_REQUIRE_EXTRA_CONFIRM_OUTSIDE_CORE = bool(int(os.getenv("BREAKOUT_REQUIRE_EXTRA_CONFIRM_OUTSIDE_CORE", 1)))
BREAKOUT_MIN_SQUEEZE_BARS = int(os.getenv("BREAKOUT_MIN_SQUEEZE_BARS", 5))
BREAKOUT_MAX_SQUEEZE_BARS = int(os.getenv("BREAKOUT_MAX_SQUEEZE_BARS", 20))
BREAKOUT_BBW_PERCENTILE_MAX = float(os.getenv("BREAKOUT_BBW_PERCENTILE_MAX", 15.0))
BREAKOUT_VOLUME_RATIO_MIN_RELAXED = float(os.getenv("BREAKOUT_VOLUME_RATIO_MIN_RELAXED", 2.20))  # Minimal gevşetme: 2.25x -> 2.20x (~+10% tolerans)
BREAKOUT_VOLUME_INCREASE_MIN_RELAXED = float(os.getenv("BREAKOUT_VOLUME_INCREASE_MIN_RELAXED", 27.0))  # 30% -> 27%
BREAKOUT_BODY_STRENGTH_MIN_RELAXED = float(os.getenv("BREAKOUT_BODY_STRENGTH_MIN_RELAXED", 54.0))  # 60% -> 54%
BREAKOUT_DISTANCE_MIN_RELAXED = float(os.getenv("BREAKOUT_DISTANCE_MIN_RELAXED", 0.27))  # 0.30% -> 0.27%
ENABLE_BREAKOUT_RELAX_PHASE = bool(int(os.getenv("ENABLE_BREAKOUT_RELAX_PHASE", 1)))

# --- Breakout Extended Sıkışma Kabul (uzun squeeze durumları için) ---
# Sıkışma süresi max_bars'ı aştığında, aşırı düşük BBW percentile ile ek kabul
ENABLE_BREAKOUT_EXTENDED_SQUEEZE = bool(int(os.getenv("ENABLE_BREAKOUT_EXTENDED_SQUEEZE", 1)))
BREAKOUT_EXT_SQUEEZE_MAX_BARS = int(os.getenv("BREAKOUT_EXT_SQUEEZE_MAX_BARS", 30))
BREAKOUT_EXT_BBW_PERCENTILE_MAX = float(os.getenv("BREAKOUT_EXT_BBW_PERCENTILE_MAX", 12.0))  # EXT kabul için daha sıkı BBW (%12)

# Pullback VWAP toleransı (çok hafif gevşetme, ATR yüksekse genişletme kapalı)
PULLBACK_VWAP_TOLERANCE_LONG = float(os.getenv("PULLBACK_VWAP_TOLERANCE_LONG", 0.0115))  # 1.15%
PULLBACK_VWAP_TOLERANCE_SHORT = float(os.getenv("PULLBACK_VWAP_TOLERANCE_SHORT", 0.0115))  # 1.15%
PULLBACK_VWAP_MAX_ATR_PERCENT_FOR_EXTENSION = float(os.getenv("PULLBACK_VWAP_MAX_ATR_PERCENT_FOR_EXTENSION", 4.0))
PULLBACK_VWAP_TOLERANCE_RELAX_FACTOR = float(os.getenv("PULLBACK_VWAP_TOLERANCE_RELAX_FACTOR", 1.08))  # %8 gevşeme
ENABLE_PULLBACK_RELAX_PHASE = bool(int(os.getenv("ENABLE_PULLBACK_RELAX_PHASE", 1)))

# --- Probabilistic Position Sizing ---
ENABLE_PROBABILISTIC_SIZING = bool(int(os.getenv("ENABLE_PROBABILISTIC_SIZING", 1)))
PROB_SIZING_MIN = float(os.getenv("PROB_SIZING_MIN", 0.45))  # Min risk yüzdesi ölçeği
PROB_SIZING_MAX = float(os.getenv("PROB_SIZING_MAX", 1.1))   # Max risk yüzdesi ölçeği (kalite + momentum yüksekse)

# --- Frequency Throttle ---
ENABLE_FREQUENCY_THROTTLE = bool(int(os.getenv("ENABLE_FREQUENCY_THROTTLE", 1)))
THROTTLE_WINDOW_MINUTES = int(os.getenv("THROTTLE_WINDOW_MINUTES", 90))  # Son 90 dakikada...
MAX_NEW_POSITIONS_PER_WINDOW = int(os.getenv("MAX_NEW_POSITIONS_PER_WINDOW", 4))  # ... en fazla 4 yeni pozisyon
THROTTLE_GRADE_PRIORITY = ['A', 'B', 'C']  # D grade zaten düşük öncelik
THROTTLE_WINDOW_MINUTES_RELAXED = int(os.getenv("THROTTLE_WINDOW_MINUTES_RELAXED", 85))
MAX_NEW_POSITIONS_PER_WINDOW_RELAXED = int(os.getenv("MAX_NEW_POSITIONS_PER_WINDOW_RELAXED", 5))

# D: Tamamen iptal (sadece çok kötü sinyaller)

# --- v9.2 SMART SL/TP System Parameters ---
# ATR Bazlı Sistem (SL_TP_METHOD='ATR' veya 'SMART')
ATR_SL_MULTIPLIER = float(os.getenv("ATR_SL_MULTIPLIER", 2.0))  # SL = ATR × 2.0
ATR_TP_MULTIPLIER = float(os.getenv("ATR_TP_MULTIPLIER", 4.0))  # TP = ATR × 4.0 (R:R=2.0)

# Eski değişken isimleri (geriye dönük uyumluluk)
SL_ATR_MULTIPLIER = ATR_SL_MULTIPLIER
TP_ATR_MULTIPLIER = ATR_TP_MULTIPLIER

# Strateji Filtre Ayarları
MAX_ATR_PERCENT = float(os.getenv("MAX_ATR_PERCENT", 5.0)) 
MIN_ATR_PERCENT_BREAKOUT = float(os.getenv("MIN_ATR_PERCENT_BREAKOUT", 0.3))
PULLBACK_VOL_RATIO_LIMIT = float(os.getenv("PULLBACK_VOL_RATIO_LIMIT", 4.0))
BREAKOUT_VOL_RATIO_MIN = float(os.getenv("BREAKOUT_VOL_RATIO_MIN", 1.1))  # v7.0: 1.3 → 1.1 (daha fazla sinyal)

# --- v5.0 ULTRA-OPTIMIZED: Gelişmiş Scalp Strateji Ayarları ---
# v5.0: 15m → 1h (funding maliyeti azaltmak için)
# Funding rate 8 saatte bir → 1h daha az maliyet
SCALP_TIMEFRAME = '1h'  # v5.0: Was '15m'
# Önerdiğin RSI filtreleri (bunları düzelttiğimiz mantıkla kullanacağız)
SCALP_RSI_LONG_ENTRY_MAX = 75.0  # LONG için RSI 75'ten KÜÇÜK olmalı
SCALP_RSI_LONG_ENTRY_MIN = 45.0  # LONG için RSI 45'ten BÜYÜK olmalı
SCALP_RSI_SHORT_ENTRY_MIN = 25.0 # SHORT için RSI 25'ten BÜYÜK olmalı
SCALP_RSI_SHORT_ENTRY_MAX = 55.0 # SHORT için RSI 55'ten KÜÇÜK olmalı
# Hacim artışı (son hacim / ortalama hacim)
SCALP_VOL_RATIO_MIN = float(os.getenv("SCALP_VOL_RATIO_MIN", 1.8))
# Maksimum Volatilite (ATR / Kapanış Fiyatı)
SCALP_MAX_ATR_PERCENT = float(os.getenv("SCALP_MAX_ATR_PERCENT", 2.0)) # Scalp için %2'den fazla olmasın
# Kaç koşul sağlanmalı (örn: 6 koşuldan 5'i, ~%83)
SCALP_CONDITIONS_REQUIRED_COUNT = 5 


# --- Korelasyon Grupları (102 Coin) ---
CORRELATION_GROUPS = {
    # ... (102 coinlik tam listeniz burada, değişiklik yok) ...
    'FETUSDT': 'AI', 'WLDUSDT': 'AI', 'RNDRUSDT': 'AI_DePIN', 'TAOUSDT': 'AI', 'AGIXUSDT': 'AI',
    'OCEANUSDT': 'AI', 'PHBUSDT': 'AI', 'NFPUSDT': 'AI', 'FILUSDT': 'DePIN_STORAGE', 
    'ARUSDT': 'DePIN_STORAGE', 'HNTUSDT': 'DePIN_IOT', 'LPTUSDT': 'DePIN_VIDEO', 'THETAUSDT': 'DePIN_VIDEO',
    'IOTXUSDT': 'DePIN_IOT', 'JASMYUSDT': 'IOT', 'ONDOUSDT': 'RWA', 'POLYXUSDT': 'RWA',
    'AXLUSDT': 'INFRA_RWA', 'MKRUSDT': 'RWA_STABLE', 'AXSUSDT': 'GameFi', 'IMXUSDT': 'GameFi_L2',
    'RONINUSDT': 'GameFi', 'SANDUSDT': 'Metaverse', 'MANAUSDT': 'Metaverse', 'GALAUSDT': 'GameFi',
    'ALICEUSDT': 'GameFi', 'ENJUSDT': 'GameFi', 'YGGUSDT': 'GameFi', 'BEAMXUSDT': 'GameFi',
    'ACEUSDT': 'GameFi', 'PIXELUSDT': 'GameFi', 'DOGEUSDT': 'MEME', 'SHIBUSDT': 'MEME',
    'PEPEUSDT': 'MEME', 'FLOKIUSDT': 'MEME', 'BONKUSDT': 'MEME', 'WIFUSDT': 'MEME',
    'ORDIUSDT': 'BRC20', 'SATSUSDT': 'BRC20', 'MEMEUSDT': 'MEME', 'MOGUSDT': 'MEME',
    'BTCUSDT': 'MAJOR_L1', 'ETHUSDT': 'MAJOR_L1', 'SOLUSDT': 'L1', 'BNBUSDT': 'EXCHANGE_L1',
    'AVAXUSDT': 'L1', 'ADAUSDT': 'L1', 'DOTUSDT': 'L0', 'ATOMUSDT': 'L0', 'NEARUSDT': 'L1',
    'KSMUSDT': 'L0', 'FTMUSDT': 'L1', 'EGLDUSDT': 'L1', 'ALGOUSDT': 'L1', 'KASUSDT': 'L1',
    'INJUSDT': 'L1_DeFi', 'SEIUSDT': 'L1_NEW', 'SUIUSDT': 'L1_NEW', 'APTUSDT': 'L1_NEW',
    'TIAUSDT': 'MODULAR', 'MATICUSDT': 'L2', 'ARBUSDT': 'L2', 'OPUSDT': 'L2', 'STRKUSDT': 'L2',
    'MNTUSDT': 'L2', 'METISUSDT': 'L2', 'SKLUSDT': 'L2', 'LINKUSDT': 'ORACLE', 'UNIUSDT': 'DEX',
    'AAVEUSDT': 'LENDING', 'SNXUSDT': 'SYNTHETICS', 'RUNEUSDT': 'DEX', 'DYDXUSDT': 'DEX',
    'GMXUSDT': 'DEX', 'CRVUSDT': 'DEX', '1INCHUSDT': 'DEX_AGG', 'SUSHIUSDT': 'DEX',
    'COMPUSDT': 'LENDING', 'LDOUSDT': 'LIQUID_STAKING', 'RPLUSDT': 'LIQUID_STAKING',
    'PYTHUSDT': 'ORACLE', 'TRBUSDT': 'ORACLE', 'BANDUSDT': 'ORACLE', 'YFIUSDT': 'YIELD',
    'ENAUSDT': 'SYNTHETIC_USD', 'PENDLEUSDT': 'YIELD', 'RDNTUSDT': 'LENDING',
    'JUPUSDT': 'DEX_AGG', 'JTOUSDT': 'LIQUID_STAKING', 'ICPUSDT': 'WEB3_INFRA',
    'GRTUSDT': 'INFRA_AI', 'BATUSDT': 'WEB3_INFRA', 'CHZUSDT': 'FAN_TOKEN', 'CFXUSDT': 'L1_POW',
    'XRPUSDT': 'LEGACY_PAYMENT', 'LTCUSDT': 'LEGACY_POW', 'BCHUSDT': 'LEGACY_POW',
    'ETCUSDT': 'LEGACY_POW', 'TRXUSDT': 'L1_OLD', 'EOSUSDT': 'L1_OLD', 'XTZUSDT': 'L1_OLD',
    'XLMUSDT': 'L1_OLD', 'ZECUSDT': 'PRIVACY', 'DASHUSDT': 'PRIVACY', 'ZENUSDT': 'PRIVACY',
    'NEOUSDT': 'L1_OLD', 'QTUMUSDT': 'L1_OLD', 'ZROUSDT': 'L0', 'ZKUSDT': 'L2_ZK',
    'LISTAUSDT': 'DeFi', 'NOTUSDT': 'GameFi_TAP'
}

# --- Duygu Analizi Ayarları ---
# ... (Bu bölümün tamamı aynı kalıyor, değişiklik yok) ...
SENTIMENT_RSS_FEEDS = [
    "https://cointelegraph.com/rss", "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptonews.com/news/feed/", "https://bitcoinmagazine.com/.rss/full/",
]
SENTIMENT_SYMBOL_KEYWORDS = {
    'btc': ['bitcoin', 'btc'], 'eth': ['ethereum', 'eth'], 'bnb': ['binance coin', 'bnb', 'bsc'],
    'sol': ['solana', 'sol'], 'ada': ['cardano', 'ada'], 'xrp': ['ripple', 'xrp'],
    'doge': ['dogecoin', 'doge'], 'shib': ['shiba inu', 'shib'], 'pepe': ['pepe'],
    'wld': ['worldcoin', 'wld'], 'fet': ['fetch.ai', 'fetch', 'fet'],
    'rndr': ['render', 'rndr'], 'tao': ['bittensor', 'tao'], 'agix': ['singularitynet', 'agix'],
    'ocean': ['ocean protocol', 'ocean'], 'phb': ['phoenix', 'phb'], 'nfp': ['nfprompt', 'nfp'],
    'fil': ['filecoin', 'fil'], 'ar': ['arweave', 'ar'], 'hnt': ['helium', 'hnt'],
    'lpt': ['livepeer', 'lpt'], 'theta': ['theta'], 'iotx': ['iotex', 'iotx'], 'jasmy': ['jasmy'],
    'ondo': ['ondo finance', 'ondo'], 'polyx': ['polymesh', 'polyx'], 'axl': ['axelar', 'axl'],
    'mkr': ['maker', 'mkr'], 'axs': ['axie infinity', 'axs'], 'imx': ['immutable', 'imx'],
    'ronin': ['ronin', 'ron'], 'sand': ['the sandbox', 'sand'], 'mana': ['decentraland', 'mana'],
    'gala': ['gala games', 'gala'], 'alice': ['my neighbor alice', 'alice'], 'enj': ['enjin coin', 'enj'],
    'ygg': ['yield guild games', 'ygg'], 'beamx': ['beam', 'beamx'], 'ace': ['fusionist', 'ace'],
    'pixel': ['pixel'], 'floki': ['floki'], 'bonk': ['bonk'], 'wif': ['dogwifhat', 'wif'],
    'ordi': ['ordi', 'ordinals'], 'sats': ['sats'], 'meme': ['memecoin', 'meme'], 'mog': ['mog coin', 'mog'],
    'dot': ['polkadot', 'dot'], 'atom': ['cosmos', 'atom'], 'near': ['near protocol', 'near'],
    'ksm': ['kusama', 'ksm'], 'ftm': ['fantom', 'ftm'], 'egld': ['multiversx', 'egld'],
    'algo': ['algorand', 'algo'], 'kas': ['kaspa', 'kas'], 'inj': ['injective', 'inj'],
    'sei': ['sei'], 'sui': ['sui'], 'apt': ['aptos', 'apt'], 'tia': ['celestia', 'tia'],
    'matic': ['polygon', 'matic'], 'arb': ['arbitrum', 'arb'], 'op': ['optimism', 'op'],
    'strk': ['starknet', 'strk'], 'mnt': ['mantle', 'mnt'], 'metis': ['metis'], 'skl': ['skale', 'skl'],
    'link': ['chainlink', 'link'], 'uni': ['uniswap', 'uni'], 'aave': ['aave'], 'snx': ['synthetix', 'snx'],
    'rune': ['thorchain', 'rune'], 'dydx': ['dydx'], 'gmx': ['gmx'], 'crv': ['curve', 'crv'],
    '1inch': ['1inch'], 'sushi': ['sushi'], 'comp': ['compound', 'comp'], 'ldo': ['lido', 'ldo'],
    'rpl': ['rocket pool', 'rpl'], 'pyth': ['pyth network', 'pyth'], 'trb': ['tellor', 'trb'],
    'band': ['band protocol', 'band'], 'yfi': ['yearn finance', 'yfi'], 'ena': ['ethena', 'ena'],
    'pendle': ['pendle'], 'rdnt': ['radiant capital', 'rdnt'], 'jup': ['jupiter', 'jup'], 'jto': ['jito', 'jto'],
    'icp': ['internet computer', 'icp'], 'grt': ['the graph', 'grt'], 'bat': ['basic attention token', 'bat'],
    'chz': ['chiliz', 'chz'], 'cfx': ['conflux', 'cfx'], 'ltc': ['litecoin', 'ltc'], 'bch': ['bitcoin cash', 'bch'],
    'etc': ['ethereum classic', 'etc'], 'trx': ['tron', 'trx'], 'eos': ['eos'], 'xtz': ['tezos', 'xtz'],
    'xlm': ['stellar', 'xlm'], 'zec': ['zcash', 'zec'], 'dash': ['dash'], 'zen': ['horizen', 'zen'],
    'neo': ['neo'], 'qtum': ['qtum'], 'zro': ['layerzero', 'zro'], 'zk': ['zksync', 'zk'],
    'lista': ['lista dao', 'lista'], 'not': ['notcoin', 'not']
}
SENTIMENT_NEWS_LOOKBACK_HOURS = int(os.getenv("SENTIMENT_NEWS_LOOKBACK_HOURS", 24))
SENTIMENT_FNG_UPDATE_INTERVAL_SECONDS = int(os.getenv("SENTIMENT_FNG_UPDATE_INTERVAL_SECONDS", 3600))
SENTIMENT_RSS_UPDATE_INTERVAL_SECONDS = int(os.getenv("SENTIMENT_RSS_UPDATE_INTERVAL_SECONDS", 600)) # 10dk
MAX_HEADLINES_IN_CACHE = int(os.getenv("MAX_HEADLINES_IN_CACHE", 1000))
SENTIMENT_REDDIT_SUBREDDITS = ["CryptoCurrency", "Bitcoin", "ethereum", "altcoin", "CryptoMarkets"]
REDDIT_POST_LIMIT_PER_SUB = 25
REDDIT_MIN_POST_SCORE = 1
SENTIMENT_REDDIT_UPDATE_INTERVAL_SECONDS = int(os.getenv("SENTIMENT_REDDIT_UPDATE_INTERVAL_SECONDS", 600)) # 10dk
MAX_REDDIT_POSTS_IN_CACHE = 500
SENTIMENT_GOOGLE_TRENDS_KEYWORDS = ["Bitcoin", "Ethereum", "crypto", "Solana", "BNB"]
SENTIMENT_TRENDS_UPDATE_INTERVAL_SECONDS = int(os.getenv("SENTIMENT_TRENDS_UPDATE_INTERVAL_SECONDS", 3600 * 4))

# --- Bildirim Ayarları ---
# --- Bildirim Ayarları ---
# Ortam değişkeni ile açıkça kontrol edilebilir hale getirildi (.env.example'a eklendi)
NOTIFY_ON_NO_SIGNAL = os.getenv("NOTIFY_ON_NO_SIGNAL", "True").lower() == 'true'

# --- Trade Manager Ayarları ---
TRADE_MANAGER_SLEEP_SECONDS = int(os.getenv("TRADE_MANAGER_SLEEP_SECONDS", 3)) # 3sn

# --- Strateji Ayarları ---
# GÜNCELLENDİ: 'MOMENTUM_SCALP' -> 'ADVANCED_SCALP' olarak değiştirildi
# Gerekli göstergeler eklendi (ema8, ema21, hacim, atr)
STRATEGY_REQUIRED_INDICATORS = {
    'PULLBACK': {
        '1d': ['adx14', 'bbw', 'close', 'ema50', 'sma200', 'supertrend_direction'], # v4.0: Added Supertrend
        '4h': ['close', 'ema50', 'sma200', 'supertrend_direction'], # v4.0: Added Supertrend
        '1h': ['close', 'rsi14', 'macd_hist', 'atr14', 'volume', 'volume_sma20', 'vwap', 'supertrend_direction'] # v4.0: Added VWAP + Supertrend
    },
    'MEAN_REVERSION': {
        '1d': ['adx14', 'bbw'],
        '4h': ['close', 'bb_upper', 'bb_lower', 'rsi14', 'atr14', 'vwap'], # v4.0: Added VWAP
        '1h': ['close', 'vwap', 'rsi14'] # v4.0: Added 1H requirements for VWAP reversion check
    },
    'BREAKOUT': {
        '1d': ['adx14', 'bbw'],
        '1h': ['close', 'bb_upper', 'bb_lower', 'bbw', 'volume', 'atr14', 'volume_sma20', 'supertrend_direction'] # v4.0: Added Supertrend
    },
    # v4.0 Enhanced: Gelişmiş Scalping Stratejisi
    'ADVANCED_SCALP': {
        '1d': ['adx14', 'bbw'], # Rejim belirleme için 1D hala gerekli
        SCALP_TIMEFRAME: ['close', 'ema8', 'ema21', 'rsi14', 'macd', 'macd_signal', 'macd_hist', 'volume', 'volume_sma20', 'atr14', 'vwap', 'supertrend_direction', 'stoch_rsi_signal'] # v4.0: Added VWAP, Supertrend, Stoch RSI
    },
    'STOP': {}
}

# ============================================================
# ADVANCED RISK MANAGEMENT SETTINGS
# ============================================================

# Dinamik risk limitleri
MAX_POSITION_RISK = 4.0  # Maksimum risk yüzdesi (yüksek kaliteli sinyaller için)
MIN_POSITION_RISK = 0.5  # Minimum risk yüzdesi (düşük kaliteli sinyaller için)

# Kelly Criterion ayarları
USE_FRACTIONAL_KELLY = True  # Fractional Kelly kullan (güvenli)
KELLY_FRACTION = 0.5  # Kelly sonucunu bu oranla çarp (%50 Kelly) - AGGRESSIVE
MIN_KELLY_CONFIDENCE_THRESHOLD = 'LOW'  # Minimum kabul edilebilir Kelly güven seviyesi

# Volatilite bazlı ayarlamalar
VOLATILITY_ADJUSTMENT_ENABLED = True  # Volatiliteye göre risk ayarlama
HIGH_VOLATILITY_THRESHOLD = 0.6  # Bu değerin üstü "yüksek volatilite"
LOW_VOLATILITY_THRESHOLD = 0.3  # Bu değerin altı "düşük volatilite"

# Sentiment alignment ayarları
SENTIMENT_ALIGNMENT_WEIGHT = 1.0  # Sentiment uyumunun risk hesabındaki ağırlığı
NEGATIVE_SENTIMENT_PENALTY = 0.7  # Ters sentiment durumunda risk çarpanı

# Korelasyon grubu optimizasyonu
GROUP_EXPOSURE_WEIGHT = 1.0  # Grup doluluk oranının risk hesabındaki ağırlığı
DIVERSIFICATION_BONUS = 1.1  # Boş gruplara verilen risk çarpan bonusu

# --- v4.0 Enhanced: Otomatik Korelasyon Grubu Ataması ---
def auto_assign_correlation_group(symbol: str) -> str:
    """
    AUTO_FUTURES modunda, bilinmeyen coinler için otomatik grup ataması yapar.
    Coin adına göre kategori tahmin eder.
    
    Args:
        symbol: BTCUSDT, PEPE1000USDT gibi
    
    Returns:
        str: Tahmin edilen grup adı (örn: 'AI', 'MEME', 'L1', 'OTHER')
    """
    # Önce manuel CORRELATION_GROUPS'ta var mı kontrol et
    if symbol in CORRELATION_GROUPS:
        return CORRELATION_GROUPS[symbol]
    
    # USDT'yi temizle, coin adını al
    base = symbol.replace('USDT', '').replace('1000', '').lower()
    
    # Keyword-based classification
    ai_keywords = ['ai', 'fet', 'wld', 'agix', 'ocean', 'rndr', 'phb', 'nfp', 'grt', 'tao']
    meme_keywords = ['doge', 'shib', 'pepe', 'floki', 'bonk', 'wif', 'mog', 'meme', 'elon', 'wojak', 'turbo', 'aidoge']
    gamefi_keywords = ['axs', 'sand', 'mana', 'gala', 'enj', 'ygg', 'alice', 'beam', 'ace', 'pixel', 'imx', 'magic', 'ilv', 'star']
    defi_keywords = ['uni', 'aave', 'crv', 'snx', 'comp', 'bal', 'yfi', 'mkr', 'sushi', 'cake', 'joe', 'gmx', 'dydx', 'inj']
    l1_keywords = ['sol', 'ada', 'dot', 'avax', 'atom', 'near', 'ftm', 'algo', 'egld', 'kas', 'sui', 'apt', 'sei', 'aptos']
    l2_keywords = ['arb', 'op', 'matic', 'polygon', 'strk', 'stark', 'mnt', 'mantle', 'metis', 'skl', 'zk', 'imx']
    storage_keywords = ['fil', 'ar', 'storj', 'sia']
    oracle_keywords = ['link', 'trb', 'band', 'pyth']
    
    # Kategorileri kontrol et
    for keyword in ai_keywords:
        if keyword in base:
            return 'AI'
    
    for keyword in meme_keywords:
        if keyword in base:
            return 'MEME'
    
    for keyword in gamefi_keywords:
        if keyword in base:
            return 'GameFi'
    
    for keyword in defi_keywords:
        if keyword in base:
            return 'DeFi'
    
    for keyword in l2_keywords:
        if keyword in base:
            return 'L2'
    
    for keyword in l1_keywords:
        if keyword in base:
            return 'L1'
    
    for keyword in storage_keywords:
        if keyword in base:
            return 'DePIN_STORAGE'
    
    for keyword in oracle_keywords:
        if keyword in base:
            return 'ORACLE'
    
    # Büyük coinler için özel kontrol
    if base in ['btc', 'bitcoin']:
        return 'MAJOR_L1'
    elif base in ['eth', 'ethereum']:
        return 'MAJOR_L1'
    elif base in ['bnb', 'binance']:
        return 'EXCHANGE_L1'
    
    # Hiçbir kategori uymazsa
    return 'OTHER'


# ═══════════════════════════════════════════════════════════════════════
# v10.7.1 FIXED MARGIN SYSTEM - SABİT MARGIN SİSTEMİ
# ═══════════════════════════════════════════════════════════════════════

# Her pozisyon için sabit değerler
FIXED_MARGIN_USD = 10.0        # Her pozisyon 10 USD margin
FIXED_MARGIN_TP_RATIO = 1.40   # TP hedef değeri: 10 × 1.40 = 14 USD (margin + %40 kar)
FIXED_MARGIN_SL_RATIO = 0.90   # SL hedef değeri: 10 × 0.90 = 9 USD (margin - %10 zarar)

# Hesaplanan değerler
FIXED_TARGET_TP_VALUE = FIXED_MARGIN_USD * FIXED_MARGIN_TP_RATIO  # 14 USD (10 + 4)
FIXED_TARGET_SL_VALUE = FIXED_MARGIN_USD * FIXED_MARGIN_SL_RATIO  # 9 USD (10 - 1)
FIXED_TP_PROFIT = FIXED_TARGET_TP_VALUE - FIXED_MARGIN_USD        # +4 USD (%40 kar)
FIXED_SL_LOSS = FIXED_MARGIN_USD - FIXED_TARGET_SL_VALUE          # +1 USD (%10 zarar)

# ═══════════════════════════════════════════════════════════════════════
# v11.0 HTF-LTF STRATEGY SETTINGS (High Timeframe Filter + Low Timeframe Trigger)
# ═══════════════════════════════════════════════════════════════════════

# --- Timeframe Settings ---
HTF_TIMEFRAME = '1h'       # High Timeframe (Ana trend filtresi)
LTF_TIMEFRAME = '15m'      # Low Timeframe (Giriş tetikleyicisi)

# --- HTF (1H) Indicator Settings ---
HTF_EMA_PERIOD = 50        # 1H EMA periyodu (trend filtresi)
HTF_RSI_PERIOD = 14        # 1H RSI periyodu
HTF_MACD_FAST = 12         # 1H MACD fast period
HTF_MACD_SLOW = 26         # 1H MACD slow period
HTF_MACD_SIGNAL = 9        # 1H MACD signal period

# --- LTF (15M) Indicator Settings ---
LTF_EMA_SHORT = 5          # 15M kısa EMA (trigger)
LTF_EMA_LONG = 20          # 15M uzun EMA (trigger)
LTF_RSI_PERIOD = 14        # 15M RSI periyodu
LTF_MACD_FAST = 12         # 15M MACD fast
LTF_MACD_SLOW = 26         # 15M MACD slow
LTF_MACD_SIGNAL = 9        # 15M MACD signal

# --- LTF (15M) Signal Thresholds ---
LTF_RSI_BULL_MIN = 45      # LONG için minimum RSI (50 → 45 basitleştirme)
LTF_RSI_BULL_MAX = 85      # LONG için maximum RSI (75 → 85 daha esnek)
LTF_RSI_BEAR_MIN = 15      # SHORT için minimum RSI (25 → 15 daha esnek)
LTF_RSI_BEAR_MAX = 55      # SHORT için maximum RSI (50 → 55 basitleştirme)

# --- Risk Filters ---
SCALP_MAX_ATR_PERCENT = 2.0      # Maksimum ATR % (volatilite filtresi)
VOLUME_CONFIRMATION_REQUIRED = True  # Hacim onayı gerekli mi?
VOLUME_SMA_PERIOD = 20           # Hacim ortalaması periyodu

# --- Data Fetch Settings ---
HTF_CANDLE_LIMIT = 100     # 1H için çekilecek mum sayısı (EMA50 için yeterli)
LTF_CANDLE_LIMIT = 100     # 15M için çekilecek mum sayısı

# --- Backward Compatibility (Eski sistemle uyumluluk) ---
PRIMARY_TIMEFRAME = LTF_TIMEFRAME      # '15m'
SECONDARY_TIMEFRAME = '30m'            # Artık kullanılmıyor
HYBRID_TIMEFRAME = PRIMARY_TIMEFRAME
HYBRID_EMA_SHORT = LTF_EMA_SHORT       # 5
HYBRID_EMA_LONG = LTF_EMA_LONG         # 20
HYBRID_WARMUP_CANDLES = 50

# --- 1H Confirmation Layer Settings ---
HYBRID_CONFIRMATION_TF = '1h'  # Confirmation için timeframe
HYBRID_CONFIRMATION_LIMIT = 50  # 1H için çekilecek mum sayısı

# Scoring weights (toplam 100 puan)
HYBRID_TREND_WEIGHT = 30    # EMA trend alignment
HYBRID_STRENGTH_WEIGHT = 25  # ADX strength
HYBRID_MOMENTUM_WEIGHT = 25  # MACD momentum
HYBRID_RSI_WEIGHT = 20       # RSI levels

# --- Smart Execution Thresholds ---
HYBRID_MARKET_THRESHOLD = 70   # Score ≥70 → MARKET order
HYBRID_PARTIAL_THRESHOLD = 50  # Score 50-69 → PARTIAL (50% market + 50% limit)
# Score <50 → LIMIT order

# --- Order Execution Settings ---
HYBRID_LIMIT_PRICE_OFFSET = 0.001  # 0.1% fiyat offset (limit emirler için)
HYBRID_PARTIAL_MARKET_RATIO = 0.5  # Partial'da market kısmının oranı (50%)

# --- Order Tracker Settings ---
HYBRID_ORDER_TIMEOUT = 300  # Limit emir timeout süresi (saniye) - 5 dakika
HYBRID_ORDER_CHECK_INTERVAL = 10  # Order status kontrolü (saniye)

# --- Risk Management (v10.6 için) ---
# Not: Mevcut MAX_OPEN_POSITIONS, MAX_POSITIONS_PER_SYMBOL ayarları kullanılacak
# v10.6 pozisyonları da aynı limitlere tabi olacak

# ═══════════════════════════════════════════════════════════════════════
# v10.9 HYBRID SYSTEM - Scheduled Scan + WebSocket Monitoring (OPTIMIZED)
# ═══════════════════════════════════════════════════════════════════════

# --- Scheduled Full Market Scan (her 5 dakika - AGRESIF TEST) ---
ADAPTIVE_SCAN_INTERVAL = int(os.getenv("ADAPTIVE_SCAN_INTERVAL", 300))  # 5 dakika (daha sık scan)

# --- Proximity Detection for WebSocket Monitoring (GENİŞLETİLMİŞ) ---
PROXIMITY_THRESHOLD_PERCENT = float(os.getenv("PROXIMITY_THRESHOLD_PERCENT", 2.0))  # EMA5-EMA20 arası %2 (daha fazla coin)
MAX_WEBSOCKET_SUBSCRIPTIONS = int(os.getenv("MAX_WEBSOCKET_SUBSCRIPTIONS", 50))  # Max 50 coin WebSocket'te
WEBSOCKET_CHECK_INTERVAL = int(os.getenv("WEBSOCKET_CHECK_INTERVAL", 5))  # 5 saniyede bir proximity check

# Backward compatibility aliases for v10.6/v10.7
ADAPTIVE_PROXIMITY_THRESHOLD = PROXIMITY_THRESHOLD_PERCENT  # Old name
ADAPTIVE_MAX_WATCHLIST_SIZE = MAX_WEBSOCKET_SUBSCRIPTIONS  # Old name
ADAPTIVE_MIN_WATCHLIST_SIZE = 5  # Min watchlist size

# Instant crossover tespit edildiğinde direkt işlem açılsın mı?
INSTANT_CROSSOVER_TRADE = os.getenv("INSTANT_CROSSOVER_TRADE", "True").lower() == "true"
ADAPTIVE_INSTANT_TRADE = INSTANT_CROSSOVER_TRADE  # Old name

# 🚀 v10.8: Multi-Timeframe Confidence System (DEPRECATED - Use Confluence Score)
MIN_CONFIDENCE_SCORE = float(os.getenv("MIN_CONFIDENCE_SCORE", 0.3))  # Legacy system, not used in v11.4+

# 🎯 v11.4: CONFLUENCE-BASED TP/SL SYSTEM
# Score-based TP/SL: Kaliteli sinyaller daha geniş targets alır
USE_CONFLUENCE_BASED_TP_SL = os.getenv("USE_CONFLUENCE_BASED_TP_SL", "True").lower() == "true"

# Grade A (8.0-10.0): Yüksek kaliteli sinyaller - Geniş targets
CONFLUENCE_A_SL_USD = float(os.getenv("CONFLUENCE_A_SL_USD", 2.5))  # $2.5 risk
CONFLUENCE_A_TP_USD = float(os.getenv("CONFLUENCE_A_TP_USD", 6.0))  # $6.0 kar (R:R = 2.4)

# Grade B (6.5-7.9): Orta kaliteli sinyaller - Dengeli targets
CONFLUENCE_B_SL_USD = float(os.getenv("CONFLUENCE_B_SL_USD", 2.0))  # $2.0 risk
CONFLUENCE_B_TP_USD = float(os.getenv("CONFLUENCE_B_TP_USD", 4.0))  # $4.0 kar (R:R = 2.0)

# Grade C (5.0-6.4): Düşük kaliteli sinyaller - Muhafazakar targets
CONFLUENCE_C_SL_USD = float(os.getenv("CONFLUENCE_C_SL_USD", 1.5))  # $1.5 risk
CONFLUENCE_C_TP_USD = float(os.getenv("CONFLUENCE_C_TP_USD", 3.0))  # $3.0 kar (R:R = 2.0)

# 🆕 v10.10: ATR-Based TP/SL System (FALLBACK ONLY)
USE_ATR_BASED_TP_SL = os.getenv("USE_ATR_BASED_TP_SL", "False").lower() == "true"  # False = Use Confluence
ATR_PERIOD = int(os.getenv("ATR_PERIOD", 14))  # ATR hesaplama periyodu
ATR_TIMEFRAME = os.getenv("ATR_TIMEFRAME", "15m")  # ATR için timeframe

# ATR Multipliers (Fallback için korundu)
ATR_TP_MULTIPLIER = float(os.getenv("ATR_TP_MULTIPLIER", 4.0))  # TP = ATR × 4.0 (was 2.0 in v11.1)
ATR_SL_MULTIPLIER = float(os.getenv("ATR_SL_MULTIPLIER", 2.0))  # SL = ATR × 2.0 (was 1.0 in v11.1)

# ATR Risk Management (Legacy - Confluence sisteminde kullanılmıyor)
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", 1.5))  # Minimum R:R 1.5:1
MAX_SL_USD = float(os.getenv("MAX_SL_USD", 10.0))  # Esnetildi: Score zaten filtre ediyor
MIN_TP_USD = float(os.getenv("MIN_TP_USD", 1.0))  # Esnetildi
MIN_SL_USD = float(os.getenv("MIN_SL_USD", 0.5))  # Sadece noise koruması

# A/B Testing: KAPALI - %100 Confluence Kullanılıyor
AB_TEST_MODE = os.getenv("AB_TEST_MODE", "False").lower() == "true"  # False = Pure Confluence
AB_TEST_RATIO = float(os.getenv("AB_TEST_RATIO", 1.0))  # 1.0 = %100 Confluence

# Candle freshness thresholds (saniye)
CANDLE_FRESHNESS_THRESHOLD = {
    '15m': 120,  # 2 dakika - 15m mum kapanışından 2dk içinde giriş yap
    '30m': 300   # 5 dakika - 30m mum kapanışından 5dk içinde doğrula
}

# ═══════════════════════════════════════════════════════════════════════


print("Config: Tüm yapılandırma değişkenleri yüklendi.")

# ⚠️ GERÇEK TRADING AKTİFLEŞTİRME
# İstek üzerine varsayılanı True yapıldı; yine de .env ile güvenli şekilde yönetebilirsiniz.
ENABLE_REAL_TRADING = os.getenv('ENABLE_REAL_TRADING', 'True').lower() == 'true'

# Executor başlatılamazsa simülasyona düşülsün mü? (Canlı ticarette önerilmez)
ALLOW_SIMULATION_FALLBACK = os.getenv('ALLOW_SIMULATION_FALLBACK', 'False').lower() == 'true'

# Gerçek trading için minimum test gereksinimleri
# GÜNCELLENDİ (8 Kasım 2025): Print kullan (logger henüz import edilmedi)
if ENABLE_REAL_TRADING:
    print("=" * 60)
    print("🚨 GERÇEK TRADING MODU AKTİF!")
    print("Binance hesabınızda GERÇEK emirler açılacak!")
    print("=" * 60)
    
    # Test kontrolü
    assert BINANCE_API_KEY and BINANCE_SECRET_KEY, "API anahtarları eksik!"
    
    # Testnet kontrolü (opsiyonel)
    BINANCE_TESTNET_CHECK = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
    if BINANCE_TESTNET_CHECK:
        print("⚠️ TESTNET modu aktif - Gerçek para kullanılmayacak")
else:
    print("ℹ️ Simülasyon modu - ENABLE_REAL_TRADING=False")

# ═══════════════════════════════════════════════════════════
# FIBONACCI BOT CONFIGURATION (Spot Market Dip Buying)
# ═══════════════════════════════════════════════════════════

FIBONACCI_MAX_COINS = int(os.getenv("FIBONACCI_MAX_COINS", 2))
FIBONACCI_BUDGET_PER_COIN = float(os.getenv("FIBONACCI_BUDGET_PER_COIN", 100.0))
FIBONACCI_TOTAL_BUDGET = float(os.getenv("FIBONACCI_TOTAL_BUDGET", 200.0))
FIBONACCI_SCAN_INTERVAL_MINUTES = int(os.getenv("FIBONACCI_SCAN_INTERVAL_MINUTES", 5))
FIBONACCI_DROP_THRESHOLD = float(os.getenv("FIBONACCI_DROP_THRESHOLD", -8.0))
FIBONACCI_MIN_VOLUME = float(os.getenv("FIBONACCI_MIN_VOLUME", 1000000))
FIBONACCI_LOOKBACK_DAYS = int(os.getenv("FIBONACCI_LOOKBACK_DAYS", 90))
FIBONACCI_ADX_THRESHOLD = float(os.getenv("FIBONACCI_ADX_THRESHOLD", 40.0))

# Fibonacci bütçe dağılımı (sabit - kod içinde kullanılıyor)
FIBONACCI_BUDGET_DISTRIBUTION = {
    0.618: 0.20,  # %20 bütçe
    0.786: 0.35,  # %35 bütçe
    1.000: 0.45   # %45 bütçe
}