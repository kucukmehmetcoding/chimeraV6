#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket Tabanlı Gerçek Zamanlı Sinyal Takip Sistemi
Real-time signal tracking with Binance WebSocket
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Set
from collections import defaultdict
import threading
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from binance import AsyncClient, BinanceSocketManager
from binance.enums import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalTracker:
    """WebSocket ile sinyal takip sistemi"""
    
    def __init__(self):
        self.tracked_signals: Dict[str, Dict] = {}
        self.price_cache: Dict[str, float] = {}
        self.triggered_signals: Set[str] = set()
        self.lock = threading.Lock()
        
        # Telegram notification (optional)
        self.telegram_enabled = False
        try:
            from src.notifications.telegram import send_message
            self.send_telegram = send_message
            self.telegram_enabled = True
        except:
            logger.warning("Telegram notifications not available")
    
    def add_signals(self, signals: List[Dict]):
        """
        Taranmış sinyalleri takip listesine ekle
        
        Args:
            signals: comprehensive_signal_scan() sonucu
        """
        with self.lock:
            for signal in signals:
                symbol = signal['symbol']
                signal_id = f"{symbol}_{signal.get('signal_type', 'unknown')}_{signal.get('timeframe', 'unknown')}"
                
                # Entry, SL, TP bilgilerini çıkar
                risk_mgmt = signal.get('risk_management', {})
                
                self.tracked_signals[signal_id] = {
                    'symbol': symbol,
                    'type': signal.get('type', 'unknown'),
                    'signal_type': signal.get('signal_type', 'unknown'),
                    'timeframe': signal.get('timeframe', 'unknown'),
                    'entry_price': risk_mgmt.get('entry_price', 0),
                    'stop_loss': risk_mgmt.get('stop_loss', 0),
                    'take_profit_multi': risk_mgmt.get('take_profit_multi', []),
                    'trailing_stop': risk_mgmt.get('trailing_stop', {}),
                    'priority_score': signal.get('priority_score', 0),
                    'added_at': datetime.now(),
                    'status': 'monitoring',
                    'current_price': 0,
                    'pnl_pct': 0,
                    'hit_tp_levels': []
                }
        
        logger.info(f"Added {len(signals)} signals to tracking system")
        logger.info(f"Total tracking: {len(self.tracked_signals)} signals")
    
    def update_price(self, symbol: str, price: float):
        """WebSocket'ten gelen fiyat güncellemesi"""
        with self.lock:
            self.price_cache[symbol] = price
            
            # Bu sembole ait sinyalleri güncelle
            for signal_id, signal_data in self.tracked_signals.items():
                if signal_data['symbol'] == symbol and signal_data['status'] == 'monitoring':
                    signal_data['current_price'] = price
                    
                    # PnL hesapla
                    entry = signal_data['entry_price']
                    if entry > 0:
                        if signal_data['type'] == 'bullish':
                            signal_data['pnl_pct'] = ((price - entry) / entry) * 100
                        else:
                            signal_data['pnl_pct'] = ((entry - price) / entry) * 100
                    
                    # SL/TP kontrolleri
                    self._check_triggers(signal_id, signal_data)
    
    def _check_triggers(self, signal_id: str, signal_data: Dict):
        """SL ve TP tetiklenme kontrolü"""
        symbol = signal_data['symbol']
        current_price = signal_data['current_price']
        signal_type = signal_data['type']
        
        # Stop Loss kontrolü
        sl = signal_data['stop_loss']
        if sl > 0:
            if signal_type == 'bullish' and current_price <= sl:
                self._trigger_stop_loss(signal_id, signal_data)
                return
            elif signal_type == 'bearish' and current_price >= sl:
                self._trigger_stop_loss(signal_id, signal_data)
                return
        
        # Take Profit kontrolü (Multi TP)
        tp_levels = signal_data.get('take_profit_multi', [])
        for i, tp in enumerate(tp_levels):
            tp_level = i + 1
            if tp_level in signal_data['hit_tp_levels']:
                continue
            
            tp_price = tp['price']
            
            if signal_type == 'bullish' and current_price >= tp_price:
                self._trigger_take_profit(signal_id, signal_data, tp_level, tp)
            elif signal_type == 'bearish' and current_price <= tp_price:
                self._trigger_take_profit(signal_id, signal_data, tp_level, tp)
    
    def _trigger_stop_loss(self, signal_id: str, signal_data: Dict):
        """Stop Loss tetiklendi"""
        if signal_id in self.triggered_signals:
            return
        
        self.triggered_signals.add(signal_id)
        signal_data['status'] = 'stopped'
        signal_data['closed_at'] = datetime.now()
        signal_data['final_pnl'] = signal_data['pnl_pct']
        
        symbol = signal_data['symbol']
        pnl = signal_data['pnl_pct']
        
        message = f"""
🛑 STOP LOSS HIT - {symbol}

Type: {signal_data['signal_type'].upper()}
Timeframe: {signal_data['timeframe']}
Direction: {signal_data['type'].upper()}

Entry: ${signal_data['entry_price']:.4f}
Stop Loss: ${signal_data['stop_loss']:.4f}
Current: ${signal_data['current_price']:.4f}

📊 Final PnL: {pnl:.2f}%

⚠️ Position closed at stop loss
        """
        
        logger.warning(f"⛔ STOP LOSS: {symbol} - {pnl:.2f}%")
        print(message)
        
        if self.telegram_enabled:
            try:
                self.send_telegram(message)
            except:
                pass
    
    def _trigger_take_profit(self, signal_id: str, signal_data: Dict, level: int, tp_data: Dict):
        """Take Profit tetiklendi"""
        signal_data['hit_tp_levels'].append(level)
        
        symbol = signal_data['symbol']
        pnl = signal_data['pnl_pct']
        weight = tp_data['weight']
        target = tp_data['target_multiplier']
        
        message = f"""
✅ TAKE PROFIT {level} HIT - {symbol}

Type: {signal_data['signal_type'].upper()}
Timeframe: {signal_data['timeframe']}
Direction: {signal_data['type'].upper()}

Entry: ${signal_data['entry_price']:.4f}
TP{level}: ${tp_data['price']:.4f} (RR 1:{target:.1f})
Current: ${signal_data['current_price']:.4f}

📊 Current PnL: {pnl:.2f}%
💼 Position Weight: {weight:.0%}

🎯 Partial profit taken ({len(signal_data['hit_tp_levels'])}/{len(signal_data.get('take_profit_multi', []))})
        """
        
        logger.info(f"✅ TP{level} HIT: {symbol} - {pnl:.2f}%")
        print(message)
        
        if self.telegram_enabled:
            try:
                self.send_telegram(message)
            except:
                pass
        
        # Tüm TP'ler tamamlandı mı?
        if len(signal_data['hit_tp_levels']) >= len(signal_data.get('take_profit_multi', [])):
            signal_data['status'] = 'completed'
            signal_data['closed_at'] = datetime.now()
            signal_data['final_pnl'] = signal_data['pnl_pct']
            logger.info(f"🎉 All TPs completed for {symbol} - Final PnL: {pnl:.2f}%")
            
            # Final bildirim
            final_message = f"""
🎉 ALL TAKE PROFITS COMPLETED - {symbol}

Final PnL: {pnl:.2f}%
All {len(signal_data['hit_tp_levels'])} TP levels hit!

✅ Position fully closed with profit
            """
            print(final_message)
            
            if self.telegram_enabled:
                try:
                    self.send_telegram(final_message)
                except:
                    pass
    
    def get_active_signals(self) -> List[Dict]:
        """Aktif sinyalleri getir"""
        with self.lock:
            return [
                s for s in self.tracked_signals.values() 
                if s['status'] == 'monitoring'
            ]
    
    def get_summary(self) -> Dict:
        """Özet istatistikler"""
        with self.lock:
            total = len(self.tracked_signals)
            monitoring = sum(1 for s in self.tracked_signals.values() if s['status'] == 'monitoring')
            stopped = sum(1 for s in self.tracked_signals.values() if s['status'] == 'stopped')
            completed = sum(1 for s in self.tracked_signals.values() if s['status'] == 'completed')
            
            return {
                'total_signals': total,
                'monitoring': monitoring,
                'stopped_out': stopped,
                'completed': completed,
                'active_symbols': len(set(s['symbol'] for s in self.tracked_signals.values() if s['status'] == 'monitoring'))
            }


