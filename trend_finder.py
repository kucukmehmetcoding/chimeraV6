#!/usr/bin/env python3
"""
RSI SCANNER - Tüm Binance Futures coinlerini tarayarak RSI > 65 olanları listeler
Simple and efficient market scanner
"""

import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import sys
import os

# Proje modüllerini ekle
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config import BLACKLISTED_SYMBOLS
from src.data_fetcher.binance_fetcher import get_binance_klines, get_all_futures_usdt_symbols
from src.technical_analyzer.indicators import calculate_indicators

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rsi_scanner.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('rsi_scanner')

class RSIScanner:
    """
    Tüm Binance Futures coinlerini tarar ve RSI > 65 olanları bulur
    """
    
    def __init__(self, rsi_threshold: float = 65.0, timeframe: str = '5m'):
        self.rsi_threshold = rsi_threshold
        self.timeframe = timeframe
        self.high_rsi_coins = []
        
    def get_all_symbols(self) -> List[str]:
        """Binance Futures'daki tüm USDT çiftlerini getir"""
        try:
            symbols = get_all_futures_usdt_symbols()
            if symbols:
                # Blacklist kontrolü
                filtered = [s for s in symbols if not any(bl in s for bl in BLACKLISTED_SYMBOLS)]
                logger.info(f"✅ Toplam {len(filtered)} sembol bulundu (blacklist sonrası)")
                return filtered
            return []
        except Exception as e:
            logger.error(f"❌ Sembol listesi alınamadı: {e}")
            return []
    
    def calculate_rsi(self, symbol: str) -> Optional[Dict]:
        """Bir sembol için RSI hesapla"""
        try:
            # OHLCV verilerini al
            df = get_binance_klines(symbol, self.timeframe, limit=50)
            if df is None or df.empty or len(df) < 20:
                return None
            
            # İndikatörleri hesapla
            df = calculate_indicators(df)
            
            if 'rsi14' not in df.columns:
                return None
            
            latest = df.iloc[-1]
            rsi = latest['rsi14']
            
            if pd.isna(rsi):
                return None
            
            current_price = latest['close']
            
            return {
                'symbol': symbol,
                'rsi': rsi,
                'price': current_price,
                'timeframe': self.timeframe,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.debug(f"⚠️ {symbol} RSI hesaplanamadı: {e}")
            return None
    
    def scan_market(self) -> List[Dict]:
        """Tüm marketi tarayarak RSI > threshold olanları bul"""
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 RSI SCANNER BAŞLATILIYOR...")
        logger.info(f"   RSI Eşiği: > {self.rsi_threshold}")
        logger.info(f"   Timeframe: {self.timeframe}")
        logger.info(f"{'='*80}\n")
        
        symbols = self.get_all_symbols()
        if not symbols:
            logger.error("❌ Sembol listesi boş!")
            return []
        
        logger.info(f"📊 {len(symbols)} sembol taranacak...\n")
        
        high_rsi_coins = []
        scanned = 0
        errors = 0
        
        for symbol in symbols:
            scanned += 1
            
            # Progress log her 50 sembolde bir
            if scanned % 50 == 0:
                logger.info(f"   📈 İlerleme: {scanned}/{len(symbols)} ({scanned/len(symbols)*100:.1f}%)")
            
            result = self.calculate_rsi(symbol)
            
            if result is None:
                errors += 1
                continue
            
            # RSI kontrolü
            if result['rsi'] > self.rsi_threshold:
                high_rsi_coins.append(result)
                logger.info(f"✅ BULUNDU: {result['symbol']} - RSI: {result['rsi']:.2f} | Fiyat: ${result['price']:.4f}")
        
        # Sonuçları sırala (RSI'a göre azalan)
        high_rsi_coins.sort(key=lambda x: x['rsi'], reverse=True)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ TARAMA TAMAMLANDI!")
        logger.info(f"   Taranan: {scanned} sembol")
        logger.info(f"   Hata: {errors} sembol")
        logger.info(f"   RSI > {self.rsi_threshold}: {len(high_rsi_coins)} coin")
        logger.info(f"{'='*80}\n")
        
        return high_rsi_coins
    
    def display_results(self, results: List[Dict]):
        """Sonuçları güzel formatta göster"""
        if not results:
            logger.info("📉 RSI eşiğinin üzerinde coin bulunamadı.\n")
            return
        
        logger.info(f"\n🎯 RSI > {self.rsi_threshold} OLAN COİNLER:\n")
        logger.info(f"{'#':<4} {'Symbol':<15} {'RSI':<10} {'Fiyat':<15} {'Timeframe':<10}")
        logger.info(f"{'-'*60}")
        
        for idx, coin in enumerate(results, 1):
            logger.info(
                f"{idx:<4} {coin['symbol']:<15} {coin['rsi']:<10.2f} ${coin['price']:<14.4f} {coin['timeframe']:<10}"
            )
        
        logger.info(f"\n💡 Toplam {len(results)} coin bulundu!")
        logger.info(f"⏰ Tarama zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

def main():
    """Ana fonksiyon"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RSI Scanner - Binance Futures Market Scanner')
    parser.add_argument('--rsi', type=float, default=65.0, help='RSI eşiği (default: 65.0)')
    parser.add_argument('--timeframe', type=str, default='5m', 
                        choices=['1m', '5m', '15m', '1h', '4h', '1d'],
                        help='Timeframe (default: 5m)')
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔍 RSI SCANNER - Binance Futures Market Scanner")
    print("=" * 80)
    print(f"📊 RSI Eşiği: > {args.rsi}")
    print(f"⏰ Timeframe: {args.timeframe}")
    print("=" * 80)
    print()
    
    try:
        scanner = RSIScanner(rsi_threshold=args.rsi, timeframe=args.timeframe)
        results = scanner.scan_market()
        scanner.display_results(results)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"❌ Sistem hatası: {e}", exc_info=True)

if __name__ == "__main__":
    main()
