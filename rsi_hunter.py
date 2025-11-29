#!/usr/bin/env python3
"""
🎯 RSI HUNTER - WebSocket Tabanlı Akıllı Short Trading Bot

Strateji:
1. RSI > 65 olan coinleri tespit et (Overbought)
2. WebSocket ile anlık fiyat takibi yap
3. Satış sinyali gelince (RSI düşüşü + bearish confirmation) SHORT aç
4. Dinamik SL/TP ile pozisyon yönet

Sinyal Mantığı:
- RSI 65+ → Watchlist'e ekle
- RSI düşmeye başladı + Bearish mum → SHORT ENTRY
- RSI < 50 veya TP/SL → EXIT
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import sys
import os
import json
import time
from collections import deque

# WebSocket imports
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException

# Proje modüllerini ekle
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET,
    BLACKLISTED_SYMBOLS
)
from src.data_fetcher.binance_fetcher import get_binance_klines, get_all_futures_usdt_symbols
from src.technical_analyzer.indicators import calculate_indicators
from src.trade_manager.executor import BinanceFuturesExecutor, initialize_executor
from src import config as src_config

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rsi_hunter.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('rsi_hunter')


class CoinTracker:
    """Tek bir coin için durum takibi"""
    
    def __init__(self, symbol: str, initial_rsi: float, initial_price: float):
        self.symbol = symbol
        self.initial_rsi = initial_rsi
        self.current_rsi = initial_rsi
        self.peak_rsi = initial_rsi  # En yüksek RSI değeri
        self.initial_price = initial_price
        self.current_price = initial_price
        self.peak_price = initial_price  # En yüksek fiyat
        self.added_time = datetime.now()
        self.last_update = datetime.now()
        
        # Sinyal durumu
        self.rsi_dropping = False  # RSI düşüyor mu?
        self.bearish_candle = False  # Son mum bearish mi?
        self.volume_spike = False  # Hacim artışı var mı?
        self.signal_triggered = False  # Sinyal tetiklendi mi?
        
        # Fiyat geçmişi (son 10 fiyat)
        self.price_history = deque(maxlen=10)
        self.price_history.append(initial_price)
        
    def update_price(self, price: float):
        """Fiyat güncelle ve analiz yap"""
        self.current_price = price
        self.last_update = datetime.now()
        self.price_history.append(price)
        
        # Peak price güncelle
        if price > self.peak_price:
            self.peak_price = price
            
    def update_rsi(self, rsi: float):
        """RSI güncelle"""
        old_rsi = self.current_rsi
        self.current_rsi = rsi
        
        # Peak RSI güncelle
        if rsi > self.peak_rsi:
            self.peak_rsi = rsi
            
        # RSI düşüyor mu kontrol et
        if old_rsi > rsi and self.peak_rsi - rsi >= 3:
            self.rsi_dropping = True
        else:
            self.rsi_dropping = False
            
    def get_price_change_percent(self) -> float:
        """Peak'ten itibaren fiyat değişimi (%)"""
        if self.peak_price == 0:
            return 0
        return ((self.current_price - self.peak_price) / self.peak_price) * 100
    
    def is_ready_for_short(self) -> bool:
        """SHORT sinyali için hazır mı?"""
        conditions = []
        
        # 1. RSI peak'ten en az 5 puan düşmüş olmalı
        rsi_drop = self.peak_rsi - self.current_rsi >= 5
        conditions.append(("RSI Drop >= 5", rsi_drop, f"Peak: {self.peak_rsi:.1f}, Current: {self.current_rsi:.1f}"))
        
        # 2. RSI hala 60 üstünde olmalı (çok geç kalmamak için)
        rsi_still_high = self.current_rsi > 55
        conditions.append(("RSI > 55", rsi_still_high, f"Current RSI: {self.current_rsi:.1f}"))
        
        # 3. Fiyat peak'ten düşmüş olmalı
        price_dropping = self.get_price_change_percent() < -0.3
        conditions.append(("Price Drop > 0.3%", price_dropping, f"Change: {self.get_price_change_percent():.2f}%"))
        
        # Tüm koşullar sağlanıyorsa
        all_met = rsi_drop and rsi_still_high and price_dropping
        
        if all_met:
            logger.info(f"🎯 {self.symbol} SHORT SİNYALİ HAZIR!")
            for name, met, detail in conditions:
                status = "✅" if met else "❌"
                logger.info(f"   {status} {name}: {detail}")
                
        return all_met
    
    def __repr__(self):
        return f"CoinTracker({self.symbol}, RSI: {self.current_rsi:.1f}, Price: ${self.current_price:.4f})"


