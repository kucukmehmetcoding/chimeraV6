#!/usr/bin/env python3
"""
Fibonacci Bot - Coin Scanner
24 saatte düşüş gösteren yüksek hacimli coinleri tarar
"""

import logging
from typing import List, Dict, Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException
import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BLACKLISTED_SYMBOLS

logger = logging.getLogger('fibonacci_bot.scanner')


class FibonacciScanner:
    """Düşüş trendindeki coinleri tarar"""
    
    def __init__(self, 
                 drop_threshold: float = -8.0,
                 min_volume_usdt: float = 1000000,
                 top_n: int = 10,
                 max_retries: int = 3):
        """
        Args:
            drop_threshold: Minimum düşüş yüzdesi (örn: -8.0)
            min_volume_usdt: Minimum 24s hacim (USD)
            top_n: Seçilecek coin sayısı
            max_retries: Binance bağlantı deneme sayısı
        """
        self.client = None
        self.max_retries = max_retries
        self._init_client()
        
        self.drop_threshold = drop_threshold
        self.min_volume_usdt = min_volume_usdt
        self.top_n = top_n
        
        # Spot market için ekstra blacklist
        self.spot_blacklist = list(BLACKLISTED_SYMBOLS) + [
            'USDT', 'USDC', 'BUSD', 'TUSD', 'DAI',  # Stablecoin'ler
            'UP', 'DOWN', 'BULL', 'BEAR',  # Leverage token'lar
        ]
    
    def _init_client(self):
        """Binance client'ı retry logic ile başlat"""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Binance API bağlantısı kuruluyor... (Deneme {attempt}/{self.max_retries})")
                self.client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
                logger.info("✅ Binance API bağlantısı başarılı")
                return
            except Exception as e:
                logger.warning(f"⚠️ Binance bağlantı hatası (Deneme {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    wait_time = attempt * 2  # 2, 4, 6 saniye bekle
                    logger.info(f"   {wait_time} saniye bekleniyor...")
                    time.sleep(wait_time)
                else:
                    logger.error("❌ Binance API bağlantısı kurulamadı!")
                    logger.error("   İnternet bağlantınızı kontrol edin:")
                    logger.error("   1. WiFi/Ethernet bağlantınız aktif mi?")
                    logger.error("   2. 'ping api.binance.com' komutuyla test edin")
                    logger.error("   3. VPN kullanıyorsanız kapatıp deneyin")
                    raise
    
    def get_all_spot_symbols(self) -> List[str]:
        """Binance Spot'taki tüm USDT çiftlerini getir"""
        try:
            exchange_info = self.client.get_exchange_info()
            
            symbols = []
            for symbol_info in exchange_info['symbols']:
                symbol = symbol_info['symbol']
                
                # Sadece USDT çiftleri
                if not symbol.endswith('USDT'):
                    continue
                
                # Trading aktif mi?
                if symbol_info['status'] != 'TRADING':
                    continue
                
                # Blacklist kontrolü - Base asset'i kontrol et (BTCUSDT -> BTC)
                base_asset = symbol_info['baseAsset']
                if base_asset in self.spot_blacklist:
                    continue
                
                symbols.append(symbol)
            
            logger.info(f"✅ {len(symbols)} Spot USDT çifti bulundu")
            return symbols
            
        except BinanceAPIException as e:
            logger.error(f"❌ Binance API hatası: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Sembol listesi hatası: {e}")
            return []
    
    def get_24h_tickers(self) -> Dict[str, Dict]:
        """24 saatlik ticker verilerini getir"""
        try:
            tickers = self.client.get_ticker()
            
            ticker_dict = {}
            for ticker in tickers:
                symbol = ticker['symbol']
                
                # Sadece USDT çiftleri
                if not symbol.endswith('USDT'):
                    continue
                
                ticker_dict[symbol] = {
                    'symbol': symbol,
                    'price_change_percent': float(ticker['priceChangePercent']),
                    'volume': float(ticker['volume']),
                    'quote_volume': float(ticker['quoteVolume']),  # USDT cinsinden hacim
                    'last_price': float(ticker['lastPrice']),
                    'high_price': float(ticker['highPrice']),
                    'low_price': float(ticker['lowPrice'])
                }
            
            logger.info(f"✅ {len(ticker_dict)} ticker verisi alındı")
            return ticker_dict
            
        except BinanceAPIException as e:
            logger.error(f"❌ Binance API hatası: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ Ticker verisi hatası: {e}")
            return {}
    
    def scan_losers(self) -> List[Dict]:
        """Düşüş trendindeki coinleri tara"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 FIBONACCI SCANNER BAŞLATILIYOR...")
        logger.info(f"   Düşüş Eşiği: < {self.drop_threshold}%")
        logger.info(f"   Min Hacim: ${self.min_volume_usdt:,.0f}")
        logger.info(f"   Top N: {self.top_n}")
        logger.info(f"{'='*60}\n")
        
        # 1. Sembol listesi
        symbols = self.get_all_spot_symbols()
        if not symbols:
            logger.error("❌ Sembol listesi boş!")
            return []
        
        # 2. Ticker verileri
        tickers = self.get_24h_tickers()
        if not tickers:
            logger.error("❌ Ticker verisi alınamadı!")
            return []
        
        # 3. Filtreleme
        losers = []
        checked_count = 0
        
        for symbol in symbols:
            if symbol not in tickers:
                continue
            
            ticker = tickers[symbol]
            checked_count += 1
            
            # İlk 5 coin için debug log
            if checked_count <= 5:
                logger.info(f"   DEBUG {symbol}: {ticker['price_change_percent']:+.2f}% | "
                           f"Threshold: {self.drop_threshold}% | "
                           f"Vol: ${ticker['quote_volume']:,.0f}")
            
            # Düşüş filtresi - En az drop_threshold kadar düşmüş olmalı
            # drop_threshold = -8.0 ise, -10% düşen geçer, -5% düşen atlanır
            if ticker['price_change_percent'] > self.drop_threshold:
                continue
            
            # Hacim filtresi
            if ticker['quote_volume'] < self.min_volume_usdt:
                continue
            
            losers.append(ticker)
            logger.info(f"   ✅ {symbol}: {ticker['price_change_percent']:+.2f}% | "
                       f"Vol: ${ticker['quote_volume']:,.0f}")
        
        logger.info(f"\n   Kontrol edilen: {checked_count} coin")
        
        # 4. Sıralama (hacme göre)
        losers.sort(key=lambda x: x['quote_volume'], reverse=True)
        
        # 5. Top N seç
        top_losers = losers[:self.top_n]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ TARAMA TAMAMLANDI!")
        logger.info(f"   Toplam Düşen: {len(losers)} coin")
        logger.info(f"   Seçilen: {len(top_losers)} coin")
        logger.info(f"{'='*60}\n")
        
        return top_losers
    
    def display_results(self, losers: List[Dict]):
        """Sonuçları göster"""
        if not losers:
            logger.info("📉 Kriterlere uyan coin bulunamadı.\n")
            return
        
        logger.info(f"\n🎯 TOP LOSERS (24 Saatlik Düşüş):\n")
        logger.info(f"{'#':<4} {'Symbol':<15} {'Change %':<12} {'Volume (USD)':<18} {'Price':<12}")
        logger.info(f"{'-'*65}")
        
        for idx, coin in enumerate(losers, 1):
            logger.info(
                f"{idx:<4} {coin['symbol']:<15} "
                f"{coin['price_change_percent']:>+10.2f}% "
                f"${coin['quote_volume']:>15,.0f} "
                f"${coin['last_price']:<12.4f}"
            )
        
        logger.info(f"\n💡 {len(losers)} coin seçildi - Fibonacci analizi için hazır!\n")


if __name__ == "__main__":
    """Test modu"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    scanner = FibonacciScanner(
        drop_threshold=-5.0,  # Test için daha gevşek
        min_volume_usdt=500000,
        top_n=15
    )
    
    losers = scanner.scan_losers()
    scanner.display_results(losers)
