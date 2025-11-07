# src/data_fetcher/binance_fetcher.py
import os
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
import logging
import time
from typing import Optional, List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception # Otomatik yeniden deneme
import sys

# Proje kök dizinindeki src klasörünü Python yoluna ekle (config'i bulabilmek için)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.append(src_path)

# Yapılandırma dosyasını içe aktar
try:
    # GÜNCELLENDİ: Ana betik config'i import ettiği için burada tekrar etmeye gerek yok gibi
    # Ancak API anahtarları SADECE burada kullanılıyorsa kalabilir.
    # Eğer main_orchestrator'da da config import ediliyorsa, bu import gereksiz olabilir.
    # Şimdilik bırakıyoruz.
    from config import BINANCE_API_KEY, BINANCE_SECRET_KEY
except ImportError:
    print("HATA: config.py bulunamadı veya içe aktarılamadı.")
    print("Lütfen projenin doğru klasörde olduğundan ve config.py'nin src içinde olduğundan emin olun!")
    sys.exit(1) # Hata durumunda programdan çık.

# Loglamayı ayarla (Ana betik yapılandırıyorsa bu kısım atlanabilir veya geliştirilebilir)
# GÜNCELLENDİ: Daha standart logger alma
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    # Sadece ana betik logger'ı yapılandırmadıysa temel yapılandırmayı yap
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')

# --- Binance İstemcisini Başlatma ---
binance_client = None

# API anahtar kontrolü (Mevcut haliyle iyi)
if BINANCE_API_KEY and BINANCE_SECRET_KEY and \
   BINANCE_API_KEY != "YOUR_BINANCE_API_KEY_PLACEHOLDER" and \
   BINANCE_SECRET_KEY != "YOUR_BINANCE_SECRET_KEY_PLACEHOLDER":
    try:
        # Timeout 10s → 20s (yavaş bağlantılar için)
        binance_client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY, 
                                requests_params={'timeout': 20})
        binance_client.ping()
        logger.info("✅ Binance API istemcisi başarıyla başlatıldı ve bağlantı kuruldu.")
    except (BinanceAPIException, BinanceRequestException) as e:
        logger.error(f"❌ Binance API istemcisi başlatılırken hata oluştu: {e}")
        logger.error("   API anahtarlarınızın doğru olduğundan ve Binance'te izinlerin ayarlandığından emin olun.")
        binance_client = None # Hata durumunda istemciyi None yap
    except Exception as e:
        logger.error(f"❌ Binance API istemcisi başlatılırken beklenmedik bir hata oluştu: {e}")
        binance_client = None
else:
    logger.warning("⚠️ Binance API anahtarları eksik veya yer tutucu değerler içeriyor (config.py).")
    logger.warning("   Binance verileri çekilemeyecek.")


# --- Mum Verisi Çekme Fonksiyonu ---

# GÜNCELLENDİ: Sadece tekrar denenebilir hatalar için retry yapalım
# BinanceRequestException (network hatası) ve Rate Limit (örn. kod -1003) tekrar denenebilir.
def should_retry_binance_exception(exception):
    """Sadece tekrar denenebilir Binance hataları için True döndür."""
    if isinstance(exception, BinanceRequestException):
        return True # Network hatalarını tekrar dene
    if isinstance(exception, BinanceAPIException):
        # Rate limit veya geçici sunucu hatalarını tekrar dene
        # -1003: TOO_MANY_REQUESTS
        # -1021: Timestamp for this request is outside of the recvWindow
        # -1007: Timeout waiting for response from backend server
        # Diğer potansiyel geçici hatalar...
        return exception.code in [-1003, -1021, -1007] # veya 429, 418 durum kodları
    return False # Diğer hataları (örn. -1121 Invalid Symbol) tekrar deneme

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5), retry=retry_if_exception(should_retry_binance_exception))
def get_binance_klines(symbol: str, interval: str, limit: int = 500) -> pd.DataFrame | None:
    """
    Binance FUTURES API'sinden belirtilen sembol ve zaman aralığı için tarihsel mum verilerini çeker.
    Tekrar denenebilir hatalarda (network, rate limit) otomatik yeniden dener.
    
    GÜNCELLENDİ (6 Kasım 2025): Spot → Futures API geçişi yapıldı
    """
    if not binance_client:
        logger.error(f"❌ Binance istemcisi başlatılamadığı için {symbol} verisi çekilemiyor.")
        return None

    logger.info(f"Binance Futures'tan {symbol} için {interval} aralığında {limit} adet mum verisi çekiliyor...")

    try:
        # GÜNCELLENDİ: Spot API → Futures API
        klines = binance_client.futures_klines(symbol=symbol, interval=interval, limit=limit)

        if not klines:
            # GÜNCELLENDİ: Doğru loglama çağrısı
            logger.warning(f"⚠️ {symbol} için {interval} aralığında Binance'ten veri bulunamadı (boş liste döndü).")
            return None

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'
        ])
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        df.set_index('timestamp', inplace=True)

        logger.info(f"✅ {symbol} için {len(df)} adet mum verisi başarıyla çekildi ve işlendi.")
        return df

    except BinanceAPIException as e:
        logger.error(f"❌ Binance API hatası ({symbol}, {interval}): {e.code} - {e.message}")
        if e.code == -1121: # Invalid symbol hatası
            logger.warning(f"   '{symbol}' geçersiz bir sembol. Bu hata yeniden denenmeyecek.")
            return None # Geçersiz sembol için tekrar denemeye gerek yok
        # Diğer API hataları için hatayı yükselt ki @retry çalışabilsin (eğer retry koşulu uygunsa)
        raise e

    except BinanceRequestException as e:
        logger.error(f"❌ Binance istek hatası ({symbol}, {interval}): {e}")
        # İstek hataları için hatayı yükselt ki @retry çalışsın
        raise e

    except Exception as e:
        # Kod içindeki diğer beklenmedik hatalar (örn: DataFrame işleme hatası)
        logger.error(f"❌ {symbol} verisi işlenirken kod içinde beklenmedik hata: {e}", exc_info=True)
        # Bu durumda None döndürelim, yeniden deneme yapmayalım
        return None


