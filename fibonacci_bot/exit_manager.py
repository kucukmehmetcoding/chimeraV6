#!/usr/bin/env python3
"""
Fibonacci Bot - Exit Manager
Çıkış stratejisi yönetimi: +%10 (50% sat), +%25 (kalan 50% sat)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from binance.client import Client
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config import BINANCE_API_KEY, BINANCE_SECRET_KEY

logger = logging.getLogger('fibonacci_bot.exit_manager')


class ExitManager:
    """Çıkış stratejisi yöneticisi"""
    
    def __init__(self, database):
        """
        Args:
            database: FibonacciDatabase instance
        """
        self.db = database
        self.client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        
        # Çıkış hedefleri
        self.TARGET_1 = 0.10  # +%10 kar
        self.TARGET_2 = 0.25  # +%25 kar
        
        # Satış oranları
        self.SELL_RATIO_T1 = 0.50  # Target 1'de %50 sat
        self.SELL_RATIO_T2 = 0.50  # Target 2'de kalan %50 sat
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Güncel fiyatı al"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"❌ {symbol} fiyat hatası: {e}")
            return None
    
    def calculate_profit_percent(self, entry_price: float, current_price: float) -> float:
        """Kar yüzdesini hesapla"""
        return ((current_price - entry_price) / entry_price) * 100
    
    def check_exit_conditions(self, position: Dict, current_price: float) -> Optional[Dict]:
        """Bir pozisyon için çıkış koşullarını kontrol et"""
        symbol = position['symbol']
        avg_cost = position['entry_price']  # Veritabanında 'entry_price' olarak kayıtlı
        remaining_qty = position['quantity']
        
        if remaining_qty <= 0:
            logger.warning(f"⚠️ {symbol}: Kalan miktar 0")
            return None
        
        # Kar yüzdesi
        profit_pct = self.calculate_profit_percent(avg_cost, current_price)
        
        logger.debug(f"   {symbol}: Profit = {profit_pct:+.2f}% (Entry: ${avg_cost:.4f}, Current: ${current_price:.4f})")
        
        # Target 2: +%25 (Kalan %50'yi sat)
        if profit_pct >= self.TARGET_2 * 100:
            sell_quantity = remaining_qty * self.SELL_RATIO_T2
            exit_type = 'TARGET_2'
            
            logger.info(f"🎯 {symbol} TARGET 2 (+%25) tetiklendi!")
            logger.info(f"   Satılacak Miktar: {sell_quantity:.6f} ({self.SELL_RATIO_T2*100:.0f}% of remaining)")
            
            return {
                'symbol': symbol,
                'exit_type': exit_type,
                'exit_price': current_price,
                'quantity_to_sell': sell_quantity,
                'profit_pct': profit_pct,
                'timestamp': datetime.now().isoformat()
            }
        
        # Target 1: +%10 (İlk %50'yi sat)
        elif profit_pct >= self.TARGET_1 * 100:
            # Target 1 daha önce tetiklendi mi?
            # Not: Bu kontrolü position'da 'target1_filled' flag'i ile yapabiliriz
            # Şimdilik her +%10'da %50 sat
            
            sell_quantity = remaining_qty * self.SELL_RATIO_T1
            exit_type = 'TARGET_1'
            
            logger.info(f"🎯 {symbol} TARGET 1 (+%10) tetiklendi!")
            logger.info(f"   Satılacak Miktar: {sell_quantity:.6f} ({self.SELL_RATIO_T1*100:.0f}% of total)")
            
            return {
                'symbol': symbol,
                'exit_type': exit_type,
                'exit_price': current_price,
                'quantity_to_sell': sell_quantity,
                'profit_pct': profit_pct,
                'timestamp': datetime.now().isoformat()
            }
        
        return None
    
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
    
    def execute_partial_exit(self, position_id: int, exit_signal: Dict) -> bool:
        """Kısmi çıkışı gerçek Binance order olarak gönder"""
        try:
            symbol = exit_signal['symbol']
            exit_price = exit_signal['exit_price']
            quantity_sold = exit_signal['quantity_to_sell']
            exit_type = exit_signal['exit_type']
            
            # Lot size kurallarına göre miktarı ayarla
            adjusted_quantity = self.adjust_quantity_for_lot_size(symbol, quantity_sold)
            
            if adjusted_quantity <= 0:
                logger.error(f"❌ {symbol}: Geçersiz miktar: {adjusted_quantity}")
                return False
            
            # Gerçek satış order'ı gönder
            order = self.client.create_order(
                symbol=symbol,
                side=Client.SIDE_SELL,
                type=Client.ORDER_TYPE_MARKET,
                quantity=adjusted_quantity
            )
            
            # Order detaylarını al
            order_id = order['orderId']
            executed_qty = float(order['executedQty'])
            executed_price = float(order['fills'][0]['price']) if order['fills'] else exit_price
            
            # Pozisyonu veritabanına kaydet
            position_data = self.db.close_position(position_id, executed_price)
            
            if position_data:
                logger.info(f"✅ GERÇEK ÇIKIŞ ORDER GÖNDERİLDİ: {symbol}")
                logger.info(f"   Order ID: {order_id}")
                logger.info(f"   Exit Type: {exit_type}")
                logger.info(f"   Exit Price: ${executed_price:.4f}")
                logger.info(f"   Quantity Sold: {executed_qty:.6f}")
                logger.info(f"   PnL: ${position_data['pnl']:.2f} ({position_data['pnl_percent']:.2f}%)")
                return True
            else:
                logger.error(f"❌ {symbol} pozisyon kapatılamadı")
                return False
            
        except Exception as e:
            logger.error(f"❌ Gerçek çıkış order gönderme hatası: {e}")
            return False
    
    def monitor_positions(self) -> List[Dict]:
        """Tüm açık pozisyonları izle ve çıkış sinyallerini kontrol et"""
        try:
            # Açık pozisyonları al
            open_positions = self.db.get_open_positions()
            
            if not open_positions:
                logger.debug("Açık pozisyon yok")
                return []
            
            logger.info(f"\n📊 Exit Monitor: {len(open_positions)} açık pozisyon")
            
            exit_signals = []
            
            for pos in open_positions:
                symbol = pos['symbol']
                
                # Güncel fiyat
                current_price = self.get_current_price(symbol)
                if not current_price:
                    continue
                
                # Çıkış kontrolü
                exit_signal = self.check_exit_conditions(pos, current_price)
                
                if exit_signal:
                    exit_signals.append({
                        'position_id': pos['id'],
                        'signal': exit_signal
                    })
            
            if exit_signals:
                logger.info(f"✅ {len(exit_signals)} çıkış sinyali bulundu")
            else:
                logger.debug("⏸️ Çıkış koşulu sağlanmadı")
            
            return exit_signals
            
        except Exception as e:
            logger.error(f"❌ Pozisyon izleme hatası: {e}")
            return []
    
    def execute_exit_signals(self, exit_signals: List[Dict]) -> int:
        """Çıkış sinyallerini uygula"""
        executed = 0
        
        for item in exit_signals:
            position_id = item['position_id']
            signal = item['signal']
            
            if self.execute_partial_exit(position_id, signal):
                executed += 1
        
        return executed


if __name__ == "__main__":
    """Test modu"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    from database import FibonacciDatabase
    
    db = FibonacciDatabase()
    exit_manager = ExitManager(db)
    
    print("\n" + "="*60)
    print("🎯 EXIT MANAGER TEST")
    print("="*60)
    
    # Pozisyonları izle
    exit_signals = exit_manager.monitor_positions()
    
    print(f"\nÇıkış Sinyalleri: {len(exit_signals)}")
    
    if exit_signals:
        print("\n🚀 Çıkış sinyalleri uygulanıyor...")
        executed = exit_manager.execute_exit_signals(exit_signals)
        print(f"✅ {executed} / {len(exit_signals)} çıkış gerçekleşti")
