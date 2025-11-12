# src/trade_manager/smart_executor.py
"""
v10.6: SMART EXECUTION - Phase 4
=================================

Bu modül, confirmation layer'dan gelen skorlara göre optimal emir stratejisi uygular.

Execution Strategies:
1. MARKET (Score ≥70): Hızlı giriş, piyasa fiyatından tüm pozisyon
2. PARTIAL (Score 50-69): 50% market + 50% limit, dengeli yaklaşım
3. LIMIT (Score <50): Tümü limit, agresif fiyat bekle

Price Calculation:
- Market: Current price
- Limit LONG: Current price - 0.1% (daha ucuz bekle)
- Limit SHORT: Current price + 0.1% (daha pahalı bekle)
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class SmartExecutor:
    """
    Akıllı emir yürütücü - Skor bazlı strateji
    
    İş Akışı:
    1. Confirmation layer'dan skor al (0-100)
    2. Strategy belirle (market/partial/limit)
    3. Fiyat hesapla
    4. Order tracker'a kaydet
    5. Execute (simulated or real)
    """
    
    def __init__(self, config):
        self.config = config
        
        # Strategy thresholds (confirmation_layer ile uyumlu)
        self.market_threshold = 70   # ≥70: Market
        self.partial_threshold = 50  # 50-69: Partial
        
        # Price offset for limit orders (%)
        self.limit_offset_pct = 0.1  # 0.1% = 10 basis points
        
        # Partial split ratio
        self.partial_market_ratio = 0.5  # 50% market
        self.partial_limit_ratio = 0.5   # 50% limit
        
        # Statistics
        self.execution_count = 0
        self.market_count = 0
        self.partial_count = 0
        self.limit_count = 0
        
        logger.info("🎯 SmartExecutor initialized")
        logger.info(f"   Market threshold: {self.market_threshold}")
        logger.info(f"   Partial threshold: {self.partial_threshold}")
        logger.info(f"   Limit offset: {self.limit_offset_pct}%")
    
    def execute_signal(
        self,
        symbol: str,
        signal_direction: str,  # 'bullish' or 'bearish'
        confirmation_result: Dict,  # From confirmation_layer.analyze()
        position_size: float,
        current_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict:
        """
        Sinyal için emir stratejisi uygula
        
        Args:
            symbol: Trading pair
            signal_direction: 'bullish' (LONG) or 'bearish' (SHORT)
            confirmation_result: Confirmation layer sonucu (score, strategy, etc.)
            position_size: Pozisyon büyüklüğü
            current_price: Mevcut piyasa fiyatı
            stop_loss: Stop loss fiyatı
            take_profit: Take profit fiyatı
        
        Returns:
            {
                'success': True/False,
                'execution_type': 'market'/'partial'/'limit',
                'orders': [
                    {
                        'order_id': 'sim_12345',
                        'type': 'market'/'limit',
                        'side': 'BUY'/'SELL',
                        'quantity': 0.5,
                        'price': 103500.0,
                        'status': 'FILLED'/'NEW',
                        'timestamp': '...'
                    }
                ],
                'total_quantity': 1.0,
                'filled_quantity': 0.5,
                'average_entry': 103500.0,
                'message': '...'
            }
        """
        try:
            # Extract score and strategy
            score = confirmation_result.get('score', 0)
            recommended_strategy = confirmation_result.get('execution_strategy', 'limit')
            
            logger.info(f"🎯 Executing signal for {symbol}")
            logger.info(f"   Direction: {signal_direction.upper()}")
            logger.info(f"   Score: {score}/100")
            logger.info(f"   Recommended Strategy: {recommended_strategy}")
            logger.info(f"   Position Size: {position_size}")
            logger.info(f"   Current Price: ${current_price:.2f}")
            
            # Determine side
            side = 'BUY' if signal_direction == 'bullish' else 'SELL'
            
            # Execute based on strategy
            if recommended_strategy == 'market':
                result = self._execute_market(
                    symbol, side, position_size, current_price, 
                    stop_loss, take_profit
                )
            
            elif recommended_strategy == 'partial':
                result = self._execute_partial(
                    symbol, side, position_size, current_price, 
                    stop_loss, take_profit
                )
            
            else:  # limit
                result = self._execute_limit(
                    symbol, side, position_size, current_price, 
                    stop_loss, take_profit
                )
            
            # Update statistics
            self.execution_count += 1
            if recommended_strategy == 'market':
                self.market_count += 1
            elif recommended_strategy == 'partial':
                self.partial_count += 1
            else:
                self.limit_count += 1
            
            # Add metadata
            result['signal_direction'] = signal_direction
            result['confirmation_score'] = score
            result['stop_loss'] = stop_loss
            result['take_profit'] = take_profit
            
            logger.info(f"✅ Execution complete: {result['execution_type']}")
            logger.info(f"   Total quantity: {result['total_quantity']}")
            logger.info(f"   Filled: {result['filled_quantity']}")
            logger.info(f"   Average entry: ${result['average_entry']:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Execution error for {symbol}: {e}", exc_info=True)
            return {
                'success': False,
                'execution_type': 'error',
                'orders': [],
                'total_quantity': 0,
                'filled_quantity': 0,
                'average_entry': 0,
                'message': f"Execution failed: {e}"
            }
    
    def _execute_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict:
        """Market order: Tüm pozisyon piyasa fiyatından"""
        logger.info(f"📈 MARKET ORDER: {side} {quantity} {symbol} @ ${price:.2f}")
        
        # Simulated market order (instant fill)
        order = {
            'order_id': f"sim_market_{int(time.time() * 1000)}",
            'type': 'market',
            'side': side,
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'status': 'FILLED',
            'filled_quantity': quantity,
            'timestamp': datetime.now().isoformat()
        }
        
        return {
            'success': True,
            'execution_type': 'market',
            'orders': [order],
            'total_quantity': quantity,
            'filled_quantity': quantity,
            'average_entry': price,
            'message': f'Market order filled: {quantity} @ ${price:.2f}'
        }
    
    def _execute_partial(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict:
        """Partial fill: 50% market + 50% limit"""
        logger.info(f"⚖️ PARTIAL FILL: {side} {quantity} {symbol}")
        
        # Split quantity
        market_qty = quantity * self.partial_market_ratio
        limit_qty = quantity * self.partial_limit_ratio
        
        logger.info(f"   Market: {market_qty:.6f} @ ${price:.2f}")
        
        # Calculate limit price
        if side == 'BUY':
            # LONG: Limit daha ucuz (price - offset)
            limit_price = price * (1 - self.limit_offset_pct / 100)
        else:
            # SHORT: Limit daha pahalı (price + offset)
            limit_price = price * (1 + self.limit_offset_pct / 100)
        
        logger.info(f"   Limit: {limit_qty:.6f} @ ${limit_price:.2f}")
        
        # Market order (instant fill)
        market_order = {
            'order_id': f"sim_market_{int(time.time() * 1000)}",
            'type': 'market',
            'side': side,
            'symbol': symbol,
            'quantity': market_qty,
            'price': price,
            'status': 'FILLED',
            'filled_quantity': market_qty,
            'timestamp': datetime.now().isoformat()
        }
        
        # Limit order (pending)
        limit_order = {
            'order_id': f"sim_limit_{int(time.time() * 1000) + 1}",
            'type': 'limit',
            'side': side,
            'symbol': symbol,
            'quantity': limit_qty,
            'price': limit_price,
            'status': 'NEW',  # Pending fill
            'filled_quantity': 0,
            'timestamp': datetime.now().isoformat(),
            'timeout_at': time.time() + 300  # 5 min timeout
        }
        
        return {
            'success': True,
            'execution_type': 'partial',
            'orders': [market_order, limit_order],
            'total_quantity': quantity,
            'filled_quantity': market_qty,  # Only market filled initially
            'average_entry': price,  # Will update when limit fills
            'pending_quantity': limit_qty,
            'limit_price': limit_price,
            'message': f'Partial fill: {market_qty:.6f} filled @ ${price:.2f}, '
                      f'{limit_qty:.6f} pending @ ${limit_price:.2f}'
        }
    
    def _execute_limit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict:
        """Limit order: Tüm pozisyon limit fiyatından"""
        # Calculate limit price
        if side == 'BUY':
            limit_price = price * (1 - self.limit_offset_pct / 100)
        else:
            limit_price = price * (1 + self.limit_offset_pct / 100)
        
        logger.info(f"📊 LIMIT ORDER: {side} {quantity} {symbol} @ ${limit_price:.2f}")
        logger.info(f"   Current market: ${price:.2f}")
        logger.info(f"   Waiting for {self.limit_offset_pct}% better price")
        
        # Limit order (pending)
        order = {
            'order_id': f"sim_limit_{int(time.time() * 1000)}",
            'type': 'limit',
            'side': side,
            'symbol': symbol,
            'quantity': quantity,
            'price': limit_price,
            'status': 'NEW',
            'filled_quantity': 0,
            'timestamp': datetime.now().isoformat(),
            'timeout_at': time.time() + 300  # 5 min timeout
        }
        
        return {
            'success': True,
            'execution_type': 'limit',
            'orders': [order],
            'total_quantity': quantity,
            'filled_quantity': 0,  # Not filled yet
            'average_entry': 0,  # Will update when filled
            'pending_quantity': quantity,
            'limit_price': limit_price,
            'message': f'Limit order placed: {quantity} @ ${limit_price:.2f} '
                      f'(waiting for {self.limit_offset_pct}% better than ${price:.2f})'
        }
    
    def get_stats(self) -> Dict:
        """İstatistikleri döndür"""
        total = self.execution_count
        
        return {
            'total_executions': total,
            'market_count': self.market_count,
            'partial_count': self.partial_count,
            'limit_count': self.limit_count,
            'market_pct': (self.market_count / total * 100) if total > 0 else 0,
            'partial_pct': (self.partial_count / total * 100) if total > 0 else 0,
            'limit_pct': (self.limit_count / total * 100) if total > 0 else 0
        }


# Module-level singleton
_smart_executor_instance: Optional[SmartExecutor] = None


def get_smart_executor(config) -> SmartExecutor:
    """Get or create SmartExecutor instance (singleton)"""
    global _smart_executor_instance
    
    if _smart_executor_instance is None:
        _smart_executor_instance = SmartExecutor(config)
    
    return _smart_executor_instance


def reset_smart_executor():
    """Reset singleton instance (for testing)"""
    global _smart_executor_instance
    _smart_executor_instance = None
