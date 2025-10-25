import os
from dotenv import load_dotenv

# .env dosyasını yükle (eğer varsa)
# Proje kök dizinindeki .env dosyasını arar (src klasörünün bir üstü)
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- API Anahtarları (Ortam Değişkenlerinden Oku) ---
# Gerçek anahtarları BURAYA YAZMAYIN! .env dosyasına yazın.

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "YOUR_BINANCE_API_KEY_PLACEHOLDER")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "YOUR_BINANCE_SECRET_KEY_PLACEHOLDER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_PLACEHOLDER")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER")

# Opsiyonel API Anahtarları
WHALE_ALERT_API_KEY = os.getenv("WHALE_ALERT_API_KEY", None) # Eğer yoksa None olacak
SERPAPI_KEY = os.getenv("SERPAPI_KEY", None) # Eğer yoksa None olacak

# --- Portföy Ayarları ---
VIRTUAL_PORTFOLIO_USD = 1000.0  # Sanal portföy başlangıç değeri (Dolar)
BASE_RISK_PERCENT = 2.0      # İşlem başına temel risk yüzdesi (%)
MAX_OPEN_POSITIONS = 5         # Aynı anda açık olabilecek maksimum pozisyon sayısı
MAX_RISK_PER_GROUP = 5.0       # Bir korelasyon grubuna atanabilecek maksimum toplam portföy riski (%)

# --- Tarama Ayarları ---
SCAN_INTERVAL_MINUTES = 10     # Ana tarama döngüsünün ne sıklıkla çalışacağı (dakika)
DYNAMIC_SCAN_TOP_N = 50        # Dinamik taramada seçilecek en hareketli coin sayısı
SCAN_DELAY_SECONDS = 5         # Coinler arası bekleme süresi (saniye) - Rate Limit için

# --- Alfa Ayarları ---
PRIORITY_SYMBOLS = [          # Alfa analizi (On-Chain/Sentiment) yapılacak öncelikli coinler
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "MATICUSDT", "SHIBUSDT", "TRXUSDT", "UNIUSDT", "LTCUSDT",
    # İhtiyaç duyarsan bu listeyi düzenleyebilirsin
]
ALPHA_CACHE_EXPIRY_HOURS = 1 # Alfa verisi ne kadar süreyle geçerli (saat)

# --- Korelasyon Grupları ---
# Bu listeyi daha sonra dolduracağız veya ayrı bir dosyadan okuyacağız.
# Şimdilik örnek birkaç tane ekleyelim.
CORRELATION_GROUPS = {
    'BTCUSDT': 'MAJOR',
    'ETHUSDT': 'MAJOR',
    'PEPEUSDT': 'MEME',
    'SHIBUSDT': 'MEME',
    'DOGEUSDT': 'MEME',
    'WLDUSDT': 'AI',
    'FETUSDT': 'AI',
    'SOLUSDT': 'L1',
    'AVAXUSDT': 'L1',
    'LINKUSDT': 'INFRA',
    # ... diğer ~100 coin buraya eklenecek ...
}

# --- Dosya Yolları ---
# Verilerin (açık pozisyonlar, işlem geçmişi vb.) kaydedileceği yerler
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data') # Proje kökünde 'data' klasörü
ALPHA_CHACHE_FILE = os.path.join(DATA_DIR, 'alpha_cache.json')
OPEN_POSITIONS_FILE = os.path.join(DATA_DIR, 'open_positions.json')
TRADE_HISTORY_FILE = os.path.join(DATA_DIR, 'trades_history.csv')

# --- Loglama Ayarları ---
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'chimera.log')
LOG_LEVEL = 'INFO' # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Gerekli data klasörünü oluştur (eğer yoksa)
os.makedirs(DATA_DIR,exist_ok=True)

print("Config Loaded.")