def get_current_price(symbol: str) -> float | None:
    """
    Verilen sembol için anlık fiyatı Binance FUTURES'tan alır.
    
    GÜNCELLENDİ (6 Kasım 2025): Spot → Futures API geçişi yapıldı
    """
    # GÜNCELLENDİ: İstemci kontrolü eklendi
    if not binance_client:
        logger.error(f"❌ Binance istemcisi başlatılamadığı için {symbol} anlık fiyatı alınamıyor.")
        return None
    try:
        # GÜNCELLENDİ: Spot API → Futures API
        ticker = binance_client.futures_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        logger.debug(f"Futures anlık fiyat alındı {symbol}: {price}")
        return price
    except BinanceAPIException as e:
        logger.error(f"❌ {symbol} için anlık fiyat alınırken Binance API hatası: {e}")
        return None
    except KeyError:
        logger.error(f"❌ {symbol} için anlık fiyat alınamadı, API yanıtında 'price' anahtarı yok.")
        return None
    except Exception as e:
        logger.error(f"❌ {symbol} için anlık fiyat alınırken beklenmedik hata: {e}", exc_info=True)
        return None


# --- YENİ EKLENDİ: 24 Saatlik Özet Veri Çekici ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5), retry=retry_if_exception(should_retry_binance_exception))
def get_all_24h_ticker_data() -> Optional[List[Dict[str, Any]]]:
    """
    Binance FUTURES'taki TÜM USDT paritelerinin 24 saatlik özet verilerini
    (hacim, fiyat değişimi vb.) tek bir API çağrısıyla çeker.
    
    GÜNCELLENDİ (6 Kasım 2025): Spot → Futures API geçişi yapıldı
    
    Returns:
        Optional[List[Dict[str, Any]]]: Her sembol için bir sözlük listesi veya hata durumunda None.
        Her sözlük şu anahtarları içerir: 'symbol', 'priceChangePercent', 'quoteVolume', vb.
    """
    if not binance_client:
        logger.error("❌ Binance istemcisi başlatılamadığı için 24 saatlik özet verileri çekilemiyor.")
        return None
    
    logger.info("Tüm Futures sembolleri için 24 saatlik özet verileri (ticker) çekiliyor...")
    try:
        # GÜNCELLENDİ: Spot market → Futures market
        tickers = binance_client.futures_ticker()
        
        if not tickers:
            logger.warning("Binance Futures'tan 24 saatlik özet verisi alınamadı (boş liste döndü).")
            return None
        
        logger.info(f"✅ {len(tickers)} adet Futures sembolü için 24 saatlik özet verisi başarıyla çekildi.")
        return tickers

    except BinanceAPIException as e:
        logger.error(f"❌ Binance 24h ticker verisi alınırken API hatası: {e.code} - {e.message}")
        # Rate limit hatasını retry mekanizmasına iletmek için tekrar raise et
        if e.code in [-1003, -1021, -1007] or e.status_code in [429, 418]:
            raise e
        return None
    except BinanceRequestException as e:
        logger.error(f"❌ Binance 24h ticker verisi alınırken istek hatası: {e}")
        raise e  # Retry mekanizması için
    except Exception as e:
        logger.error(f"❌ Binance 24h ticker verisi alınırken beklenmedik hata: {e}", exc_info=True)
        return None


