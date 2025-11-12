# src/trade_manager/order_tracker.py
"""
v10.6: ORDER LIFECYCLE MANAGEMENT - Phase 5
=============================================

Bu modül, limit emirlerinin yaşam döngüsünü yönetir.

Özellikler:
- Order tracking: Her limit emrinin durumunu izle
- Timeout handling: 5 dakika dolunca otomatik iptal
- Partial fill aggregation: Birden fazla fill → tek pozisyon
- Fill simulation: Piyasa fiyatı limit'e gelince otomatik fill
- Auto-cancel: Timeout olan emirleri temizle
"""

import logging
import threading
import time
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class OrderTracker:
    """
    Limit emirlerini izle ve yönet
    
    İş Akışı:
    1. Smart executor'dan limit order gelir
    2. Track_order() ile kaydet
    3. Background thread sürekli kontrol eder:
       - Timeout kontrolü (5 dakika)
       - Fill simulation (fiyat geldi mi?)
    4. Fill/Cancel event'leri callback ile bildirir
    """
    
    def __init__(self, config, timeout_seconds: int = 300):
        self.config = config
        self.timeout_seconds = timeout_seconds
        
        # Order storage
        self.orders: Dict[str, Dict] = {}  # order_id -> order_data
        self.lock = threading.Lock()
        
        # Callbacks
        self.on_fill_callback: Optional[callable] = None
        self.on_cancel_callback: Optional[callable] = None
        self.on_partial_fill_callback: Optional[callable] = None
        
        # Statistics
        self.total_tracked = 0
        self.filled_count = 0
        self.canceled_count = 0
        self.timeout_count = 0
        
        # Background monitoring
        self.stop_event = threading.Event()
        self.monitor_thread: Optional[threading.Thread] = None
        
        logger.info("📋 OrderTracker initialized")
        logger.info(f"   Timeout: {timeout_seconds}s ({timeout_seconds/60:.1f} min)")
    
    def start(self):
        """Background monitoring başlat"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("⚠️ Monitor thread already running")
            return
        
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_orders,
            daemon=True,
            name="OrderMonitorThread"
        )
        self.monitor_thread.start()
        logger.info("✅ Order monitoring started")
    
    def stop(self):
        """Background monitoring durdur"""
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            logger.warning("⚠️ Monitor thread not running")
            return
        
        self.stop_event.set()
        self.monitor_thread.join(timeout=5)
        logger.info("🛑 Order monitoring stopped")
    
    def track_order(self, order: Dict):
        """
        Yeni limit order'ı izlemeye al
        
        Args:
            order: Order data from smart_executor
                {
                    'order_id': 'sim_limit_123',
                    'type': 'limit',
                    'side': 'BUY'/'SELL',
                    'symbol': 'BTCUSDT',
                    'quantity': 0.5,
                    'price': 103000.0,
                    'status': 'NEW',
                    'filled_quantity': 0,
                    'timestamp': '...',
                    'timeout_at': unix_timestamp
                }
        """
        if order['type'] != 'limit':
            logger.debug(f"⏭️ Skipping non-limit order: {order['order_id']}")
            return
        
        with self.lock:
            order_id = order['order_id']
            self.orders[order_id] = order.copy()
            self.total_tracked += 1
            
            logger.info(f"📝 Tracking order {order_id}")
            logger.info(f"   {order['side']} {order['quantity']} {order['symbol']} @ ${order['price']:.2f}")
            logger.info(f"   Timeout: {datetime.fromtimestamp(order['timeout_at']).strftime('%H:%M:%S')}")
    
    def check_fill(self, order_id: str, current_price: float) -> Optional[Dict]:
        """
        Limit order fill kontrolü
        
        Args:
            order_id: Order ID
            current_price: Mevcut piyasa fiyatı
        
        Returns:
            Fill event if filled, None otherwise
        """
        with self.lock:
            if order_id not in self.orders:
                return None
            
            order = self.orders[order_id]
            
            # Already filled/canceled?
            if order['status'] != 'NEW':
                return None
            
            # Check if price hit
            side = order['side']
            limit_price = order['price']
            
            is_filled = False
            
            if side == 'BUY':
                # BUY limit fills when market ≤ limit
                is_filled = current_price <= limit_price
            else:
                # SELL limit fills when market ≥ limit
                is_filled = current_price >= limit_price
            
            if is_filled:
                # Fill the order
                order['status'] = 'FILLED'
                order['filled_quantity'] = order['quantity']
                order['filled_price'] = limit_price  # Filled at limit price
                order['filled_at'] = time.time()
                
                self.filled_count += 1
                
                logger.info(f"✅ Order {order_id} FILLED")
                logger.info(f"   {side} {order['quantity']} {order['symbol']} @ ${limit_price:.2f}")
                logger.info(f"   Market price: ${current_price:.2f}")
                
                # Trigger callback
                if self.on_fill_callback:
                    self.on_fill_callback(order.copy())
                
                return order.copy()
        
        return None
    
    def cancel_order(self, order_id: str, reason: str = "Manual cancel") -> bool:
        """Order iptal et"""
        with self.lock:
            if order_id not in self.orders:
                logger.warning(f"⚠️ Order not found: {order_id}")
                return False
            
            order = self.orders[order_id]
            
            if order['status'] != 'NEW':
                logger.warning(f"⚠️ Order already {order['status']}: {order_id}")
                return False
            
            # Cancel
            order['status'] = 'CANCELED'
            order['cancel_reason'] = reason
            order['canceled_at'] = time.time()
            
            self.canceled_count += 1
            if 'timeout' in reason.lower():
                self.timeout_count += 1
            
            logger.info(f"❌ Order {order_id} CANCELED: {reason}")
            
            # Trigger callback
            if self.on_cancel_callback:
                self.on_cancel_callback(order.copy())
            
            return True
    
    def get_active_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Aktif (NEW) emirleri getir"""
        with self.lock:
            active = [
                order.copy()
                for order in self.orders.values()
                if order['status'] == 'NEW'
            ]
            
            if symbol:
                active = [o for o in active if o['symbol'] == symbol]
            
            return active
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """Belirli bir emri getir"""
        with self.lock:
            return self.orders.get(order_id, None)
    
    def _monitor_orders(self):
        """Background thread: Timeout kontrolü"""
        logger.info("🔄 Order monitor thread started")
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                with self.lock:
                    for order_id, order in list(self.orders.items()):
                        if order['status'] != 'NEW':
                            continue
                        
                        # Timeout check
                        if current_time >= order['timeout_at']:
                            logger.warning(f"⏰ Order {order_id} timed out")
                            self.cancel_order(order_id, reason="Timeout (5 min)")
                
                # Sleep 1 second
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}", exc_info=True)
                time.sleep(5)
        
        logger.info("🛑 Order monitor thread stopped")
    
    def set_fill_callback(self, callback: callable):
        """Fill callback ayarla"""
        self.on_fill_callback = callback
    
    def set_cancel_callback(self, callback: callable):
        """Cancel callback ayarla"""
        self.on_cancel_callback = callback
    
    def get_stats(self) -> Dict:
        """İstatistikler"""
        with self.lock:
            active_count = len([o for o in self.orders.values() if o['status'] == 'NEW'])
            
            return {
                'total_tracked': self.total_tracked,
                'active_orders': active_count,
                'filled_count': self.filled_count,
                'canceled_count': self.canceled_count,
                'timeout_count': self.timeout_count,
                'fill_rate': (self.filled_count / self.total_tracked * 100) if self.total_tracked > 0 else 0,
                'timeout_rate': (self.timeout_count / self.total_tracked * 100) if self.total_tracked > 0 else 0
            }
    
    def cleanup_old_orders(self, max_age_hours: int = 24):
        """Eski emirleri temizle"""
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)
        
        with self.lock:
            removed_count = 0
            
            for order_id in list(self.orders.keys()):
                order = self.orders[order_id]
                
                # Skip active orders
                if order['status'] == 'NEW':
                    continue
                
                # Check age
                order_time = order.get('filled_at') or order.get('canceled_at') or 0
                
                if order_time < cutoff_time:
                    del self.orders[order_id]
                    removed_count += 1
            
            if removed_count > 0:
                logger.info(f"🧹 Cleaned up {removed_count} old orders (>{max_age_hours}h)")


