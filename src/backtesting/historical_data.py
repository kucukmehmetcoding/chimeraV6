"""
Historical Data Fetcher
Binance'den historical OHLCV data çeker ve cache'ler
"""

import os
import time
import logging
import pandas as pd
from datetime import datetime, timedelta
from binance.client import Client
from src.config import BINANCE_API_KEY, BINANCE_SECRET_KEY

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'backtest_cache')
os.makedirs(CACHE_DIR, exist_ok=True)


class HistoricalDataFetcher:
    """
    Binance'den historical klines (OHLCV) data indirir
    Multiple timeframes destekler: 1d, 4h, 1h
    Local cache kullanır (CSV formatında)
    """
    
    def __init__(self, use_cache=True):
        """
        Args:
            use_cache: True ise önce cache'den okur, yoksa API'den çeker
        """
        self.client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        self.use_cache = use_cache
    
    def fetch_klines(self, symbol: str, interval: str, start_date: str, end_date: str = None) -> pd.DataFrame:
        """
        Belirli tarih aralığında OHLCV data çeker
        
        Args:
            symbol: Trading pair (örn: 'BTCUSDT')
            interval: Kline interval ('1d', '4h', '1h')
            start_date: Başlangıç tarihi (format: 'YYYY-MM-DD')
            end_date: Bitiş tarihi (None ise bugün)
        
        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        # Cache file path
        cache_file = os.path.join(
            CACHE_DIR, 
            f"{symbol}_{interval}_{start_date}_{end_date or 'now'}.csv"
        )
        
        # Cache kontrolü
        if self.use_cache and os.path.exists(cache_file):
            logger.info(f"📂 Cache'den okunuyor: {cache_file}")
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        
        # API'den çek
        logger.info(f"🌐 Binance API'den çekiliyor: {symbol} {interval} ({start_date} - {end_date or 'now'})")
        
        # Tarih parse
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        if end_date:
            end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        else:
            end_ts = int(datetime.now().timestamp() * 1000)
        
        # Binance API limit: 1000 klines per request
        all_klines = []
        current_start = start_ts
        
        while current_start < end_ts:
            try:
                klines = self.client.get_historical_klines(
                    symbol=symbol,
                    interval=interval,
                    start_str=current_start,
                    end_str=end_ts,
                    limit=1000
                )
                
                if not klines:
                    break
                
                all_klines.extend(klines)
                
                # Son kline'ın timestamp'i
                current_start = klines[-1][0] + 1
                
                # Rate limit protection
                time.sleep(0.5)
                
                logger.debug(f"   Çekilen: {len(klines)} klines (total: {len(all_klines)})")
                
            except Exception as e:
                logger.error(f"❌ Kline çekme hatası: {e}")
                break
        
        # DataFrame'e dönüştür
        if not all_klines:
            logger.warning(f"⚠️ {symbol} için data bulunamadı")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Sadece gerekli kolonları al
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        # Tip dönüşümleri
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        # Cache'e kaydet
        df.to_csv(cache_file, index=False)
        logger.info(f"💾 Cache'e kaydedildi: {cache_file} ({len(df)} klines)")
        
        return df
    
    def fetch_multiple_timeframes(self, symbol: str, start_date: str, end_date: str = None) -> dict:
        """
        Birden fazla timeframe'de data çeker (1d, 4h, 1h)
        
        Returns:
            dict: {'1d': df_1d, '4h': df_4h, '1h': df_1h}
        """
        timeframes = ['1d', '4h', '1h']
        data = {}
        
        for interval in timeframes:
            df = self.fetch_klines(symbol, interval, start_date, end_date)
            data[interval] = df
            logger.info(f"   ✅ {symbol} {interval}: {len(df)} klines")
        
        return data
    
    def clear_cache(self):
        """Cache klasörünü temizle"""
        import shutil
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR)
            logger.info("🧹 Cache temizlendi")


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = HistoricalDataFetcher(use_cache=True)
    
    # Son 3 ay BTC data çek
    end = datetime.now()
    start = end - timedelta(days=90)
    
    logger.info("=" * 60)
    logger.info("BTC Historical Data Test")
    logger.info("=" * 60)
    
    data = fetcher.fetch_multiple_timeframes(
        symbol='BTCUSDT',
        start_date=start.strftime('%Y-%m-%d'),
        end_date=end.strftime('%Y-%m-%d')
    )
    
    for interval, df in data.items():
        logger.info(f"\n{interval} data:")
        logger.info(f"   Başlangıç: {df['timestamp'].iloc[0]}")
        logger.info(f"   Bitiş: {df['timestamp'].iloc[-1]}")
        logger.info(f"   Toplam: {len(df)} klines")
        logger.info(f"   İlk close: ${df['close'].iloc[0]:.2f}")
        logger.info(f"   Son close: ${df['close'].iloc[-1]:.2f}")