class RSIHunter:
    """
    🎯 RSI HUNTER - Ana Bot Sınıfı
    """
    
    def __init__(self, live_trading: bool = False):
        # Ayarlar
        self.rsi_threshold = 65.0  # Watchlist için RSI eşiği
        self.timeframe = '5m'  # Analiz timeframe
        self.max_watchlist = 10  # Maksimum takip edilecek coin
        self.scan_interval = 300  # RSI tarama aralığı (saniye)
        self.update_interval = 30  # Coin güncelleme aralığı (saniye)
        
        # Trading ayarları
        self.live_trading = live_trading
        self.position_size_usdt = 60.0  # Her pozisyon için USDT
        self.max_positions = 5  # Maksimum açık pozisyon
        self.sl_percent = 0.5  # Stop Loss %
        self.tp_percent = 1.5  # Take Profit %
        self.leverage = 10  # Kaldıraç
        
        # Durum
        self.watchlist: Dict[str, CoinTracker] = {}  # Takip edilen coinler
        self.active_positions: Dict[str, dict] = {}  # Açık pozisyonlar
        self.executor = None
        self.running = True
        
        # WebSocket
        self.client = None
        self.bsm = None
        self.socket_tasks = []
        
        # İstatistikler
        self.stats = {
            'total_scans': 0,
            'signals_generated': 0,
            'trades_opened': 0,
            'trades_closed': 0,
            'total_pnl': 0.0
        }
        
        # Executor başlat
        if self.live_trading:
            logger.info("🔥 LIVE TRADING MODE - Executor başlatılıyor...")
            try:
                self.executor = initialize_executor(src_config)
                logger.info("✅ Executor başarıyla başlatıldı")
            except Exception as e:
                logger.error(f"❌ Executor başlatılamadı: {e}")
                self.live_trading = False
        else:
            logger.info("📊 SCAN-ONLY MODE - İşlem açılmayacak")
    
    # ==================== RSI TARAMA ====================
    
    def get_all_symbols(self) -> List[str]:
        """Binance Futures sembollerini getir"""
        try:
            symbols = get_all_futures_usdt_symbols()
            if symbols:
                filtered = [s for s in symbols if not any(bl in s for bl in BLACKLISTED_SYMBOLS)]
                return filtered
            return []
        except Exception as e:
            logger.error(f"❌ Sembol listesi alınamadı: {e}")
            return []
    
    def calculate_coin_rsi(self, symbol: str) -> Optional[Dict]:
        """Bir coin için RSI hesapla"""
        try:
            df = get_binance_klines(symbol, self.timeframe, limit=50)
            if df is None or df.empty or len(df) < 20:
                return None
            
            df = calculate_indicators(df)
            
            if 'rsi14' not in df.columns:
                return None
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            rsi = latest['rsi14']
            
            if pd.isna(rsi):
                return None
            
            # Bearish mum kontrolü
            is_bearish = latest['close'] < latest['open']
            
            # Hacim kontrolü
            avg_volume = df['volume'].tail(20).mean()
            volume_spike = latest['volume'] > avg_volume * 1.5
            
            return {
                'symbol': symbol,
                'rsi': rsi,
                'prev_rsi': prev['rsi14'],
                'price': latest['close'],
                'is_bearish': is_bearish,
                'volume_spike': volume_spike,
                'timeframe': self.timeframe
            }
            
        except Exception as e:
            logger.debug(f"⚠️ {symbol} RSI hesaplanamadı: {e}")
            return None
    
    def scan_for_high_rsi_coins(self) -> List[Dict]:
        """RSI > threshold olan coinleri bul"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 RSI TARAMASI BAŞLIYOR... (RSI > {self.rsi_threshold})")
        logger.info(f"{'='*60}")
        
        symbols = self.get_all_symbols()
        if not symbols:
            return []
        
        high_rsi_coins = []
        scanned = 0
        
        for symbol in symbols:
            # Zaten watchlist'te veya pozisyonda olanları atla
            if symbol in self.watchlist or symbol in self.active_positions:
                continue
                
            scanned += 1
            
            if scanned % 50 == 0:
                logger.info(f"   📊 İlerleme: {scanned}/{len(symbols)}")
            
            result = self.calculate_coin_rsi(symbol)
            
            if result and result['rsi'] > self.rsi_threshold:
                high_rsi_coins.append(result)
                logger.info(f"   ✅ {result['symbol']}: RSI {result['rsi']:.1f} | ${result['price']:.4f}")
        
        # RSI'a göre sırala (en yüksek önce)
        high_rsi_coins.sort(key=lambda x: x['rsi'], reverse=True)
        
        logger.info(f"\n📊 Tarama tamamlandı: {len(high_rsi_coins)} coin bulundu (RSI > {self.rsi_threshold})")
        
        self.stats['total_scans'] += 1
        
        return high_rsi_coins
    
    def update_watchlist(self, new_coins: List[Dict]):
        """Watchlist'i güncelle"""
        # Watchlist'te yer varsa yeni coinler ekle
        available_slots = self.max_watchlist - len(self.watchlist)
        
        for coin in new_coins[:available_slots]:
            symbol = coin['symbol']
            if symbol not in self.watchlist:
                tracker = CoinTracker(
                    symbol=symbol,
                    initial_rsi=coin['rsi'],
                    initial_price=coin['price']
                )
                self.watchlist[symbol] = tracker
                logger.info(f"➕ Watchlist'e eklendi: {symbol} (RSI: {coin['rsi']:.1f})")
        
        logger.info(f"📋 Güncel Watchlist: {len(self.watchlist)} coin")
    
    # ==================== COIN TAKİP ====================
    
    async def update_coin_data(self, symbol: str):
        """Bir coin'in verilerini güncelle"""
        try:
            result = self.calculate_coin_rsi(symbol)
            
            if result and symbol in self.watchlist:
                tracker = self.watchlist[symbol]
                tracker.update_rsi(result['rsi'])
                tracker.update_price(result['price'])
                tracker.bearish_candle = result['is_bearish']
                tracker.volume_spike = result['volume_spike']
                
                # SHORT sinyali kontrol et
                if tracker.is_ready_for_short() and not tracker.signal_triggered:
                    tracker.signal_triggered = True
                    self.stats['signals_generated'] += 1
                    
                    logger.info(f"\n🚨 {'='*50} 🚨")
                    logger.info(f"🎯 SHORT SİNYALİ: {symbol}")
                    logger.info(f"   RSI: {tracker.peak_rsi:.1f} → {tracker.current_rsi:.1f}")
                    logger.info(f"   Fiyat: ${tracker.peak_price:.4f} → ${tracker.current_price:.4f}")
                    logger.info(f"   Düşüş: {tracker.get_price_change_percent():.2f}%")
                    logger.info(f"🚨 {'='*50} 🚨\n")
                    
                    # İşlem aç
                    if self.live_trading:
                        await self.open_short_position(tracker)
                    
                # RSI çok düştüyse watchlist'ten çıkar
                if result['rsi'] < 50:
                    logger.info(f"➖ {symbol} RSI < 50, watchlist'ten çıkarıldı")
                    del self.watchlist[symbol]
                    
        except Exception as e:
            logger.error(f"❌ {symbol} güncelleme hatası: {e}")
    
    async def update_all_coins(self):
        """Tüm watchlist coinlerini güncelle"""
        if not self.watchlist:
            return
            
        logger.debug(f"🔄 {len(self.watchlist)} coin güncelleniyor...")
        
        for symbol in list(self.watchlist.keys()):
            await self.update_coin_data(symbol)
            await asyncio.sleep(0.2)  # Rate limit koruması
    
    # ==================== POZİSYON YÖNETİMİ ====================
    
    async def open_short_position(self, tracker: CoinTracker):
        """SHORT pozisyon aç"""
        symbol = tracker.symbol
        
        if len(self.active_positions) >= self.max_positions:
            logger.warning(f"⚠️ Maksimum pozisyon limitine ulaşıldı ({self.max_positions})")
            return
            
        if symbol in self.active_positions:
            logger.warning(f"⚠️ {symbol} için zaten pozisyon var")
            return
        
        try:
            current_price = tracker.current_price
            
            # SL/TP hesapla
            sl_price = current_price * (1 + self.sl_percent / 100)
            tp_price = current_price * (1 - self.tp_percent / 100)
            
            # Pozisyon büyüklüğü
            quantity = self.position_size_usdt / current_price
            
            logger.info(f"\n🚀 SHORT POZİSYON AÇILIYOR: {symbol}")
            logger.info(f"   💰 Fiyat: ${current_price:.4f}")
            logger.info(f"   📊 Miktar: {quantity:.4f} ({self.position_size_usdt} USDT)")
            logger.info(f"   🛑 SL: ${sl_price:.4f} (+{self.sl_percent}%)")
            logger.info(f"   🎯 TP: ${tp_price:.4f} (-{self.tp_percent}%)")
            logger.info(f"   ⚡ Kaldıraç: {self.leverage}x")
            
            if self.executor:
                # Kaldıraç ayarla
                self.executor.set_leverage(symbol, self.leverage)
                
                # Market order aç
                order = self.executor.open_market_order(
                    symbol=symbol,
                    direction='SHORT',
                    quantity_units=quantity,
                    leverage=self.leverage
                )
                
                if order:
                    # SL/TP yerleştir
                    time.sleep(0.3)
                    self.executor.place_sl_tp_orders(
                        symbol=symbol,
                        direction='SHORT',
                        quantity_units=quantity,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        entry_price=current_price
                    )
                    
                    # Pozisyonu kaydet
                    self.active_positions[symbol] = {
                        'entry_price': current_price,
                        'quantity': quantity,
                        'sl_price': sl_price,
                        'tp_price': tp_price,
                        'entry_time': datetime.now(),
                        'entry_rsi': tracker.current_rsi
                    }
                    
                    self.stats['trades_opened'] += 1
                    logger.info(f"✅ {symbol} SHORT pozisyon açıldı!")
                    
                    # Watchlist'ten çıkar
                    if symbol in self.watchlist:
                        del self.watchlist[symbol]
                else:
                    logger.error(f"❌ {symbol} order başarısız!")
            else:
                logger.info(f"📝 [DEMO] {symbol} SHORT pozisyon simüle edildi")
                
        except Exception as e:
            logger.error(f"❌ {symbol} pozisyon açma hatası: {e}", exc_info=True)
    
    async def check_positions(self):
        """Açık pozisyonları kontrol et"""
        if not self.active_positions:
            return
            
        for symbol in list(self.active_positions.keys()):
            try:
                pos = self.active_positions[symbol]
                
                # Güncel fiyat al
                result = self.calculate_coin_rsi(symbol)
                if not result:
                    continue
                    
                current_price = result['price']
                entry_price = pos['entry_price']
                
                # PnL hesapla (SHORT için)
                pnl_percent = ((entry_price - current_price) / entry_price) * 100 * self.leverage
                
                logger.info(f"   📊 {symbol}: ${current_price:.4f} | PnL: {pnl_percent:+.2f}%")
                
                # SL/TP kontrol (Binance zaten yapıyor ama backup olarak)
                if current_price >= pos['sl_price']:
                    logger.warning(f"🛑 {symbol} STOP LOSS!")
                    await self.close_position(symbol, "STOP_LOSS")
                elif current_price <= pos['tp_price']:
                    logger.info(f"🎯 {symbol} TAKE PROFIT!")
                    await self.close_position(symbol, "TAKE_PROFIT")
                    
            except Exception as e:
                logger.error(f"❌ {symbol} pozisyon kontrol hatası: {e}")
    
    async def close_position(self, symbol: str, reason: str):
        """Pozisyon kapat"""
        if symbol not in self.active_positions:
            return
            
        try:
            if self.executor:
                self.executor.close_position_market(symbol)
                
            pos = self.active_positions[symbol]
            del self.active_positions[symbol]
            
            self.stats['trades_closed'] += 1
            logger.info(f"✅ {symbol} pozisyon kapatıldı: {reason}")
            
        except Exception as e:
            logger.error(f"❌ {symbol} kapatma hatası: {e}")
    
    # ==================== ANA DÖNGÜ ====================
    
    def display_status(self):
        """Durum özeti göster"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 RSI HUNTER DURUMU - {datetime.now().strftime('%H:%M:%S')}")
        logger.info(f"{'='*60}")
        logger.info(f"   📋 Watchlist: {len(self.watchlist)} coin")
        logger.info(f"   📈 Aktif Pozisyon: {len(self.active_positions)}/{self.max_positions}")
        logger.info(f"   🔍 Toplam Tarama: {self.stats['total_scans']}")
        logger.info(f"   🎯 Üretilen Sinyal: {self.stats['signals_generated']}")
        logger.info(f"   💰 Açılan İşlem: {self.stats['trades_opened']}")
        
        if self.watchlist:
            logger.info(f"\n   📋 WATCHLIST:")
            for symbol, tracker in self.watchlist.items():
                rsi_change = tracker.current_rsi - tracker.peak_rsi
                logger.info(f"      {symbol}: RSI {tracker.current_rsi:.1f} ({rsi_change:+.1f}) | ${tracker.current_price:.4f}")
        
        if self.active_positions:
            logger.info(f"\n   📈 AKTİF POZİSYONLAR:")
            for symbol, pos in self.active_positions.items():
                logger.info(f"      {symbol}: Entry ${pos['entry_price']:.4f} | SL ${pos['sl_price']:.4f} | TP ${pos['tp_price']:.4f}")
        
        logger.info(f"{'='*60}\n")
    
    async def run(self):
        """Ana çalışma döngüsü"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 RSI HUNTER BAŞLATILIYOR")
        logger.info(f"{'='*60}")
        logger.info(f"   RSI Eşiği: > {self.rsi_threshold}")
        logger.info(f"   Timeframe: {self.timeframe}")
        logger.info(f"   Max Watchlist: {self.max_watchlist}")
        logger.info(f"   Live Trading: {'✅ AÇIK' if self.live_trading else '❌ KAPALI'}")
        logger.info(f"   Pozisyon Büyüklüğü: {self.position_size_usdt} USDT")
        logger.info(f"   SL/TP: {self.sl_percent}% / {self.tp_percent}%")
        logger.info(f"{'='*60}\n")
        
        last_scan_time = datetime.min
        last_update_time = datetime.min
        last_status_time = datetime.min
        
        try:
            while self.running:
                now = datetime.now()
                
                # RSI taraması (her scan_interval saniyede)
                if (now - last_scan_time).total_seconds() >= self.scan_interval:
                    high_rsi_coins = self.scan_for_high_rsi_coins()
                    self.update_watchlist(high_rsi_coins)
                    last_scan_time = now
                
                # Coin güncellemesi (her update_interval saniyede)
                if (now - last_update_time).total_seconds() >= self.update_interval:
                    await self.update_all_coins()
                    await self.check_positions()
                    last_update_time = now
                
                # Durum gösterimi (her 60 saniyede)
                if (now - last_status_time).total_seconds() >= 60:
                    self.display_status()
                    last_status_time = now
                
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Kullanıcı tarafından durduruldu")
        except Exception as e:
            logger.error(f"❌ Ana döngü hatası: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("\n🏁 RSI HUNTER SONLANDIRILDI")
            self.display_status()


async def main():
    """Ana fonksiyon"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RSI Hunter - WebSocket Short Trading Bot')
    parser.add_argument('--live', action='store_true', help='Live trading modunu aç')
    parser.add_argument('--rsi', type=float, default=65.0, help='RSI eşiği (default: 65)')
    parser.add_argument('--size', type=float, default=60.0, help='Pozisyon büyüklüğü USDT (default: 60)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 RSI HUNTER - Akıllı Short Trading Bot")
    print("=" * 60)
    print(f"📊 RSI Eşiği: > {args.rsi}")
    print(f"💰 Pozisyon: {args.size} USDT")
    print(f"🔥 Live Trading: {'AÇIK' if args.live else 'KAPALI'}")
    print("=" * 60)
    
    if args.live:
        print("\n⚠️  UYARI: LIVE TRADING MODU!")
        print("    Gerçek para ile işlem yapılacak!")
        confirm = input("    Devam etmek için 'EVET' yazın: ")
        if confirm != 'EVET':
            print("❌ İptal edildi.")
            return
    
    hunter = RSIHunter(live_trading=args.live)
    hunter.rsi_threshold = args.rsi
    hunter.position_size_usdt = args.size
    
    await hunter.run()


if __name__ == "__main__":
    asyncio.run(main())