class PositionAggregator:
    """
    Birden fazla fill'i tek pozisyona birleştir
    
    Örnek:
    - Order 1: BUY 0.3 @ $100
    - Order 2: BUY 0.2 @ $102
    → Total: 0.5 @ $100.8 average
    """
    
    def __init__(self):
        self.positions: Dict[str, List[Dict]] = defaultdict(list)  # symbol -> [fills]
    
    def add_fill(self, symbol: str, fill: Dict):
        """Fill ekle"""
        self.positions[symbol].append({
            'quantity': fill['filled_quantity'],
            'price': fill['filled_price'],
            'side': fill['side'],
            'timestamp': fill.get('filled_at', time.time())
        })
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Pozisyon özeti"""
        if symbol not in self.positions or not self.positions[symbol]:
            return None
        
        fills = self.positions[symbol]
        
        # Calculate average
        total_qty = sum(f['quantity'] for f in fills)
        weighted_sum = sum(f['quantity'] * f['price'] for f in fills)
        avg_price = weighted_sum / total_qty if total_qty > 0 else 0
        
        return {
            'symbol': symbol,
            'total_quantity': total_qty,
            'average_price': avg_price,
            'fill_count': len(fills),
            'first_fill': min(f['timestamp'] for f in fills),
            'last_fill': max(f['timestamp'] for f in fills),
            'fills': fills.copy()
        }


# Module-level singleton
_order_tracker_instance: Optional[OrderTracker] = None


def get_order_tracker(config) -> OrderTracker:
    """Get or create OrderTracker instance (singleton)"""
    global _order_tracker_instance
    
    if _order_tracker_instance is None:
        _order_tracker_instance = OrderTracker(config)
    
    return _order_tracker_instance


def reset_order_tracker():
    """Reset singleton instance (for testing)"""
    global _order_tracker_instance
    
    if _order_tracker_instance is not None:
        try:
            _order_tracker_instance.stop()
        except:
            pass
    
    _order_tracker_instance = None
