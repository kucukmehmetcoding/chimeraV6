#!/usr/bin/env python3
"""
RANGE BOT - NEAR-MISS SIGNAL MONITOR (v12.1)
=============================================

Bu modül, reddedilen ama %90+ threshold geçen sinyalleri WebSocket ile gerçek zamanlı izler.
Sinyal kriterleri karşılandığında otomatik pozisyon açar.

Özellikler:
- WebSocket ile sürekli fiyat güncellemesi
- Priority queue ile max 20 aktif subscription
- Duplicate pozisyon kontrolü
- TTL tabanlı otomatik cleanup
- 30 saniyede bir revalidation
"""

import sys
import os
import time
import logging
from datetime import datetime, timedelta
from threading import Event, Lock
from typing import Dict, List

# Proje kökünü path'e ekle
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config
from src.database.models import NearMissSignal, OpenPosition, db_session
from src.data_fetcher.binance_fetcher import get_binance_klines, binance_client
from src.data_fetcher.websocket_manager import get_websocket_manager
from src.technical_analyzer.range_strategy import analyze_range_signal
from src.notifications import telegram as telegram_notifier

logger = logging.getLogger(__name__)

# Global WebSocket manager ve lock
ws_manager = None
near_miss_lock = Lock()
position_lock = Lock()  # Shared with main bot


