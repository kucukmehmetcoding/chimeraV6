# src/risk_manager/correlation_manager.py

import logging
import pandas as pd
from typing import Dict, List, Optional
import sys, os
import time

# Proje kökünü path'e ekle
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path: sys.path.append(project_root)

# Loglamayı ayarla
logger = logging.getLogger(__name__)

try:
    from src.data_fetcher import binance_fetcher
    from src import config
except ImportError:
    logger.critical("correlation_manager: Gerekli modüller import edilemedi!")
    raise

def calculate_correlation_matrix(symbols: List[str], days: int = 30) -> Optional[pd.DataFrame]:
    """
    Verilen sembol listesi için Binance'den 1D verileri çeker ve
    kapanış fiyatlarına dayalı bir Pearson korelasyon matrisi hesaplar.
    """
    if not symbols:
        logger.warning("Korelasyon hesaplamak için sembol listesi boş.")
        return None

    logger.info(f"{len(symbols)} sembol için son {days} günlük veriler çekiliyor (Korelasyon Matrisi için)...")
    
    all_closes = {}
    failed_symbols = []

    for i, symbol in enumerate(symbols):
        # API limitlerini aşmamak için küçük bir bekleme
        # Bu işlem (eğer 100+ coin varsa) uzun sürecek, ana döngüden ayrı çalışmalı
        # (update_sentiment_cache içinde olduğu için sorun değil)
        time.sleep(getattr(config, 'SCAN_DELAY_SECONDS', 0.5) * 0.5) # Normal gecikmenin yarısı
        
        # 1D verisi, 'days' + (NaN olabilecek ekstra mumlar) kadar çekilir
        klines_df = binance_fetcher.get_binance_klines(symbol, '1d', limit=days + 10)
        
        if klines_df is not None and not klines_df.empty and len(klines_df) >= days:
            # Sadece 'close' sütununu ve son 'days' kadarını al
            all_closes[symbol] = klines_df['close'].iloc[-days:].reset_index(drop=True)
        else:
            logger.warning(f"   {symbol} için korelasyon verisi çekilemedi/yetersiz.")
            failed_symbols.append(symbol)

    if len(all_closes) < 2:
        logger.error("Korelasyon matrisi hesaplamak için yeterli (en az 2) coin verisi bulunamadı.")
        return None
        
    if failed_symbols:
         logger.warning(f"{len(failed_symbols)} sembol için korelasyon hesaplaması atlandı: {failed_symbols[:5]}...")

    try:
        # Tüm kapanış serilerini tek bir DataFrame'de birleştir
        closes_df = pd.DataFrame(all_closes)
        
        # Fiyatların kendisine değil, yüzdesel değişimlerine bakmak daha doğrudur
        returns_df = closes_df.pct_change().dropna()
        
        # Korelasyon matrisini hesapla
        correlation_matrix = returns_df.corr(method='pearson')
        
        logger.info(f"✅ {len(all_closes)} sembol için Korelasyon Matrisi başarıyla hesaplandı.")
        return correlation_matrix

    except Exception as e:
        logger.error(f"Korelasyon matrisi oluşturulurken hata: {e}", exc_info=True)
        return None