class WebSocketPriceTracker:
    """Binance WebSocket ile fiyat takibi"""
    
    def __init__(self, signal_tracker: SignalTracker):
        self.signal_tracker = signal_tracker
        self.client = None
        self.bsm = None
        self.running = False
        self.tasks = []
    
    async def start(self):
        """WebSocket bağlantısını başlat"""
        logger.info("Starting WebSocket connection...")
        
        # Binance API client (WebSocket için API key gerekmez ama varsa daha stabil)
        try:
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_SECRET_KEY')
            
            if api_key and api_secret:
                self.client = await AsyncClient.create(api_key, api_secret)
            else:
                self.client = await AsyncClient.create()
        except Exception as e:
            logger.error(f"Failed to create Binance client: {e}")
            self.client = await AsyncClient.create()
        
        self.bsm = BinanceSocketManager(self.client)
        self.running = True
        
        # Takip edilen sembolleri al
        active_signals = self.signal_tracker.get_active_signals()
        symbols = list(set(s['symbol'] for s in active_signals))
        
        if not symbols:
            logger.warning("No symbols to track")
            return
        
        logger.info(f"Tracking {len(symbols)} symbols via WebSocket")
        
        # Her sembol için WebSocket stream başlat
        for symbol in symbols:
            task = asyncio.create_task(self._track_symbol(symbol.lower()))
            self.tasks.append(task)
        
        # Summary task
        summary_task = asyncio.create_task(self._print_summary())
        self.tasks.append(summary_task)
        
        # Tüm task'ları bekle
        await asyncio.gather(*self.tasks)
    
    async def _track_symbol(self, symbol: str):
        """Tek sembol için WebSocket stream"""
        try:
            # MiniTicker stream (en hafif, sadece fiyat)
            ts = self.bsm.symbol_miniticker_socket(symbol)
            
            async with ts as tscm:
                while self.running:
                    msg = await tscm.recv()
                    
                    if msg:
                        symbol_upper = msg['s']
                        price = float(msg['c'])  # Close price
                        
                        # Signal tracker'ı güncelle
                        self.signal_tracker.update_price(symbol_upper, price)
        
        except Exception as e:
            logger.error(f"WebSocket error for {symbol}: {e}")
    
    async def _print_summary(self):
        """Periyodik özet yazdır"""
        while self.running:
            await asyncio.sleep(60)  # Her 60 saniyede
            
            summary = self.signal_tracker.get_summary()
            active = self.signal_tracker.get_active_signals()
            all_signals = list(self.signal_tracker.tracked_signals.values())
            
            # Toplam PnL hesapla (AÇIK POZİSYONLAR)
            total_active_pnl = sum(s['pnl_pct'] for s in active)
            avg_active_pnl = total_active_pnl / len(active) if active else 0
            
            # Kar/Zarar ayrımı
            in_profit = [s for s in active if s['pnl_pct'] > 0]
            in_loss = [s for s in active if s['pnl_pct'] < 0]
            breakeven = [s for s in active if s['pnl_pct'] == 0]
            
            # Kapanan pozisyonlar
            closed = [s for s in all_signals if s['status'] in ['stopped', 'completed']]
            
            # KAPANAN POZİSYONLARIN TOPLAM PnL'i
            closed_total_pnl = sum(s.get('final_pnl', s['pnl_pct']) for s in closed) if closed else 0
            closed_avg_pnl = closed_total_pnl / len(closed) if closed else 0
            
            # GERÇEK TOPLAM PnL (Açık + Kapalı)
            grand_total_pnl = total_active_pnl + closed_total_pnl
            
            print("\n" + "="*100)
            print(f"📊 SIGNAL TRACKER SUMMARY - {datetime.now().strftime('%H:%M:%S')}")
            print(f"Total Signals: {summary['total_signals']} | Monitoring: {summary['monitoring']} | " +
                  f"Stopped: {summary['stopped_out']} | Completed: {summary['completed']}")
            print(f"Active Symbols: {summary['active_symbols']}")
            
            # 🔥 YENİ: TOPLAM PnL (Gerçek Performans)
            total_icon = "🟢" if grand_total_pnl > 0 else "🔴" if grand_total_pnl < 0 else "⚪"
            print(f"\n{total_icon} TOPLAM PnL (ACTIVE + CLOSED): {grand_total_pnl:+.2f}%")
            print(f"   💰 Active Positions PnL: {total_active_pnl:+.2f}%")
            print(f"   📋 Closed Positions PnL: {closed_total_pnl:+.2f}%")
            
            # Kar/Zarar durumu
            print(f"\n💰 ACTIVE POSITIONS STATUS:")
            print(f"   🟢 In Profit: {len(in_profit)} signals")
            print(f"   🔴 In Loss: {len(in_loss)} signals")
            print(f"   ⚪ Breakeven: {len(breakeven)} signals")
            print(f"   📊 Average PnL: {avg_active_pnl:+.2f}%")
            
            # En iyi 5 karlı
            if in_profit:
                print(f"\n🔥 TOP 5 PROFITABLE SIGNALS:")
                sorted_profit = sorted(in_profit, key=lambda x: x['pnl_pct'], reverse=True)[:5]
                
                for s in sorted_profit:
                    sl_distance = abs(s['current_price'] - s['stop_loss']) / s['stop_loss'] * 100
                    print(f"   🟢 {s['symbol']:<12} {s['pnl_pct']:+6.2f}% | ${s['current_price']:.4f} | " +
                          f"SL: {sl_distance:.2f}% away | {s['signal_type']}")
            
            # En kötü 5 zararlı
            if in_loss:
                print(f"\n⚠️  TOP 5 LOSING SIGNALS:")
                sorted_loss = sorted(in_loss, key=lambda x: x['pnl_pct'])[:5]
                
                for s in sorted_loss:
                    sl_distance = abs(s['current_price'] - s['stop_loss']) / s['stop_loss'] * 100
                    print(f"   🔴 {s['symbol']:<12} {s['pnl_pct']:+6.2f}% | ${s['current_price']:.4f} | " +
                          f"SL: {sl_distance:.2f}% away | {s['signal_type']}")
            
            # Kapanan pozisyonlar
            if closed:
                print(f"\n📋 CLOSED POSITIONS (Son {min(len(closed), 10)}):")
                recent_closed = sorted(closed, key=lambda x: x.get('closed_at', x['added_at']), reverse=True)[:10]
                
                for s in recent_closed:
                    status_icon = "🛑" if s['status'] == 'stopped' else "✅"
                    final_pnl = s.get('final_pnl', s['pnl_pct'])
                    pnl_icon = "🟢" if final_pnl > 0 else "🔴"
                    closed_time = s.get('closed_at', s['added_at']).strftime('%H:%M:%S')
                    print(f"   {status_icon} {pnl_icon} {s['symbol']:<12} {final_pnl:+6.2f}% | " +
                          f"{s['status'].upper():<10} | {s['signal_type']:<15} | {closed_time}")
                
                # Kapanan pozisyonların istatistikleri
                winning_trades = len([s for s in closed if s.get('final_pnl', s['pnl_pct']) > 0])
                losing_trades = len([s for s in closed if s.get('final_pnl', s['pnl_pct']) < 0])
                win_rate = (winning_trades / len(closed) * 100) if closed else 0
                
                print(f"\n   📊 Closed Stats:")
                print(f"      Total PnL: {closed_total_pnl:+.2f}% | Avg: {closed_avg_pnl:+.2f}%")
                print(f"      Win: {winning_trades} | Loss: {losing_trades} | Win Rate: {win_rate:.1f}%")
            else:
                print(f"\n📋 No closed positions yet")
            
            print("="*100 + "\n")
    
    async def stop(self):
        """WebSocket bağlantısını kapat"""
        logger.info("Stopping WebSocket tracker...")
        self.running = False
        
        if self.client:
            await self.client.close_connection()