class NearMissMonitor:
    """
    Near-miss signal monitoring ve validation sistemi.
    """
    
    def __init__(self, stop_event: Event, position_lock: Lock):
        self.stop_event = stop_event
        self.position_lock = position_lock
        
        # Configuration (from ENV via range_main.py)
        self.check_interval = int(os.getenv('RANGE_NEAR_MISS_CHECK_INTERVAL', '30'))
        self.max_active = int(os.getenv('RANGE_NEAR_MISS_MAX_ACTIVE', '20'))
        
        # WebSocket manager
        global ws_manager
        ws_manager = get_websocket_manager(config, stop_event)
        ws_manager.on_near_miss_price_update = self.on_price_update
        
        # Current price cache (updated by WebSocket)
        self.price_cache = {}  # symbol -> {price, timestamp}
        self.price_cache_lock = Lock()
        
        logger.info(f"✅ Near-Miss Monitor initialized (check interval: {self.check_interval}s)")
    
    def start(self):
        """Start near-miss monitoring"""
        logger.info("🎯 Near-Miss Monitor başlatılıyor...")
        
        # Start WebSocket manager
        if not ws_manager.is_connected:
            if not ws_manager.start():
                logger.error("❌ WebSocket başlatılamadı - Near-Miss Monitor devre dışı")
                return
        
        logger.info("✅ Near-Miss Monitor aktif")
        
        # Main monitoring loop
        while not self.stop_event.is_set():
            try:
                # 1. Cleanup expired near-miss signals
                self.cleanup_expired_signals()
                
                # 2. Load active near-miss signals from DB
                active_signals = self.load_active_signals()
                
                # 3. Subscribe to WebSocket for top priority signals
                self.update_subscriptions(active_signals)
                
                # 4. Revalidate signals that might have become valid
                self.revalidate_signals(active_signals)
                
                # Sleep until next check
                self.stop_event.wait(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Near-Miss Monitor error: {e}", exc_info=True)
                self.stop_event.wait(60)
        
        logger.info("🛑 Near-Miss Monitor stopped")
    
    def cleanup_expired_signals(self):
        """Remove expired near-miss signals"""
        db = db_session()
        try:
            now = datetime.now()
            expired_count = db.query(NearMissSignal).filter(
                NearMissSignal.expires_at <= now,
                NearMissSignal.is_active == True
            ).update({'is_active': False})
            
            if expired_count > 0:
                db.commit()
                logger.info(f"🗑️  {expired_count} expired near-miss signals cleaned")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Cleanup error: {e}")
        finally:
            db_session.remove()
    
    def load_active_signals(self) -> List[NearMissSignal]:
        """Load active near-miss signals, sorted by priority"""
        db = db_session()
        try:
            signals = db.query(NearMissSignal).filter(
                NearMissSignal.is_active == True,
                NearMissSignal.is_consumed == False
            ).order_by(NearMissSignal.priority_score.desc()).all()
            
            logger.debug(f"📊 Loaded {len(signals)} active near-miss signals")
            return signals
        except Exception as e:
            logger.error(f"❌ Load signals error: {e}")
            return []
        finally:
            db_session.remove()
    
    def update_subscriptions(self, signals: List[NearMissSignal]):
        """Update WebSocket subscriptions based on priority"""
        # Get top N signals by priority
        top_signals = signals[:self.max_active]
        
        # Get current subscriptions
        current_subs = ws_manager.get_near_miss_subscriptions()
        current_symbols = set(current_subs.keys())
        target_symbols = {s.symbol for s in top_signals}
        
        # Unsubscribe from signals no longer in top N
        for symbol in current_symbols - target_symbols:
            ws_manager.unsubscribe_near_miss(symbol)
            logger.debug(f"   Unsubscribed: {symbol} (no longer in top {self.max_active})")
        
        # Subscribe to new top signals
        for signal in top_signals:
            if signal.symbol not in current_symbols:
                success = ws_manager.subscribe_near_miss(
                    signal.symbol,
                    signal.priority_score,
                    signal.id
                )
                if success:
                    logger.debug(f"   Subscribed: {signal.symbol} (priority: {signal.priority_score:.2f})")
    
    def on_price_update(self, symbol: str, price: float, is_closed: bool):
        """
        WebSocket callback for price updates.
        
        Args:
            symbol: Trading pair
            price: Current price
            is_closed: Is candle closed?
        """
        with self.price_cache_lock:
            self.price_cache[symbol] = {
                'price': price,
                'timestamp': time.time(),
                'is_closed': is_closed
            }
        
        # Only act on closed candles to avoid false triggers
        if not is_closed:
            return
        
        logger.debug(f"💹 {symbol}: {price:.2f} (closed)")
        
        # Quick validation check (full revalidation happens in main loop)
        # This is for ultra-fast response when price hits exact levels
        self.quick_validate_symbol(symbol, price)
    
    def quick_validate_symbol(self, symbol: str, current_price: float):
        """
        Quick validation when price update received.
        Checks if price is now within entry zone.
        """
        db = db_session()
        try:
            # Get active near-miss for this symbol
            nm = db.query(NearMissSignal).filter(
                NearMissSignal.symbol == symbol,
                NearMissSignal.is_active == True,
                NearMissSignal.is_consumed == False
            ).first()
            
            if not nm:
                return
            
            # Check if price is within entry zone
            entry_zone_valid = False
            
            if nm.direction == 'LONG':
                # LONG: price should be near support
                if abs(current_price - nm.support) / nm.support <= 0.005:  # Within 0.5%
                    entry_zone_valid = True
            elif nm.direction == 'SHORT':
                # SHORT: price should be near resistance
                if abs(current_price - nm.resistance) / nm.resistance <= 0.005:
                    entry_zone_valid = True
            
            if entry_zone_valid:
                logger.info(f"⚡ {symbol} price entered zone! Triggering full revalidation...")
                # Trigger immediate full revalidation (will happen in next loop iteration)
                # For now, just log it
        
        except Exception as e:
            logger.error(f"❌ Quick validate error for {symbol}: {e}")
        finally:
            db_session.remove()
    
    def revalidate_signals(self, signals: List[NearMissSignal]):
        """
        Full revalidation of near-miss signals.
        Fetches fresh data and rechecks all criteria.
        """
        for nm in signals[:10]:  # Limit to top 10 per cycle to avoid API spam
            try:
                # Get current price from cache or API
                current_price = self.get_current_price(nm.symbol)
                if not current_price:
                    continue
                
                # Check if position already exists (duplicate prevention)
                with self.position_lock:
                    db = db_session()
                    try:
                        existing_pos = db.query(OpenPosition).filter(
                            OpenPosition.symbol == nm.symbol
                        ).first()
                        
                        if existing_pos:
                            logger.debug(f"   ⏭️  {nm.symbol} already has open position, marking consumed")
                            nm.is_consumed = True
                            nm.is_active = False
                            db.commit()
                            continue
                    finally:
                        db_session.remove()
                
                # Fetch fresh 15M and 1H data
                df_15m = get_binance_klines(nm.symbol, '15m', limit=100)
                df_1h = get_binance_klines(nm.symbol, '1h', limit=50)
                
                if df_15m is None or df_1h is None or df_15m.empty or df_1h.empty:
                    logger.debug(f"   ⚠️ {nm.symbol} data unavailable")
                    continue
                
                # Re-analyze signal
                signal = analyze_range_signal(df_15m, df_1h, nm.symbol)
                
                if not signal:
                    logger.debug(f"   ❌ {nm.symbol} no longer valid range")
                    continue
                
                # Check if all criteria now pass
                from range_main import (
                    MIN_RANGE_WIDTH, MIN_RR_RATIO, MIN_SL_DISTANCE,
                    MIN_QUALITY, open_range_position
                )
                
                range_width = signal.get('range_width', 0)
                range_quality = signal.get('range_quality', 'D')
                entry_price = signal['entry_price']
                tp_price = signal['tp_price']
                sl_price = signal['sl_price']
                
                risk = abs(entry_price - sl_price)
                reward = abs(tp_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                sl_distance_pct = risk / entry_price
                
                # Validate all criteria
                if range_quality in ['C', 'D']:
                    continue
                if range_width < MIN_RANGE_WIDTH:
                    continue
                if rr_ratio < MIN_RR_RATIO:
                    continue
                if sl_distance_pct < MIN_SL_DISTANCE:
                    continue
                if len(signal.get('false_breakouts', [])) > 2:
                    continue
                
                # ALL CRITERIA PASSED! 🎉
                logger.info(f"🎯 NEAR-MISS VALIDATED: {nm.symbol}")
                logger.info(f"   Quality: {range_quality} | RR: {rr_ratio:.2f} | Width: {range_width*100:.1f}%")
                
                # Open position
                signal['symbol'] = nm.symbol
                success = open_range_position(nm.symbol, signal, source='near_miss')
                
                if success:
                    # Mark as consumed
                    db = db_session()
                    try:
                        nm.is_consumed = True
                        nm.is_active = False
                        db.commit()
                        logger.info(f"✅ Near-miss position opened successfully")
                        
                        # Send special Telegram notification
                        try:
                            msg = (
                                f"⚡ **NEAR-MISS SIGNAL TRIGGERED**\n\n"
                                f"Symbol: `{nm.symbol}`\n"
                                f"Direction: {signal['direction']}\n"
                                f"Entry: {entry_price:.4f}\n"
                                f"Quality: {range_quality} → {range_quality}\n"
                                f"RR: {rr_ratio:.2f}:1\n"
                                f"Range: {range_width*100:.1f}%\n\n"
                                f"_Originally rejected, now validated via real-time monitoring!_"
                            )
                            telegram_notifier.send_message(msg)
                        except Exception as tg_error:
                            logger.error(f"Telegram error: {tg_error}")
                        
                    except Exception as db_error:
                        db.rollback()
                        logger.error(f"DB update error: {db_error}")
                    finally:
                        db_session.remove()
                
            except Exception as e:
                logger.error(f"❌ Revalidation error for {nm.symbol}: {e}", exc_info=True)
                continue
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price from cache or API"""
        # Try cache first
        with self.price_cache_lock:
            cached = self.price_cache.get(symbol)
            if cached and (time.time() - cached['timestamp']) < 60:
                return cached['price']
        
        # Fallback to API
        try:
            ticker = binance_client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"Price fetch error for {symbol}: {e}")
            return None


def run_near_miss_monitor(stop_event: Event, position_lock: Lock):
    """
    Near-miss monitor thread main function.
    
    Args:
        stop_event: Shutdown signal
        position_lock: Shared lock with main bot for position operations
    """
    logger.info("🚀 Near-Miss Monitor thread başlatıldı")
    
    try:
        monitor = NearMissMonitor(stop_event, position_lock)
        monitor.start()
    except Exception as e:
        logger.error(f"❌ Near-Miss Monitor fatal error: {e}", exc_info=True)
    finally:
        logger.info("👋 Near-Miss Monitor thread kapandı")


if __name__ == "__main__":
    # Test run
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s'
    )
    
    stop_event = Event()
    position_lock = Lock()
    
    try:
        run_near_miss_monitor(stop_event, position_lock)
    except KeyboardInterrupt:
        logger.info("\nCtrl+C pressed, shutting down...")
        stop_event.set()
