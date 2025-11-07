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
BOT_VERSION = "5.0-AutoPilot" # GÜNCELLENDİ: v5.0 Oto-Pilot Trading Engine

# --- API Anahtarları ---
# Testnet moduna göre key seçimi
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "True").lower() == "true"

if BINANCE_TESTNET:
    # Testnet mode - testnet keys kullan
    BINANCE_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "YOUR_TESTNET_API_KEY_HERE")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_TESTNET_SECRET_KEY", "YOUR_TESTNET_SECRET_KEY_HERE")
else:
    # Live mode - real keys kullan
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "YOUR_BINANCE_API_KEY_PLACEHOLDER")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "YOUR_BINANCE_SECRET_KEY_PLACEHOLDER")

# --- Binance Futures Trading Ayarları (v5.0) ---
FUTURES_LEVERAGE = int(os.getenv("FUTURES_LEVERAGE", 10))  # Sabit kaldıraç (tüm pozisyonlar)
FUTURES_MARGIN_TYPE = os.getenv("FUTURES_MARGIN_TYPE", "ISOLATED")  # ISOLATED veya CROSS
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", None)
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", None)
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", None)
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", None)
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "ChimeraBotSentiment/0.1 (by u/UnknownUser)")

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
MAX_COINS_TO_SCAN = int(os.getenv("MAX_COINS_TO_SCAN", 300))  # v4.0: 110 → 300 (Futures için)
SCAN_DELAY_SECONDS = float(os.getenv("SCAN_DELAY_SECONDS", 0.5))

# --- v4.0 Enhanced: Dinamik Coin Listesi ---
# 'MANUAL': CORRELATION_GROUPS içindeki coinleri kullan (106 coin)
# 'AUTO_FUTURES': Binance Futures'tan tüm USDT çiftlerini otomatik çek (~300+ coin)
COIN_LIST_MODE = os.getenv("COIN_LIST_MODE", "AUTO_FUTURES")  # v4.0: Otomatik mod varsayılan
AUTO_FUTURES_UPDATE_HOURS = int(os.getenv("AUTO_FUTURES_UPDATE_HOURS", 24))  # Liste güncelleme sıklığı
# ------------------------------------------------------

# --- YENİ EKLENDİ: Hızlı Ön Filtreleme Ayarları (v4.0 Enhancement) ---
# Taramaya dahil etmek için minimum 24 saatlik USDT hacmi
# v5.0 ULTRA-OPTIMIZED: Ön filtreleme sıkılaştırıldı
PRE_SCREEN_MIN_VOLUME_USD = float(os.getenv("PRE_SCREEN_MIN_VOLUME_USD", 5_000_000)) # 5M → Likidite garantisi
# Taramaya dahil etmek için minimum 24 saatlik mutlak fiyat değişimi yüzdesi
PRE_SCREEN_MIN_PRICE_CHANGE_PERCENT = float(os.getenv("PRE_SCREEN_MIN_PRICE_CHANGE_PERCENT", 2.5)) # %2.5 → Anlamlı hareket
# Filtreleme modu: 'AND' (hem hacim hem değişim) veya 'OR' (en az biri)
PRE_SCREEN_FILTER_MODE = os.getenv("PRE_SCREEN_FILTER_MODE", "AND")  # v5.0: AND modu (ikisi de gerekli)
# -----------------------------------------------------------

# --- Portföy ve Risk Ayarları ---
# v6.0 FIXED RISK SYSTEM: Sabit risk yaklaşımı (7 Kasım 2025)
USE_REAL_BALANCE = os.getenv("USE_REAL_BALANCE", "True").lower() == "true"  # Gerçek bakiyeyi Binance'den al
VIRTUAL_PORTFOLIO_USD = float(os.getenv("VIRTUAL_PORTFOLIO_USD", 200.0))  # Sanal portföy (USE_REAL_BALANCE=False ise)

# YENİ: Sabit Risk Sistemi
USE_FIXED_RISK_USD = os.getenv("USE_FIXED_RISK_USD", "True").lower() == "true"  # Sabit risk modu
FIXED_RISK_USD = float(os.getenv("FIXED_RISK_USD", 5.0))  # Her işlemde maksimum $5 risk
MAX_POSITION_VALUE_USD = float(os.getenv("MAX_POSITION_VALUE_USD", 300.0))  # Pozisyon değeri limiti (dar SL için yeterli)

# ESKİ SİSTEM (USE_FIXED_RISK_USD=False ise kullanılır)
BASE_RISK_PERCENT = float(os.getenv("BASE_RISK_PERCENT", 10.0))  # %10 = $20 POZİSYON DEĞERİ (kaldıraç dahil)

MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 15))  # Maksimum 15 pozisyon
MAX_RISK_PER_GROUP = float(os.getenv("MAX_RISK_PER_GROUP", 30.0))  # Grup başı %30 risk (10-12 pozisyon/grup)
# v6.0: 15% → 30% (Her gruptan daha fazla pozisyon alabilmek için)
# Hesaplama: 30% ÷ 2.65% (pozisyon riski) ≈ 11 pozisyon/grup
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", 2.0))
MAX_POSITIONS_PER_SYMBOL = int(os.getenv("MAX_POSITIONS_PER_SYMBOL", 1))

