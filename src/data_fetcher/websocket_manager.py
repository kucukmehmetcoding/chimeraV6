# src/data_fetcher/websocket_manager.py
"""
v10.6: WEBSOCKET REAL-TIME MONITORING - Phase 1
================================================

Bu modül, Binance Futures WebSocket API üzerinden gerçek zamanlı kline (mum) verisi alır.
15 dakikalık mumları izleyerek EMA kesişimlerini erken yakalamamızı sağlar.

Temel Özellikler:
- ThreadedWebsocketManager kullanarak çoklu sembol izleme
- Otomatik yeniden bağlanma
- Thread-safe operasyonlar
- Sağlık kontrolü ve istatistikler
"""

import logging
import threading
import time
import json
from threading import Lock, Event
from datetime import datetime
from typing import Callable, Dict, Optional, Any

try:
    from binance import ThreadedWebsocketManager
    from binance.client import Client
except ImportError:
    ThreadedWebsocketManager = None
    Client = None

logger = logging.getLogger(__name__)


class WebSocketKlineManager:
    """
    Binance Futures WebSocket Kline Stream Manager
    
    Manages real-time kline (candlestick) data streaming from Binance Futures.
    Handles reconnection, data parsing, and event callbacks.
    """
    
    def __init__(self, config, stop_event: Event):
        """
        Initialize WebSocket manager
        
        Args:
            config: Configuration module
            stop_event: Threading event for graceful shutdown
        """
        self.config = config
        self.stop_event = stop_event
        
        # API credentials
        self.api_key = getattr(config, 'BINANCE_API_KEY', None)
        self.api_secret = getattr(config, 'BINANCE_SECRET_KEY', None)
        self.testnet = getattr(config, 'BINANCE_TESTNET', False)
        
        # WebSocket settings
        self.interval = getattr(config, 'WEBSOCKET_KLINE_INTERVAL', '15m')
        self.symbols = []  # Will be populated dynamically
        
        # Connection state
        self.twm = None  # ThreadedWebsocketManager instance
        self.active_streams = {}  # symbol -> stream_name mapping
        self.connection_lock = Lock()
        self.is_connected = False
        
        # Callbacks
        self.on_kline_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None
        
        # Reconnection settings
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        
        # Stats
        self.message_count = 0
        self.last_message_time = None
        self.error_count = 0
        
        # 🆕 v10.9: EMA cache for crossover detection
        self.ema_cache = {}  # symbol -> {prev_ema5, prev_ema20, current_ema5, current_ema20}
        self.ema_cache_lock = Lock()
        
        logger.info(f"✅ WebSocket Manager initialized (Interval: {self.interval}, Testnet: {self.testnet})")
    
    def start(self) -> bool:
        """
        Start WebSocket manager
        
        Returns:
            bool: True if started successfully
        """
        if ThreadedWebsocketManager is None:
            logger.error("❌ binance library not available - WebSocket cannot start")
            return False
        
        try:
            with self.connection_lock:
                # Create ThreadedWebsocketManager
                if self.testnet:
                    # Testnet WebSocket endpoint
                    self.twm = ThreadedWebsocketManager(
                        api_key=self.api_key,
                        api_secret=self.api_secret,
                        testnet=True
                    )
                else:
                    # Production WebSocket endpoint
                    self.twm = ThreadedWebsocketManager(
                        api_key=self.api_key,
                        api_secret=self.api_secret
                    )
                
                # Start the manager
                self.twm.start()
                self.is_connected = True
                
                logger.info("✅ WebSocket Manager started successfully")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket Manager: {e}", exc_info=True)
            self.is_connected = False
            return False
    
    def stop(self):
        """Stop WebSocket manager and all streams"""
        logger.info("🛑 Stopping WebSocket Manager...")
        
        with self.connection_lock:
            if self.twm:
                try:
                    # Stop all active streams
                    for symbol, stream_name in list(self.active_streams.items()):
                        try:
                            self.twm.stop_socket(stream_name)
                            logger.debug(f"   Stopped stream for {symbol}")
                        except Exception as e:
                            logger.warning(f"   Error stopping stream for {symbol}: {e}")
                    
                    # Stop the manager
                    self.twm.stop()
                    
                    # Wait for thread to fully terminate
                    time.sleep(0.5)
                    
                    logger.info("✅ WebSocket Manager stopped")
                    
                except Exception as e:
                    logger.error(f"❌ Error stopping WebSocket Manager: {e}")
                finally:
                    self.twm = None
                    self.active_streams.clear()
                    self.symbols.clear()
                    self.is_connected = False
    
    def subscribe_symbol(self, symbol: str) -> bool:
        """
        Subscribe to kline stream for a symbol
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            
        Returns:
            bool: True if subscribed successfully
        """
        if not self.is_connected:
            logger.warning(f"⚠️ Cannot subscribe {symbol} - WebSocket not connected")
            return False
        
        # Check if already subscribed
        if symbol in self.active_streams:
            logger.debug(f"   {symbol} already subscribed")
            return True
        
        try:
            # Create kline callback for this symbol
            def kline_callback(msg):
                self._handle_kline_message(msg, symbol)
            
            # ✅ DÜZELTME: Futures için start_kline_futures_socket kullan
            # Spot için: start_kline_socket
            # Futures için: start_kline_futures_socket
            stream_name = self.twm.start_kline_futures_socket(
                callback=kline_callback,
                symbol=symbol,
                interval=self.interval
            )
            
            # Store stream reference
            with self.connection_lock:
                self.active_streams[symbol] = stream_name
                if symbol not in self.symbols:
                    self.symbols.append(symbol)
            
            logger.info(f"✅ Subscribed to {symbol} {self.interval} kline stream")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe {symbol}: {e}", exc_info=True)
            return False
    
    # Alias for compatibility with hybrid system
    def subscribe(self, symbol: str) -> bool:
        """Alias for subscribe_symbol (v10.9 hybrid system compatibility)"""
        return self.subscribe_symbol(symbol)
    
    def unsubscribe_symbol(self, symbol: str) -> bool:
        """
        Unsubscribe from kline stream for a symbol
        
        Args:
            symbol: Trading pair
            
        Returns:
            bool: True if unsubscribed successfully
        """
        with self.connection_lock:
            if symbol not in self.active_streams:
                logger.debug(f"   {symbol} not subscribed")
                return True
            
            try:
                stream_name = self.active_streams[symbol]
                self.twm.stop_socket(stream_name)
                
                del self.active_streams[symbol]
                if symbol in self.symbols:
                    self.symbols.remove(symbol)
                
                logger.info(f"✅ Unsubscribed from {symbol} kline stream")
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to unsubscribe {symbol}: {e}")
                return False
    
    # Alias for compatibility with hybrid system
    def unsubscribe(self, symbol: str) -> bool:
        """Alias for unsubscribe_symbol (v10.9 hybrid system compatibility)"""
        return self.unsubscribe_symbol(symbol)
    
    def _handle_kline_message(self, msg: Dict[str, Any], symbol: str):
        """
        Internal handler for kline messages
        
        Args:
            msg: WebSocket message
            symbol: Trading pair
        """
        try:
            # Update stats
            self.message_count += 1
            self.last_message_time = time.time()
            
            # Validate message structure
            # Accept both 'kline' (regular) and 'continuous_kline' (futures) events
            event_type = msg.get('e', '')
            if event_type not in ['kline', 'continuous_kline']:
                logger.warning(f"⚠️ Invalid kline message for {symbol}: {event_type}")
                return
            
            # Extract kline data
            kline = msg.get('k', {})
            
            # Parse kline data
            kline_data = {
                'symbol': symbol,
                'interval': kline.get('i'),
                'open_time': kline.get('t'),
                'close_time': kline.get('T'),
                'open': float(kline.get('o', 0)),
                'high': float(kline.get('h', 0)),
                'low': float(kline.get('l', 0)),
                'close': float(kline.get('c', 0)),
                'volume': float(kline.get('v', 0)),
                'is_closed': kline.get('x', False),
                'quote_volume': float(kline.get('q', 0)),
                'trades': int(kline.get('n', 0))
            }
            
            # Validate data
            if kline_data['close'] <= 0:
                logger.warning(f"⚠️ Invalid price data for {symbol}: close={kline_data['close']}")
                return
            
            # Call user callback
            if self.on_kline_callback:
                try:
                    self.on_kline_callback(kline_data)
                except Exception as e:
                    logger.error(f"❌ Error in kline callback for {symbol}: {e}", exc_info=True)
                    if self.on_error_callback:
                        self.on_error_callback(e, kline_data)
            
            # Debug log (every 10th message to reduce noise)
            if self.message_count % 10 == 0:
                status = "CLOSED" if kline_data['is_closed'] else "OPEN"
                logger.debug(f"   📊 {symbol} {self.interval} | Price: {kline_data['close']:.2f} | {status}")
        
        except Exception as e:
            logger.error(f"❌ Error handling kline message for {symbol}: {e}", exc_info=True)
            self.error_count += 1
            
            if self.on_error_callback:
                self.on_error_callback(e, msg)
    
    def set_kline_callback(self, callback: Callable):
        """
        Set callback function for kline data
        
        Args:
            callback: Function(kline_data: dict) -> None
        """
        self.on_kline_callback = callback
        logger.debug("✅ Kline callback registered")
    
    def set_error_callback(self, callback: Callable):
        """
        Set callback function for errors
        
        Args:
            callback: Function(error: Exception, data: dict) -> None
        """
        self.on_error_callback = callback
        logger.debug("✅ Error callback registered")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket statistics"""
        return {
            'is_connected': self.is_connected,
            'subscribed_symbols': len(self.active_streams),
            'symbols': list(self.symbols),
            'message_count': self.message_count,
            'error_count': self.error_count,
            'last_message_time': self.last_message_time,
            'uptime_seconds': time.time() - self.last_message_time if self.last_message_time else 0
        }
    
    def health_check(self) -> bool:
        """
        Check if WebSocket is healthy
        
        Returns:
            bool: True if healthy (received message in last 60 seconds)
        """
        if not self.is_connected:
            return False
        
        if self.last_message_time is None:
            return True  # Just started, no messages yet
        
        time_since_last_message = time.time() - self.last_message_time
        
        # Healthy if received message in last 60 seconds
        if time_since_last_message > 60:
            logger.warning(f"⚠️ WebSocket health check FAILED: No message for {time_since_last_message:.0f}s")
            return False
        
        return True
    
    def update_ema_cache(self, symbol: str, prev_ema5: float, prev_ema20: float,
                         current_ema5: float, current_ema20: float):
        """
        Update EMA cache for crossover detection (v10.9 Hybrid System)
        
        Args:
            symbol: Trading pair
            prev_ema5: Previous candle's EMA5
            prev_ema20: Previous candle's EMA20
            current_ema5: Current candle's EMA5
            current_ema20: Current candle's EMA20
        """
        with self.ema_cache_lock:
            self.ema_cache[symbol] = {
                'prev_ema5': prev_ema5,
                'prev_ema20': prev_ema20,
                'current_ema5': current_ema5,
                'current_ema20': current_ema20,
                'updated_at': time.time()
            }
            logger.debug(
                f"EMA cache updated for {symbol}: "
                f"prev({prev_ema5:.2f}/{prev_ema20:.2f}) -> "
                f"current({current_ema5:.2f}/{current_ema20:.2f})"
            )
    
    def get_ema_cache(self, symbol: str) -> Optional[Dict]:
        """
        Get EMA cache for a symbol
        
        Args:
            symbol: Trading pair
        
        Returns:
            Dict with EMA values or None if not cached
        """
        with self.ema_cache_lock:
            return self.ema_cache.get(symbol)
    
    def clear_ema_cache(self, symbol: str = None):
        """
        Clear EMA cache for a symbol or all symbols
        
        Args:
            symbol: Trading pair (if None, clear all)
        """
        with self.ema_cache_lock:
            if symbol:
                self.ema_cache.pop(symbol, None)
                logger.debug(f"EMA cache cleared for {symbol}")
            else:
                self.ema_cache.clear()
                logger.debug("All EMA cache cleared")


# Module-level instance (singleton pattern)
_websocket_manager_instance: Optional[WebSocketKlineManager] = None


def get_websocket_manager(config, stop_event: Event, force_new: bool = False) -> WebSocketKlineManager:
    """
    Get or create WebSocket manager instance (singleton)
    
    Args:
        config: Configuration module
        stop_event: Stop event for shutdown
        force_new: Force creation of new instance (for testing)
        
    Returns:
        WebSocketKlineManager instance
    """
    global _websocket_manager_instance
    
    # If force_new or no instance exists, create new one
    if force_new or _websocket_manager_instance is None:
        # Stop existing instance if present
        if _websocket_manager_instance is not None:
            try:
                _websocket_manager_instance.stop()
            except:
                pass
        
        _websocket_manager_instance = WebSocketKlineManager(config, stop_event)
    
    return _websocket_manager_instance


def reset_websocket_manager():
    """Reset the singleton instance (for testing)"""
    global _websocket_manager_instance
    
    if _websocket_manager_instance is not None:
        try:
            _websocket_manager_instance.stop()
        except:
            pass
        _websocket_manager_instance = None
