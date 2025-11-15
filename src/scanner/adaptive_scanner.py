# src/scanner/adaptive_scanner.py

"""
Adaptive Scanner - Smart EMA Pre-Crossover Detection
Tüm Binance Futures coinlerini tarayıp EMA kesişmesine yakın olanları tespit eder.
"""

import logging
import time
import random
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class AdaptiveScanner:
    """
    Binance Futures'taki tüm coinleri tarayıp EMA pre-crossover durumunu tespit eder.
    """
    
    def __init__(self, config, binance_client=None):
        """
        Args:
            config: Config modülü
            binance_client: Binance API client (opsiyonel - binance_fetcher kullanılır)
        """
        self.config = config
        self.client = binance_client  # Artık kullanılmıyor ama geriye uyumluluk için bırakıldı
        
        # Scan parametreleri
        self.scan_interval = getattr(config, 'ADAPTIVE_SCAN_INTERVAL', 300)  # 5 dakika
        self.timeframe = getattr(config, 'HYBRID_TIMEFRAME', '15m')
        self.ema_short = getattr(config, 'HYBRID_EMA_SHORT', 5)
        self.ema_long = getattr(config, 'HYBRID_EMA_LONG', 20)
        self.lookback = getattr(config, 'HYBRID_WARMUP_CANDLES', 25)
        
        # Pre-crossover threshold (EMA'lar ne kadar yakın olmalı?)
        self.proximity_threshold = getattr(config, 'ADAPTIVE_PROXIMITY_THRESHOLD', 0.5)  # %0.5
        
        # Cache
        self.all_futures_symbols: List[str] = []
        self.last_full_scan_time = 0
        self.symbol_refresh_interval = 3600  # 1 saatte bir symbol listesi yenile
        
        logger.info(f"📡 AdaptiveScanner initialized")
        logger.info(f"   Scan interval: {self.scan_interval}s ({self.scan_interval/60:.1f} min)")
        logger.info(f"   Timeframe: {self.timeframe}")
        logger.info(f"   EMA: {self.ema_short} x {self.ema_long}")
        logger.info(f"   Proximity threshold: {self.proximity_threshold}%")
    
    def get_all_futures_symbols(self) -> List[str]:
        """
        Binance Futures'taki tüm USDT perpetual coinleri getirir.
        1 saatte bir yenilenir (yeni listeler için).
        
        Returns:
            List[str]: USDT perpetual semboller (örn: ['BTCUSDT', 'ETHUSDT', ...])
        """
        now = time.time()
        
        # Cache'den dön (1 saat dolmadıysa)
        if self.all_futures_symbols and (now - self.last_full_scan_time) < self.symbol_refresh_interval:
            return self.all_futures_symbols
        
        try:
            # binance_fetcher modülünü kullan
            from src.data_fetcher.binance_fetcher import binance_client
            
            logger.info("🔍 Binance Futures symbol listesi çekiliyor...")
            exchange_info = binance_client.futures_exchange_info()
            
            # Sadece USDT perpetual ve TRADING aktif olanlar
            usdt_symbols = [
                s['symbol'] 
                for s in exchange_info['symbols']
                if s['symbol'].endswith('USDT') 
                and s['contractType'] == 'PERPETUAL'
                and s['status'] == 'TRADING'
            ]
            
            self.all_futures_symbols = sorted(usdt_symbols)
            self.last_full_scan_time = now
            
            logger.info(f"✅ {len(self.all_futures_symbols)} adet USDT perpetual coin bulundu")
            return self.all_futures_symbols
            
        except Exception as e:
            logger.error(f"❌ Symbol listesi alınamadı: {e}")
            # Fallback: CORRELATION_GROUPS kullan
            if not self.all_futures_symbols:
                self.all_futures_symbols = list(getattr(self.config, 'CORRELATION_GROUPS', {}).keys())
                logger.warning(f"⚠️ Fallback: CORRELATION_GROUPS kullanılıyor ({len(self.all_futures_symbols)} coin)")
            return self.all_futures_symbols
    
    def calculate_ema_proximity(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        DataFrame'den EMA proximity hesaplar.
        
        Args:
            df: OHLCV DataFrame (en az 25 mum olmalı)
        
        Returns:
            Dict: {
                'ema_short': float,
                'ema_long': float,
                'distance_percent': float,  # EMA'lar arası mesafe (%)
                'is_close': bool,           # Proximity threshold içinde mi?
                'short_above': bool,        # Short EMA yukarıda mı?
                'trend': str                # 'bullish' veya 'bearish'
            }
            None: Veri yetersiz veya hata
        """
        try:
            if df is None or df.empty or len(df) < self.lookback:
                return None
            
            # EMA hesapla
            df[f'ema{self.ema_short}'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
            df[f'ema{self.ema_long}'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
            
            # Son değerler
            last_row = df.iloc[-1]
            ema_short_val = last_row[f'ema{self.ema_short}']
            ema_long_val = last_row[f'ema{self.ema_long}']
            
            if pd.isna(ema_short_val) or pd.isna(ema_long_val):
                return None
            
            # Mesafe hesapla (%)
            distance_pct = abs((ema_short_val - ema_long_val) / ema_long_val) * 100
            short_above = ema_short_val > ema_long_val
            
            # Trend belirleme
            if short_above:
                trend = 'bullish'
            else:
                trend = 'bearish'
            
            # Proximity check
            is_close = distance_pct <= self.proximity_threshold
            
            return {
                'ema_short': float(ema_short_val),
                'ema_long': float(ema_long_val),
                'distance_percent': float(distance_pct),
                'is_close': is_close,
                'short_above': short_above,
                'trend': trend,
                'close_price': float(last_row['close'])
            }
            
        except Exception as e:
            logger.debug(f"EMA proximity hesaplanamadı: {e}")
            return None
    
    def check_instant_crossover(self, df: pd.DataFrame) -> Optional[str]:
        """
        ŞU ANKİ MUM İÇİNDE crossover olup olmadığını kontrol eder.
        
        CRITICAL (v10.7.1):
        - Bir önceki mumda kesişme → GEÇTE KALIRIZ ❌
        - Şu anki mumun BAŞINDA ve SONUNDA EMA karşılaştırması → ERKEN GİRİŞ ✅
        
        Mantık:
        1. Önceki mumun EMA'ları → Başlangıç durumu
        2. Şu anki mumun EMA'ları → Bitiş durumu
        3. Eğer aralarında kesişme olmuşsa → ANINDA SINYAL!
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            'LONG': Bullish crossover (5 EMA yukarı kesti 20 EMA'yı)
            'SHORT': Bearish crossover (5 EMA aşağı kesti 20 EMA'yı)
            None: Crossover yok
        """
        try:
            if df is None or df.empty or len(df) < 2:
                return None
            
            # EMA hesapla
            df[f'ema{self.ema_short}'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
            df[f'ema{self.ema_long}'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
            
            # CRITICAL: Önceki mum ve şu anki mum
            prev_row = df.iloc[-2]  # Mum başlangıcı (önceki mum kapanışı)
            curr_row = df.iloc[-1]  # Şu anki mum (henüz kapanmamış olabilir)
            
            prev_short = prev_row[f'ema{self.ema_short}']
            prev_long = prev_row[f'ema{self.ema_long}']
            curr_short = curr_row[f'ema{self.ema_short}']
            curr_long = curr_row[f'ema{self.ema_long}']
            
            # NaN check
            if pd.isna([prev_short, prev_long, curr_short, curr_long]).any():
                return None
            
            # Bullish crossover: ÖNCEDEN altındaydı, ŞİMDİ üstte
            if prev_short <= prev_long and curr_short > curr_long:
                return 'LONG'
            
            # Bearish crossover: ÖNCEDEN üstteydi, ŞİMDİ altta
            if prev_short >= prev_long and curr_short < curr_long:
                return 'SHORT'
            
            return None
            
        except Exception as e:
            logger.debug(f"Instant crossover check hatası: {e}")
            return None
    
    def scan_single_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Tek bir sembol için tarama yapar.
        
        Args:
            symbol: Sembol adı (örn: 'BTCUSDT')
        
        Returns:
            Dict: {
                'symbol': str,
                'proximity': Dict (calculate_ema_proximity sonucu),
                'instant_crossover': str veya None ('LONG'/'SHORT'/None),
                'timestamp': datetime
            }
            None: Hata durumunda
        """
        try:
            from src.data_fetcher.binance_fetcher import get_binance_klines
            
            # Kline verisi çek
            df = get_binance_klines(
                symbol=symbol,
                interval=self.timeframe,
                limit=self.lookback
            )
            
            if df is None or df.empty:
                return None
            
            # Proximity hesapla
            proximity = self.calculate_ema_proximity(df)
            if proximity is None:
                return None
            
            # Instant crossover kontrol
            instant_crossover = self.check_instant_crossover(df)
            
            return {
                'symbol': symbol,
                'proximity': proximity,
                'instant_crossover': instant_crossover,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.warning(f"Scan hatası [{symbol}]: {e}")
            return None
    
    def full_market_scan(self) -> Dict[str, Dict]:
        """
        Tüm Futures marketini tarar ve sonuçları döndürür.
        
        Returns:
            Dict: {
                'close_to_crossover': List[Dict],  # Proximity threshold içindeki coinler
                'instant_signals': List[Dict],     # Şu anda crossover yapmış coinler
                'total_scanned': int,
                'scan_duration': float,
                'timestamp': datetime
            }
        """
        start_time = time.time()
        logger.info("🔍 Full market scan başlatılıyor...")
        
        # Tüm symbolleri al
        all_symbols = self.get_all_futures_symbols()
        
        close_to_crossover = []
        instant_signals = []
        scanned_count = 0
        error_count = 0
        
        # 🎲 Rastgele sırayla tara (alfabetik bias önlemek için)
        random.shuffle(all_symbols)
        
        logger.info(f"📊 Toplam {len(all_symbols)} coin taranacak (rastgele sırayla)...")
        
        for idx, symbol in enumerate(all_symbols, 1):
            try:
                # Rate limit protection (daha kısa delay - 0.1s)
                time.sleep(0.1)
                
                # Scan
                result = self.scan_single_symbol(symbol)
                if result is None:
                    error_count += 1
                    # İlk 50 coin'de hataları göster
                    if idx <= 50:
                        logger.warning(f"⚠️ Scan başarısız: {symbol} (#{idx})")
                    continue
                
                scanned_count += 1
                proximity = result['proximity']
                
                # Instant crossover var mı?
                if result['instant_crossover']:
                    instant_signals.append({
                        'symbol': symbol,
                        'direction': result['instant_crossover'],
                        'price': proximity['close_price'],
                        'ema_short': proximity['ema_short'],
                        'ema_long': proximity['ema_long'],
                        'timestamp': result['timestamp']
                    })
                    logger.warning(f"🚨 INSTANT CROSSOVER: {symbol} → {result['instant_crossover']}")
                
                # Pre-crossover (yakın EMA'lar)
                elif proximity['is_close']:
                    close_to_crossover.append({
                        'symbol': symbol,
                        'distance_percent': proximity['distance_percent'],
                        'trend': proximity['trend'],
                        'price': proximity['close_price'],
                        'ema_short': proximity['ema_short'],
                        'ema_long': proximity['ema_long']
                    })
                
                # Progress log (her 10 coinde bir - daha sık)
                if idx % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = idx / elapsed if elapsed > 0 else 0
                    eta_seconds = (len(all_symbols) - idx) / rate if rate > 0 else 0
                    logger.info(f"   📈 Progress: {idx}/{len(all_symbols)} ({scanned_count} başarılı, {error_count} hata) - {rate:.1f} coin/s - ETA: {int(eta_seconds)}s")
                
            except Exception as e:
                error_count += 1
                if idx <= 50:  # İlk 50 coin'de exception'ları göster
                    logger.error(f"❌ Exception [{symbol}]: {e}")
                continue
        
        duration = time.time() - start_time
        
        # Sonuçları sırala (mesafeye göre)
        close_to_crossover.sort(key=lambda x: x['distance_percent'])
        
        logger.info(f"✅ Scan tamamlandı: {scanned_count} coin, {duration:.1f}s")
        logger.info(f"   📊 Pre-crossover: {len(close_to_crossover)} coin")
        logger.info(f"   🚨 Instant signals: {len(instant_signals)} coin")
        
        # Top 10 en yakın coinleri logla
        if close_to_crossover:
            logger.info(f"\n📍 Top 10 Pre-Crossover Coins:")
            for i, coin in enumerate(close_to_crossover[:10], 1):
                logger.info(f"   {i}. {coin['symbol']}: {coin['distance_percent']:.3f}% ({coin['trend']})")
        
        return {
            'close_to_crossover': close_to_crossover,
            'instant_signals': instant_signals,
            'total_scanned': scanned_count,
            'scan_duration': duration,
            'timestamp': datetime.now()
        }


# --- Yardımcı Fonksiyonlar ---

def create_adaptive_scanner(config, binance_client):
    """AdaptiveScanner instance oluşturur."""
    return AdaptiveScanner(config, binance_client)


if __name__ == '__main__':
    # Test bloğu
    import sys
    import os
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, project_root)
    
    from src import config
    from src.data_fetcher.binance_fetcher import get_binance_client
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
    )
    
    print("=" * 60)
    print("ADAPTIVE SCANNER TEST")
    print("=" * 60)
    
    client = get_binance_client()
    scanner = create_adaptive_scanner(config, client)
    
    # Full scan yap
    results = scanner.full_market_scan()
    
    print(f"\n📊 SCAN RESULTS:")
    print(f"   Total scanned: {results['total_scanned']}")
    print(f"   Pre-crossover: {len(results['close_to_crossover'])}")
    print(f"   Instant signals: {len(results['instant_signals'])}")
    print(f"   Duration: {results['scan_duration']:.1f}s")
