#!/usr/bin/env python3
"""
Fibonacci Bot - Fibonacci Calculator
Swing High/Low tespiti ve Fibonacci retracement seviyeleri hesaplama
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional
from binance.client import Client
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config import BINANCE_API_KEY, BINANCE_SECRET_KEY
from src.technical_analyzer.indicators import calculate_indicators

logger = logging.getLogger('fibonacci_bot.calculator')


class FibonacciCalculator:
    """Fibonacci retracement seviyeleri hesaplayıcı"""
    
    def __init__(self, lookback_days: int = 90, adx_threshold: float = 40.0):
        """
        Args:
            lookback_days: Swing High/Low için geriye bakış süresi (gün)
            adx_threshold: ADX eşiği (üstündeyse coin atlanır)
        """
        self.client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        self.lookback_days = lookback_days
        self.adx_threshold = adx_threshold
    
    def get_historical_data(self, symbol: str, days: int = 90) -> Optional[pd.DataFrame]:
        """Geçmiş OHLCV verilerini al"""
        try:
            # Binance limit: 1000 candle
            # 1 günlük mum için 90 gün = 90 candle
            interval = Client.KLINE_INTERVAL_1DAY
            limit = days
            
            klines = self.client.get_historical_klines(
                symbol,
                interval,
                f"{days} days ago UTC"
            )
            
            if not klines:
                logger.warning(f"⚠️ {symbol}: Veri alınamadı")
                return None
            
            # DataFrame oluştur
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Tip dönüşümleri
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            # Sadece gerekli kolonlar
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            logger.debug(f"✅ {symbol}: {len(df)} günlük veri alındı")
            return df
            
        except Exception as e:
            logger.error(f"❌ {symbol} veri hatası: {e}")
            return None
    
    def find_swing_high_low(self, df: pd.DataFrame) -> Dict:
        """Swing High ve Swing Low tespiti"""
        if df is None or len(df) < 30:
            return {}
        
        # Swing High: Son 90 günün en yükseği
        swing_high_idx = df['high'].idxmax()
        swing_high = df.loc[swing_high_idx, 'high']
        swing_high_date = df.loc[swing_high_idx, 'timestamp']
        
        # Swing Low: Swing High'dan SONRA en düşük
        after_high = df.loc[swing_high_idx:]
        
        if len(after_high) < 5:  # En az 5 gün olmalı
            logger.warning(f"⚠️ Swing High çok yakın, yeterli Swing Low yok")
            return {}
        
        swing_low_idx = after_high['low'].idxmin()
        swing_low = after_high.loc[swing_low_idx, 'low']
        swing_low_date = after_high.loc[swing_low_idx, 'timestamp']
        
        return {
            'swing_high': swing_high,
            'swing_high_date': swing_high_date.isoformat(),
            'swing_high_idx': swing_high_idx,
            'swing_low': swing_low,
            'swing_low_date': swing_low_date.isoformat(),
            'swing_low_idx': swing_low_idx
        }
    
    def calculate_fibonacci_levels(self, swing_high: float, swing_low: float) -> Dict:
        """Fibonacci retracement seviyelerini hesapla"""
        if swing_high <= swing_low:
            logger.error(f"❌ Geçersiz Swing: High ({swing_high}) <= Low ({swing_low})")
            return {}
        
        diff = swing_high - swing_low
        
        # Fibonacci seviyeleri
        level_618 = swing_high - (diff * 0.618)
        level_786 = swing_high - (diff * 0.786)
        level_1000 = swing_low  # %100 retrace
        
        return {
            'level_618': level_618,
            'level_786': level_786,
            'level_1000': level_1000,
            'swing_range': diff,
            'swing_range_percent': (diff / swing_high) * 100
        }
    
    def calculate_adx(self, df: pd.DataFrame) -> float:
        """ADX(14) hesapla - Trend gücü göstergesi"""
        try:
            # İndikatörleri hesapla
            df_with_indicators = calculate_indicators(df)
            
            if 'adx14' not in df_with_indicators.columns:
                logger.warning("⚠️ ADX hesaplanamadı")
                return 0.0
            
            # Son ADX değeri
            adx = df_with_indicators['adx14'].iloc[-1]
            
            if pd.isna(adx):
                return 0.0
            
            return float(adx)
            
        except Exception as e:
            logger.error(f"❌ ADX hesaplama hatası: {e}")
            return 0.0
    
    def analyze_coin(self, symbol: str) -> Optional[Dict]:
        """Bir coin için tam Fibonacci analizi"""
        logger.info(f"\n📊 Fibonacci Analizi: {symbol}")
        
        # 1. Geçmiş veri al
        df = self.get_historical_data(symbol, self.lookback_days)
        if df is None or df.empty:
            logger.warning(f"   ❌ Veri alınamadı")
            return None
        
        # 2. Swing High/Low bul
        swing_data = self.find_swing_high_low(df)
        if not swing_data:
            logger.warning(f"   ❌ Swing High/Low bulunamadı")
            return None
        
        # 3. Fibonacci seviyeleri hesapla
        fib_levels = self.calculate_fibonacci_levels(
            swing_data['swing_high'],
            swing_data['swing_low']
        )
        
        if not fib_levels:
            logger.warning(f"   ❌ Fibonacci hesaplanamadı")
            return None
        
        # 4. ADX hesapla (trend gücü)
        adx = self.calculate_adx(df)
        
        # 5. ADX filtresi
        if adx > self.adx_threshold:
            logger.warning(f"   ❌ ADX çok yüksek ({adx:.1f} > {self.adx_threshold}) - Güçlü trend riski")
            return None
        
        # 6. Güncel fiyat
        current_price = df['close'].iloc[-1]
        
        # 7. Sonuçları birleştir
        result = {
            'symbol': symbol,
            'swing_high': swing_data['swing_high'],
            'swing_low': swing_data['swing_low'],
            'swing_high_date': swing_data['swing_high_date'],
            'swing_low_date': swing_data['swing_low_date'],
            'level_618': fib_levels['level_618'],
            'level_786': fib_levels['level_786'],
            'level_1000': fib_levels['level_1000'],
            'current_price': current_price,
            'adx': adx,
            'swing_range': fib_levels['swing_range'],
            'swing_range_percent': fib_levels['swing_range_percent'],
            'calculated_at': datetime.now().isoformat()
        }
        
        # 8. Log
        logger.info(f"   ✅ Swing High: ${swing_data['swing_high']:.4f} ({swing_data['swing_high_date'][:10]})")
        logger.info(f"   ✅ Swing Low:  ${swing_data['swing_low']:.4f} ({swing_data['swing_low_date'][:10]})")
        logger.info(f"   📏 Range: ${fib_levels['swing_range']:.4f} ({fib_levels['swing_range_percent']:.2f}%)")
        logger.info(f"   🎯 Fib 0.618: ${fib_levels['level_618']:.4f}")
        logger.info(f"   🎯 Fib 0.786: ${fib_levels['level_786']:.4f}")
        logger.info(f"   🎯 Fib 1.000: ${fib_levels['level_1000']:.4f}")
        logger.info(f"   📊 Current:   ${current_price:.4f}")
        logger.info(f"   💪 ADX(14):   {adx:.1f}")
        
        return result
    
    def analyze_multiple_coins(self, symbols: list) -> Dict[str, Dict]:
        """Birden fazla coin için Fibonacci analizi"""
        results = {}
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 FİBONACCI CALCULATOR BAŞLATILIYOR...")
        logger.info(f"   Lookback: {self.lookback_days} gün")
        logger.info(f"   ADX Threshold: {self.adx_threshold}")
        logger.info(f"   Coin Sayısı: {len(symbols)}")
        logger.info(f"{'='*60}")
        
        for symbol in symbols:
            result = self.analyze_coin(symbol)
            if result:
                results[symbol] = result
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ FİBONACCI ANALİZİ TAMAMLANDI!")
        logger.info(f"   Başarılı: {len(results)} / {len(symbols)} coin")
        logger.info(f"{'='*60}\n")
        
        return results


if __name__ == "__main__":
    """Test modu"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    calculator = FibonacciCalculator(lookback_days=90, adx_threshold=40.0)
    
    # Test coinleri
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    results = calculator.analyze_multiple_coins(test_symbols)
    
    print("\n" + "="*60)
    print("📊 FİBONACCI SEVİYELERİ ÖZETİ")
    print("="*60)
    
    for symbol, data in results.items():
        print(f"\n{symbol}:")
        print(f"  Current: ${data['current_price']:.4f}")
        print(f"  Fib 0.618: ${data['level_618']:.4f}")
        print(f"  Fib 0.786: ${data['level_786']:.4f}")
        print(f"  Fib 1.000: ${data['level_1000']:.4f}")
        print(f"  ADX: {data['adx']:.1f}")
