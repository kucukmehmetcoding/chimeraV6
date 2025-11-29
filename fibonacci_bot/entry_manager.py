#!/usr/bin/env python3
"""
Fibonacci Bot - Entry Manager
Giriş sinyali validasyonu ve pozisyon açma mantığı
TA-Lib candlestick pattern recognition ile destekli
"""

import logging
import talib
import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime
from binance.client import Client
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config import BINANCE_API_KEY, BINANCE_SECRET_KEY
from src.technical_analyzer.indicators import calculate_indicators

logger = logging.getLogger('fibonacci_bot.entry_manager')


class EntryManager:
    """Giriş sinyali validasyonu ve pozisyon açma yöneticisi"""
    
    def __init__(self, database):
        """
        Args:
            database: FibonacciDatabase instance
        """
        self.db = database
        self.client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        
        # Seviye bazlı bütçe dağılımı (%)
        self.BUDGET_DISTRIBUTION = {
            0.618: 0.20,  # %20
            0.786: 0.35,  # %35
            1.000: 0.45   # %45
        }
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Güncel fiyatı al"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"❌ {symbol} fiyat hatası: {e}")
            return None
    
    def get_recent_candles(self, symbol: str, interval: str = '1h', limit: int = 100) -> Optional[pd.DataFrame]:
        """Son mumları al (pattern tespiti için)"""
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            if not klines:
                return None
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            
            return df[['open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            logger.error(f"❌ {symbol} mum verisi hatası: {e}")
            return None
    
    def detect_bullish_patterns(self, df: pd.DataFrame) -> Dict[str, bool]:
        """TA-Lib ile bullish candlestick pattern tespiti"""
        if df is None or len(df) < 10:
            return {}
        
        open_prices = df['open'].values
        high_prices = df['high'].values
        low_prices = df['low'].values
        close_prices = df['close'].values
        
        patterns = {}
        
        try:
            # Hammer (Çekiç)
            hammer = talib.CDLHAMMER(open_prices, high_prices, low_prices, close_prices)
            patterns['hammer'] = int(hammer[-1]) > 0  # Son mum
            
            # Inverted Hammer (Ters Çekiç)
            inv_hammer = talib.CDLINVERTEDHAMMER(open_prices, high_prices, low_prices, close_prices)
            patterns['inverted_hammer'] = int(inv_hammer[-1]) > 0
            
            # Doji
            doji = talib.CDLDOJI(open_prices, high_prices, low_prices, close_prices)
            patterns['doji'] = int(doji[-1]) != 0  # Doji var mı
            
            # Dragonfly Doji
            dragonfly_doji = talib.CDLDRAGONFLYDOJI(open_prices, high_prices, low_prices, close_prices)
            patterns['dragonfly_doji'] = int(dragonfly_doji[-1]) > 0
            
            # Bullish Engulfing (Yutan Mum)
            engulfing = talib.CDLENGULFING(open_prices, high_prices, low_prices, close_prices)
            patterns['bullish_engulfing'] = int(engulfing[-1]) > 0
            
            # Morning Star (Sabah Yıldızı)
            morning_star = talib.CDLMORNINGSTAR(open_prices, high_prices, low_prices, close_prices)
            patterns['morning_star'] = int(morning_star[-1]) > 0
            
            # Piercing Pattern (Delici Model)
            piercing = talib.CDLPIERCING(open_prices, high_prices, low_prices, close_prices)
            patterns['piercing'] = int(piercing[-1]) > 0
            
        except Exception as e:
            logger.error(f"❌ Pattern tespit hatası: {e}")
            return {}
        
        return patterns
    
    def calculate_rsi(self, df: pd.DataFrame) -> float:
        """RSI(14) hesapla"""
        try:
            df_with_indicators = calculate_indicators(df)
            
            if 'rsi14' not in df_with_indicators.columns:
                logger.warning("⚠️ RSI hesaplanamadı")
                return 50.0  # Nötr
            
            rsi = df_with_indicators['rsi14'].iloc[-1]
            
            if pd.isna(rsi):
                return 50.0
            
            return float(rsi)
            
        except Exception as e:
            logger.error(f"❌ RSI hesaplama hatası: {e}")
            return 50.0
    
    def check_level_618_entry(self, current_price: float, fib_level: float, rsi: float, patterns: Dict) -> bool:
        """0.618 seviyesi için giriş koşulları"""
        # Fiyat kontrolü: Level civarında mı? (±1.0% tolerance)
        price_diff_pct = abs((current_price - fib_level) / fib_level) * 100
        if price_diff_pct > 1.0:
            logger.debug(f"   ❌ 0.618 Fiyat tolerans dışında: Fark={price_diff_pct:.2f}%")
            return False

        # RSI < 35 (aşırı satım)
        if rsi >= 35:
            logger.debug(f"   ❌ 0.618 RSI yetersiz ({rsi:.1f} >= 35)")
            return False

        # Bullish pattern gerekli (Hammer veya Doji)
        if not (patterns.get('hammer') or patterns.get('doji') or 
                patterns.get('dragonfly_doji') or patterns.get('inverted_hammer')):
            logger.debug("   ❌ 0.618 Bullish pattern yok")
            return False

        logger.info(f"   ✅ 0.618 Giriş Sinyali: RSI={rsi:.1f}, Pattern={patterns}")
        return True
    
    def check_level_786_entry(self, current_price: float, fib_level: float, rsi: float) -> bool:
        """0.786 seviyesi için giriş koşulları"""
        # Fiyat kontrolü
        price_diff_pct = abs((current_price - fib_level) / fib_level) * 100
        if price_diff_pct > 1.5:
            logger.debug(f"   ❌ 0.786 Fiyat tolerans dışında: Fark={price_diff_pct:.2f}%")
            return False

        # RSI < 40
        if rsi >= 40:
            logger.debug(f"   ❌ 0.786 RSI yetersiz ({rsi:.1f} >= 40)")
            return False

        logger.info(f"   ✅ 0.786 Giriş Sinyali: RSI={rsi:.1f}")
        return True
    
    def check_level_1000_entry(self, current_price: float, fib_level: float) -> bool:
        """1.000 seviyesi için giriş koşulları (koşulsuz)"""
        # Fiyat kontrolü - 1.000 seviyesi için daha geniş tolerans
        price_diff_pct = abs((current_price - fib_level) / fib_level) * 100
        if price_diff_pct > 2.0:
            logger.debug(f"   ❌ 1.000 Fiyat tolerans dışında: Fark={price_diff_pct:.2f}% (Current: ${current_price:.4f}, Fib: ${fib_level:.4f})")
            return False
        
        logger.info(f"   ✅ 1.000 Giriş Sinyali: Koşulsuz alım (Fark: {price_diff_pct:.2f}%)")
        return True
    
    def calculate_position_size(
        self, 
        symbol: str, 
        fib_level: float, 
        current_price: float,
        max_budget_per_coin: float = 100.0
    ) -> float:
        """Pozisyon büyüklüğünü hesapla"""
        # Fibonacci seviyesine göre bütçe dağılımı
        level_key = None
        if abs(current_price - fib_level) / fib_level < 0.005:  # %0.5 tolerance
            # En yakın Fibonacci seviyesini bul
            for key in [0.618, 0.786, 1.000]:
                if abs(current_price / fib_level - 1.0) < 0.01:  # Yaklaşık eşit
                    level_key = key
                    break
        
        if level_key is None:
            # Varsayılan: Eşit dağılım
            budget_ratio = 0.33
        else:
            budget_ratio = self.BUDGET_DISTRIBUTION.get(level_key, 0.33)
        
        # Bu seviye için bütçe
        level_budget = max_budget_per_coin * budget_ratio
        
        # Miktar hesapla
        quantity = level_budget / current_price
        
        return quantity
    
    def check_entry_signals(
        self, 
        symbol: str, 
        fib_data: Dict,
        max_budget_per_coin: float = 100.0
    ) -> List[Dict]:
        """Bir coin için tüm Fibonacci seviyelerinde giriş kontrolü"""
        logger.info(f"\n🔍 Entry Check: {symbol}")
        
        # 1. Güncel fiyat
        current_price = self.get_current_price(symbol)
        if not current_price:
            logger.warning("   ❌ Fiyat alınamadı")
            return []
        
        logger.info(f"   Current Price: ${current_price:.4f}")
        
        # 2. Son mumları al
        df = self.get_recent_candles(symbol, interval='1h', limit=100)
        if df is None or df.empty:
            logger.warning("   ❌ Mum verisi alınamadı")
            return []
        
        # 3. RSI hesapla
        rsi = self.calculate_rsi(df)
        logger.info(f"   RSI(14): {rsi:.1f}")
        
        # 4. Bullish pattern tespit
        patterns = self.detect_bullish_patterns(df)
        detected_patterns = [k for k, v in patterns.items() if v]
        if detected_patterns:
            logger.info(f"   📊 Patterns: {', '.join(detected_patterns)}")
        else:
            logger.debug("   ❌ Bullish pattern bulunamadı")
        
        # 5. Her Fibonacci seviyesini kontrol et
        signals = []
        
        # Level 0.618
        if self.check_level_618_entry(current_price, fib_data['level_618'], rsi, patterns):
            logger.debug("   ✅ 0.618 seviyesi giriş koşulları sağlandı")
            quantity = self.calculate_position_size(symbol, fib_data['level_618'], current_price, max_budget_per_coin)
            signals.append({
                'symbol': symbol,
                'fib_level': 0.618,
                'entry_price': current_price,
                'quantity': quantity,
                'budget': quantity * current_price,
                'rsi': rsi,
                'patterns': detected_patterns,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.debug("   ❌ 0.618 seviyesi giriş koşulları sağlanmadı")
        
        # Level 0.786
        if self.check_level_786_entry(current_price, fib_data['level_786'], rsi):
            logger.debug("   ✅ 0.786 seviyesi giriş koşulları sağlandı")
            quantity = self.calculate_position_size(symbol, fib_data['level_786'], current_price, max_budget_per_coin)
            signals.append({
                'symbol': symbol,
                'fib_level': 0.786,
                'entry_price': current_price,
                'quantity': quantity,
                'budget': quantity * current_price,
                'rsi': rsi,
                'patterns': detected_patterns,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.debug("   ❌ 0.786 seviyesi giriş koşulları sağlanmadı")
        
        # Level 1.000
        if self.check_level_1000_entry(current_price, fib_data['level_1000']):
            logger.debug("   ✅ 1.000 seviyesi giriş koşulları sağlandı")
            quantity = self.calculate_position_size(symbol, fib_data['level_1000'], current_price, max_budget_per_coin)
            signals.append({
                'symbol': symbol,
                'fib_level': 1.000,
                'entry_price': current_price,
                'quantity': quantity,
                'budget': quantity * current_price,
                'rsi': rsi,
                'patterns': detected_patterns,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.debug("   ❌ 1.000 seviyesi giriş koşulları sağlanmadı")
        
        if signals:
            logger.info(f"   ✅ {len(signals)} giriş sinyali bulundu")
        else:
            logger.debug("   ⏸️ Giriş koşulları sağlanmadı")
        
        return signals
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Symbol bilgilerini al (lot size, min notional, etc.)"""
        try:
            info = self.client.get_symbol_info(symbol)
            return info
        except Exception as e:
            logger.error(f"❌ {symbol} bilgisi alınamadı: {e}")
            return None
    
    def adjust_quantity_for_lot_size(self, symbol: str, quantity: float) -> float:
        """Lot size kurallarına göre miktarı ayarla"""
        try:
            info = self.get_symbol_info(symbol)
            if not info:
                return quantity
            
            # Lot size filtresini bul
            lot_size_filter = next((f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            if not lot_size_filter:
                return quantity
            
            min_qty = float(lot_size_filter['minQty'])
            max_qty = float(lot_size_filter['maxQty'])
            step_size = float(lot_size_filter['stepSize'])
            
            # Minimum lot size kontrolü
            if quantity < min_qty:
                logger.warning(f"⚠️ {symbol}: Miktar minimum lot size'tan küçük ({quantity:.6f} < {min_qty:.6f})")
                return min_qty
            
            # Maximum lot size kontrolü
            if quantity > max_qty:
                logger.warning(f"⚠️ {symbol}: Miktar maximum lot size'tan büyük ({quantity:.6f} > {max_qty:.6f})")
                return max_qty
            
            # Step size'a göre yuvarla
            adjusted_qty = round(quantity / step_size) * step_size
            logger.debug(f"   {symbol}: Miktar {quantity:.6f} → {adjusted_qty:.6f} (step: {step_size})")
            
            return adjusted_qty
            
        except Exception as e:
            logger.error(f"❌ Lot size ayarlama hatası: {e}")
            return quantity
    
    def execute_entry(self, signal: Dict) -> bool:
        """Giriş sinyalini gerçek Binance order olarak gönder"""
        try:
            symbol = signal['symbol']
            quantity = signal['quantity']
            current_price = signal['entry_price']
            
            # Lot size kurallarına göre miktarı ayarla
            adjusted_quantity = self.adjust_quantity_for_lot_size(symbol, quantity)
            
            if adjusted_quantity <= 0:
                logger.error(f"❌ {symbol}: Geçersiz miktar: {adjusted_quantity}")
                return False
            
            # Market order gönder
            order = self.client.create_order(
                symbol=symbol,
                side=Client.SIDE_BUY,
                type=Client.ORDER_TYPE_MARKET,
                quantity=adjusted_quantity
            )
            
            # Order detaylarını al
            order_id = order['orderId']
            executed_qty = float(order['executedQty'])
            executed_price = float(order['fills'][0]['price']) if order['fills'] else current_price
            
            # Pozisyonu veritabanına kaydet
            self.db.add_position(
                symbol=symbol,
                level=signal['fib_level'],
                entry_price=executed_price,
                quantity=executed_qty,
                spent_usd=executed_qty * executed_price
            )
            
            logger.info(f"✅ GERÇEK ORDER GÖNDERİLDİ: {symbol} @ ${executed_price:.4f}")
            logger.info(f"   Order ID: {order_id}")
            logger.info(f"   Miktar: {executed_qty:.6f}")
            logger.info(f"   Bütçe: ${executed_qty * executed_price:.2f}")
            logger.info(f"   Fib Level: {signal['fib_level']}")
            logger.info(f"   RSI: {signal['rsi']:.1f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Gerçek order gönderme hatası: {e}")
            return False


if __name__ == "__main__":
    """Test modu"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    from database import FibonacciDatabase
    
    db = FibonacciDatabase()
    entry_manager = EntryManager(db)
    
    # Test Fibonacci data (örnek)
    test_fib_data = {
        'level_618': 95000.0,
        'level_786': 93000.0,
        'level_1000': 90000.0
    }
    
    print("\n" + "="*60)
    print("🎯 ENTRY MANAGER TEST")
    print("="*60)
    
    signals = entry_manager.check_entry_signals('BTCUSDT', test_fib_data, max_budget_per_coin=100.0)
    
    print(f"\n✅ Bulunan Sinyaller: {len(signals)}")
    for sig in signals:
        print(f"  - {sig['symbol']} @ Fib {sig['fib_level']}: ${sig['entry_price']:.4f} ({sig['quantity']:.4f} adet)")