# --- v4.0 Enhanced: Tüm Futures USDT Çiftlerini Çek ---
@retry(stop=stop_after_attempt(3), wait=wait_fixed(5), retry=retry_if_exception(should_retry_binance_exception))
def get_all_futures_usdt_symbols() -> Optional[List[str]]:
    """
    Binance Futures'ta işlem gören tüm USDT perpetual kontratlarını çeker.
    
    Returns:
        Optional[List[str]]: ['BTCUSDT', 'ETHUSDT', ...] veya None (hata durumunda)
    """
    if binance_client is None:
        logger.warning("Binance istemcisi başlatılmamış, Futures sembol listesi alınamıyor.")
        return None
    
    try:
        logger.info("Binance Futures USDT perpetual kontratları çekiliyor...")
        
        # Futures exchange bilgilerini al
        exchange_info = binance_client.futures_exchange_info()
        
        usdt_symbols = []
        for symbol_info in exchange_info.get('symbols', []):
            symbol = symbol_info.get('symbol', '')
            status = symbol_info.get('status', '')
            quote_asset = symbol_info.get('quoteAsset', '')
            contract_type = symbol_info.get('contractType', '')
            
            # Filtreler:
            # 1. USDT çifti olmalı
            # 2. TRADING durumunda olmalı
            # 3. PERPETUAL (sonsuz) kontrat olmalı
            if (quote_asset == 'USDT' and 
                status == 'TRADING' and 
                contract_type == 'PERPETUAL'):
                usdt_symbols.append(symbol)
        
        logger.info(f"✅ Binance Futures: {len(usdt_symbols)} adet USDT perpetual kontratı bulundu")
        return sorted(usdt_symbols)
    
    except BinanceAPIException as e:
        logger.error(f"❌ Binance Futures API hatası: {e.code} - {e.message}")
        if e.code in [-1003, -1021, -1007] or e.status_code in [429, 418]:
            raise e  # Retry için
        return None
    except BinanceRequestException as e:
        logger.error(f"❌ Binance Futures bağlantı hatası: {e}")
        raise e  # Retry için
    except Exception as e:
        logger.error(f"❌ Futures sembol listesi alınırken beklenmedik hata: {e}", exc_info=True)
        return None


# --- Test Kodu ---
if __name__ == "__main__":
    # Test için log seviyesini DEBUG yapabiliriz
    # logging.getLogger().setLevel(logging.DEBUG)

    logger.info("--- binance_fetcher.py Test Modu ---")

    if not binance_client:
        logger.error("Test başarısız: Binance istemcisi başlatılamadı.")
        sys.exit(1)

    # --- get_binance_klines testi ---
    logger.info("\n--- get_binance_klines fonksiyon testi ---")
    btc_1h_data = get_binance_klines(symbol='BTCUSDT', interval='1h', limit=10) # Limiti küçük tutalım
    if btc_1h_data is not None:
        print("\nBTCUSDT 1h Verisi (İlk 5 Satır):")
        print(btc_1h_data.head())
        print("\nVeri Tipleri:")
        btc_1h_data.info()
    else:
        print("\nBTCUSDT 1h verisi çekilemedi.")

    # Geçersiz sembol testi
    logger.info("\n--- Geçersiz Sembol Testi ---")
    invalid_data = get_binance_klines(symbol='INVALIDCOIN', interval='1h', limit=10)
    if invalid_data is None:
        print("✅ Geçersiz sembol testi başarılı (None döndü).")
    else:
        print("❌ Geçersiz sembol testi başarısız.")

    # --- get_current_price testi ---
    # GÜNCELLENDİ: Test eklendi
    logger.info("\n--- get_current_price fonksiyon testi ---")
    btc_price = get_current_price(symbol='BTCUSDT')
    if btc_price is not None:
        print(f"✅ Anlık BTCUSDT Fiyatı: {btc_price}")
    else:
        print("❌ Anlık BTCUSDT fiyatı alınamadı.")

    eth_price = get_current_price(symbol='ETHUSDT')
    if eth_price is not None:
        print(f"✅ Anlık ETHUSDT Fiyatı: {eth_price}")
    else:
        print("❌ Anlık ETHUSDT fiyatı alınamadı.")

    invalid_price = get_current_price(symbol='INVALIDCOIN')
    if invalid_price is None:
        print(f"✅ Geçersiz sembol için anlık fiyat testi başarılı (None döndü).")
    else:
         print(f"❌ Geçersiz sembol için anlık fiyat testi başarısız (Fiyat döndü: {invalid_price}).")

    # --- get_all_24h_ticker_data testi ---
    logger.info("\n--- get_all_24h_ticker_data fonksiyon testi ---")
    all_tickers = get_all_24h_ticker_data()
    if all_tickers is not None:
        print(f"✅ {len(all_tickers)} adet sembol için 24 saatlik özet verisi alındı.")
        print("\nİlk 3 sembol örneği:")
        for ticker in all_tickers[:3]:
            symbol = ticker.get('symbol', 'N/A')
            price_change = ticker.get('priceChangePercent', 'N/A')
            volume = ticker.get('quoteVolume', 'N/A')
            print(f"  {symbol}: Değişim: {price_change}%, Hacim: {volume}")
    else:
        print("❌ 24 saatlik özet verileri alınamadı.")

    logger.info("\n--- Test tamamlandı ---")