# ============================================================================
# MAIN FUNCTION
# ============================================================================

async def main():
    """Ana WebSocket tracker"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # İlk taramayı yap
    print("\n🔍 Running initial signal scan...")
    from ema_crossover_scanner import (
        MultiTimeframeConfig, 
        get_usdt_futures_symbols,
        comprehensive_signal_scan
    )
    
    config = MultiTimeframeConfig()
    config.current_mode = 'moderate'  # Orta seviye
    
    symbols = get_usdt_futures_symbols(limit=100)
    scan_results = comprehensive_signal_scan(symbols, config)
    
    # Sadece HIGH priority sinyalleri al
    high_priority = [
        s for s in scan_results['signals'] 
        if s.get('priority_score', 0) > 200 and s.get('validation', {}).get('is_valid', False)
    ]
    
    print(f"\n✅ Found {len(high_priority)} high-priority signals to track\n")
    
    if not high_priority:
        print("❌ No high-priority signals found. Exiting.")
        return
    
    # Signal tracker oluştur
    tracker = SignalTracker()
    tracker.add_signals(high_priority[:20])  # İlk 20 yüksek öncelikli
    
    # WebSocket tracker başlat
    ws_tracker = WebSocketPriceTracker(tracker)
    
    try:
        print("\n🚀 Starting WebSocket real-time tracking...\n")
        await ws_tracker.start()
    except KeyboardInterrupt:
        print("\n⚠️ Stopping tracker...")
        await ws_tracker.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        await ws_tracker.stop()


if __name__ == "__main__":
    asyncio.run(main())