# --- v5.0 AUTO-PILOT: Sermaye Yönetimi (Capital Manager) ---
MAX_DRAWDOWN_PERCENT = float(os.getenv("MAX_DRAWDOWN_PERCENT", -50.0))  # Devre kesici limiti (%)
PROFIT_TARGET_PERCENT = float(os.getenv("PROFIT_TARGET_PERCENT", 50.0))  # Kâr realizasyonu hedefi (%)
AUTO_CLOSE_ON_CIRCUIT_BREAKER = os.getenv("AUTO_CLOSE_ON_CIRCUIT_BREAKER", "False").lower() == "true"  # ⚠️ TEHLİKELİ!
AUTO_TRANSFER_PROFIT = os.getenv("AUTO_TRANSFER_PROFIT", "False").lower() == "true"  # Otomatik kâr transferi
# -----------------------------------------------------------

# --- v6.0 UPDATED: SABİT Kaldıraç Sistemi (7 Kasım 2025) ---
# Yüzde tabanlı SL sistemi (%10 sabit) ile uyumlu
FUTURES_LEVERAGE = int(os.getenv("FUTURES_LEVERAGE", 8))  # SABİT 8x kaldıraç

# Dinamik kaldıraç devre dışı (yüzde bazlı SL ile uyumsuz)
DYNAMIC_LEVERAGE_ENABLED = False

# ESKİ DİNAMİK SİSTEM (kapalı - referans için tutuldu)
LEVERAGE_BY_SL_DISTANCE = {
    0.02: 10,  # SL %2 mesafede  → 10x kaldıraç (tasfiye %10, güvenlik %8)
    0.05: 5,   # SL %5 mesafede  → 5x kaldıraç (tasfiye %20, güvenlik %15)
    0.10: 3,   # SL %10 mesafede → 3x kaldıraç (tasfiye %33, güvenlik %23)
    0.15: 2    # SL %15 mesafede → 2x kaldıraç (tasfiye %50, güvenlik %35)
}
MINIMUM_SAFETY_MARGIN = 0.08  # SL ile tasfiye arası minimum %8 mesafe

# ESKİ SİSTEM (yedek - volatilite bazlı)
LEVERAGE_LOW_VOLATILITY = 10
LEVERAGE_MID_VOLATILITY = 5
LEVERAGE_HIGH_VOLATILITY = 3
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
# ESKİ SİSTEM: ATR tabanlı dinamik SL/TP → Karmaşık hesaplamalar
# YENİ SİSTEM: Basit yüzde tabanlı → %10 zarar / %20-40 kar
USE_PERCENTAGE_SL_TP = True  # Yüzde tabanlı sistem kullan (ATR yerine)

# Stop Loss: Pozisyon değerinin %10 zararında
SL_PERCENT = float(os.getenv("SL_PERCENT", 10.0))  # %10 zarar

# Take Profit: Kademeli sistem
PARTIAL_TP_ENABLED = True  # Kısmi kar alma mekanizmasını aktifleştir
PARTIAL_TP_1_PERCENT = 50.0  # İlk kısmi TP'de pozisyonun %50'si kapatılır
PARTIAL_TP_1_PROFIT_PERCENT = 20.0  # İlk TP: Pozisyon değerinin %20 karı (2.0 R:R)
PARTIAL_TP_2_PROFIT_PERCENT = 40.0  # İkinci TP: Pozisyon değerinin %40 karı (4.0 R:R)

# Hesaplama Örneği:
# Pozisyon: $100 (kaldıraç dahil)
# SL: -$10 (pozisyon değerinin %10'u)
# TP_1: +$20 (pozisyon değerinin %20'si) → %50 pozisyon kapat
# TP_2: +$40 (pozisyon değerinin %40'ı) → Kalan %50 kapat
# R:R_1 = 20/10 = 2.0, R:R_2 = 40/10 = 4.0
# ---------------------------------------------------------

# Strateji Filtre Ayarları
MAX_ATR_PERCENT = float(os.getenv("MAX_ATR_PERCENT", 5.0))
# ... (dosyanın geri kalanı aynı) ...

# --- v5.0 ULTRA-OPTIMIZED: Kalite Notu Risk Çarpanları ---
# GÜNCELLENDİ (6 Kasım 2025): C-grade pozisyon boyutu problemi çözüldü
# Eski: C = 0.5x (çok küçük pozisyonlar)
# Yeni: C = 0.9x (normal pozisyonlar, minimal ceza)
QUALITY_MULTIPLIERS = { 'A': 1.3, 'B': 1.1, 'C': 0.9, 'D': 0.0 }
# A: %30 bonus (çok güçlü sinyaller)
# B: %10 bonus (iyi sinyaller)
# C: %10 ceza (orta seviye - çoğu sinyal burası)
# D: Tamamen iptal (sadece çok kötü sinyaller)

# --- GÜNCELLENDİ: Dinamik SL/TP Ayarları (Aşama 3) ---
# ESKİ SİSTEM: ATR tabanlı (USE_PERCENTAGE_SL_TP=False ise kullanılır)
SL_ATR_MULTIPLIER = float(os.getenv("SL_ATR_MULTIPLIER", 2.0))
TP_ATR_MULTIPLIER = float(os.getenv("TP_ATR_MULTIPLIER", 3.5)) 
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", 2.0))  # Minimum kabul edilebilir R:R oranı 

# Strateji Filtre Ayarları
MAX_ATR_PERCENT = float(os.getenv("MAX_ATR_PERCENT", 5.0)) 
MIN_ATR_PERCENT_BREAKOUT = float(os.getenv("MIN_ATR_PERCENT_BREAKOUT", 0.5))
PULLBACK_VOL_RATIO_LIMIT = float(os.getenv("PULLBACK_VOL_RATIO_LIMIT", 2.0))
BREAKOUT_VOL_RATIO_MIN = float(os.getenv("BREAKOUT_VOL_RATIO_MIN", 2.0))

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


print("Config: Tüm yapılandırma değişkenleri yüklendi.")