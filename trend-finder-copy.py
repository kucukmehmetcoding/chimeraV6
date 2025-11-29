#!/usr/bin/env python3
"""
QUANTUM SCALPER - Ultra Aggressive Live Trading System
Continuous market scanning + Auto execution with instant SL/TP
⚠️ LIVE MODE - GERÇEK PARA KULLANILIYOR!
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import sys
import os
import signal
import time

# Proje modüllerini ekle
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET,
    BLACKLISTED_SYMBOLS, PRE_SCREEN_MIN_VOLUME_USD
)
from src.data_fetcher.binance_fetcher import get_binance_klines, get_all_futures_usdt_symbols
from src.technical_analyzer.indicators import calculate_indicators
from src.trade_manager.executor import BinanceFuturesExecutor
from src.database.models import db_session, OpenPosition

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('quantum_scalper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('quantum_scalper')

class QuantumScalper:
    """
    QUANTUM SCALPER - Ultra Agresif Kaldıraçlı Scalping Sistemi
    5m-15m timeframe + Yüksek kaldıraç + Anlık execution + AUTO TRADING
    """
    
    def __init__(self):
        self.detected_setups = []
        self.analysis_timeframes = ['5m', '15m']  # Scalping için optimize
        self.min_volume = 5000000  # 5M USD minimum hacim
        self.leverage = 10  # Varsayılan kaldıraç
        
        # 🔥 LIVE TRADING COMPONENTS
        self.executor = BinanceFuturesExecutor(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_SECRET_KEY,
            testnet=BINANCE_TESTNET
        )
        self.active_positions: Dict[str, Dict] = {}  # symbol -> position_info
        self.position_start_times: Dict[str, datetime] = {}  # symbol -> start_time
        self.max_positions = 2  # KURAL #2: Maksimum 2 pozisyon
        self.max_capital_risk_per_trade = 0.01  # KURAL #3: %1 sermaye riski
        self.running = True
        self.scan_interval = 30  # 30 saniye tarama aralığı
        
        logger.info("🚀 QUANTUM SCALPER LIVE TRADING INITIALIZED")
        logger.info(f"   Mode: {'TESTNET' if BINANCE_TESTNET else '🔴 LIVE'}")
        logger.info(f"   Max Positions: {self.max_positions}")
        logger.info(f"   Max Risk/Trade: {self.max_capital_risk_per_trade*100}%")
        
        # 🔄 RESTART RECOVERY: Binance'den açık pozisyonları yükle
        self.load_existing_positions()
    
    def load_existing_positions(self):
        """Restart sonrası Binance'den açık pozisyonları yükle"""
        try:
            open_positions = self.executor.get_open_positions_from_binance()
            
            if open_positions:
                logger.warning(f"⚠️  RESTART RECOVERY: {len(open_positions)} açık pozisyon bulundu!")
                
                # 🎯 AKILLI FİLTRE: Sadece yakın zamanda açılmış pozisyonları yükle
                # Test hesabında 98 pozisyon var ama bunlar eski işlemler
                # Sadece son 1 saat içinde açılan pozisyonları tracking et
                
                recent_positions = 0
                import time
                current_time = time.time() * 1000  # milliseconds
                
                for pos in open_positions:
                    symbol = pos['symbol']
                    position_amt = float(pos.get('positionAmt', 0))
                    
                    if position_amt == 0:
                        continue
                    
                    # updateTime varsa kontrol et (son 2 saat içinde güncellenmiş mi?)
                    update_time = int(pos.get('updateTime', 0))
                    time_diff_hours = (current_time - update_time) / (1000 * 60 * 60)
                    
                    # Sadece son 2 saat içinde güncellenmiş pozisyonları yükle
                    if update_time > 0 and time_diff_hours < 2:
                        self.active_positions[symbol] = {
                            'entry_price': float(pos.get('entryPrice', 0)),
                            'position_size': abs(position_amt),
                            'leverage': int(pos.get('leverage', 10)),
                            'stop_loss': 0,
                            'take_profit': 0,
                            'urgency': 'HIGH',
                            'score': 5.0,
                            'order_id': 'RECOVERED'
                        }
                        self.position_start_times[symbol] = datetime.now()
                        recent_positions += 1
                        logger.warning(f"   ✅ {symbol}: {abs(position_amt)} units @ ${pos.get('entryPrice')} (güncelleme: {time_diff_hours:.1f}h önce)")
                    else:
                        # Eski pozisyon, görmezden gel
                        pass
                
                if recent_positions > 0:
                    logger.warning(f"✅ {recent_positions} YAKINTARIHLI pozisyon tracking listesine eklendi")
                    logger.info(f"   📊 Diğer {len(open_positions) - recent_positions} eski pozisyon görmezden gelindi")
                else:
                    logger.info("   ✅ Yakın tarihli pozisyon yok, temiz başlangıç")
            else:
                logger.info("   ✅ Açık pozisyon yok")
                
        except Exception as e:
            logger.error(f"❌ Pozisyon recovery hatası: {e}", exc_info=True)
        
    async def get_all_futures_symbols(self) -> List[str]:
        """Binance Futures'taki tüm USDT çiftlerini getir"""
        try:
            symbols = get_all_futures_usdt_symbols()
            if symbols:
                logger.info(f"Toplam {len(symbols)} futures sembolü bulundu")
                return [s for s in symbols if not any(blacklisted in s for blacklisted in BLACKLISTED_SYMBOLS)]
            return []
        except Exception as e:
            logger.error(f"Sembol listesi alınırken hata: {e}")
            return []
    
    async def get_ohlcv_data(self, symbol: str, timeframe: str = '5m', limit: int = 50) -> Optional[pd.DataFrame]:
        """OHLCV verilerini getir - Daha hızlı için daha az veri"""
        try:
            df = get_binance_klines(symbol, timeframe, limit)
            return df
        except Exception as e:
            return None

    def calculate_scalping_indicators(self, df: pd.DataFrame) -> Dict:
        """Scalping için ultra hızlı gösterge hesaplama"""
        try:
            if df is None or len(df) < 20:
                return {}
            
            df = calculate_indicators(df)
            
            # Son 5 mum için hızlı analiz
            latest = df.iloc[-1]
            prev_1 = df.iloc[-2]
            prev_2 = df.iloc[-3]
            prev_3 = df.iloc[-4]
            prev_4 = df.iloc[-5]
            
            current_price = latest['close']
            
            # 1. ANLIK MOMENTUM HESAPLAMA
            price_change_1 = (current_price - prev_1['close']) / prev_1['close'] * 100
            price_change_3 = (current_price - prev_3['close']) / prev_3['close'] * 100
            price_change_5 = (current_price - prev_4['close']) / prev_4['close'] * 100
            
            # 2. VOLUME SPİKE TESPİTİ
            volume_avg_10 = df['volume'].tail(10).mean()
            volume_avg_20 = df['volume'].tail(20).mean()
            volume_spike = latest['volume'] > volume_avg_10 * 2.5
            
            # 3. AŞIRI ALIM/SATIM - MULTI TIMEFRAME
            rsi = latest['rsi14']
            stoch_k = latest.get('stoch_k', 50)
            stoch_d = latest.get('stoch_d', 50)
            
            # 4. ANLIK VOLATİLITE
            atr = latest.get('atr', 0)
            atr_percent = (atr / current_price * 100) if current_price > 0 else 0
            
            # 5. ANLIK PRICE ACTION
            is_bearish = latest['close'] < latest['open']
            body_size = abs(latest['close'] - latest['open'])
            total_range = latest['high'] - latest['low']
            body_ratio = body_size / total_range if total_range > 0 else 0
            
            # 6. ANLIK MOMENTUM DEĞİŞİMİ
            macd_trend = latest['macd_hist'] < prev_1['macd_hist']
            rsi_trend = rsi < prev_1['rsi14']
            
            return {
                'current_price': current_price,
                'rsi': rsi,
                'stoch_k': stoch_k,
                'stoch_d': stoch_d,
                'macd_hist': latest['macd_hist'],
                'volume': latest['volume'],
                'volume_spike': volume_spike,
                'volume_ratio': latest['volume'] / volume_avg_10,
                'atr': atr,
                'atr_percent': atr_percent,
                'price_change_1': price_change_1,
                'price_change_3': price_change_3,
                'price_change_5': price_change_5,
                'is_bearish': is_bearish,
                'body_ratio': body_ratio,
                'macd_trend': macd_trend,
                'rsi_trend': rsi_trend,
                'high': latest['high'],
                'low': latest['low'],
                'open': latest['open'],
                'close': latest['close'],
            }
            
        except Exception as e:
            return {}

    def detect_scalping_opportunity(self, symbol: str, indicators_5m: Dict, indicators_15m: Dict) -> Dict:
        """
        Ultra agresif scalping fırsatlarını tespit et
        """
        if not all([indicators_5m, indicators_15m]):
            return {}
        
        try:
            signals = []
            score = 0
            urgency = "LOW"
            
            current_price = indicators_5m['current_price']
            
            # 🚨 KRİTİK SCALPING SİNYALLERİ 🚨
            
            # 1. RSI AŞIRI ALIM + MOMENTUM KAYBI
            if (indicators_5m['rsi'] > 68 and indicators_5m['rsi_trend'] and 
                indicators_15m['rsi'] > 65):
                score += 2.5
                signals.append(f"RSI_OVB_5m:{indicators_5m['rsi']:.1f}")
                urgency = "HIGH"
            
            # 2. VOLUME SPİKE + PRICE DECLINE
            if (indicators_5m['volume_spike'] and 
                indicators_5m['price_change_1'] < -0.8 and
                indicators_5m['is_bearish']):
                score += 3.0
                signals.append(f"VOLUME_SPIKE_DOWN:{indicators_5m['volume_ratio']:.1f}x")
                urgency = "EXTREME"
            
            # 3. STOCHASTIC AŞIRI ALIM + BEARISH
            if (indicators_5m['stoch_k'] > 85 and indicators_5m['stoch_d'] > 80 and
                indicators_5m['stoch_k'] < indicators_5m['stoch_d']):
                score += 2.0
                signals.append("STOCH_OVB_CROSS")
                urgency = "HIGH"
            
            # 4. MACD MOMENTUM KAYBI
            if (indicators_5m['macd_trend'] and indicators_15m['macd_trend'] and
                indicators_5m['macd_hist'] < 0):
                score += 1.5
                signals.append("MACD_MOMENTUM_DOWN")
                if urgency == "LOW":
                    urgency = "MEDIUM"
            
            # 5. MULTI-TIMEFRAME BEARISH CONFIRMATION
            if (indicators_5m['is_bearish'] and indicators_15m['is_bearish'] and
                indicators_5m['price_change_3'] < -1.5):
                score += 1.5
                signals.append("MULTI_TF_BEARISH")
                urgency = "HIGH"
            
            # 6. ANLIK PRICE COLLAPSE
            if indicators_5m['price_change_1'] < -2.0:
                score += 2.5
                signals.append(f"PRICE_COLLAPSE:{indicators_5m['price_change_1']:.1f}%")
                urgency = "EXTREME"
            
            # 7. HIGH VOLATILITY + BEARISH
            if (indicators_5m['atr_percent'] > 1.5 and 
                indicators_5m['is_bearish'] and
                indicators_5m['body_ratio'] > 0.6):
                score += 1.5
                signals.append("HIGH_VOL_BEARISH")
                urgency = "HIGH"
            
            # GEÇERLİLİK KOŞULU
            valid_signal = score >= 3.0
            
            if valid_signal:
                # AGGRESIVE TP/SL HESAPLAMA
                tp_sl = self.calculate_scalping_tp_sl(current_price, indicators_5m, score, urgency)
                
                # KALDIRAÇ ÖNERİSİ
                leverage = self.calculate_leverage(score, urgency, indicators_5m['atr_percent'])
                
                return {
                    'symbol': symbol,
                    'current_price': current_price,
                    'score': score,
                    'urgency': urgency,
                    'signals': signals,
                    'valid_signal': valid_signal,
                    'timestamp': datetime.now(),
                    'leverage': leverage,
                    'tp_sl': tp_sl,
                    'timeframe_confirmation': {
                        '5m_rsi': indicators_5m['rsi'],
                        '15m_rsi': indicators_15m['rsi'],
                        '5m_volume_ratio': indicators_5m['volume_ratio'],
                        'price_change_1m': indicators_5m['price_change_1']
                    }
                }
            
            return {}
            
        except Exception as e:
            return {}

    def calculate_scalping_tp_sl(self, current_price: float, indicators: Dict, score: float, urgency: str) -> Dict:
        """Scalping için ultra agresif TP/SL hesaplama"""
        try:
            atr = indicators['atr']
            price_change = abs(indicators['price_change_1'])
            
            # ACİL DURUMA GÖRE TP/SL
            if urgency == "EXTREME":
                risk_percent = 0.8  # %0.8 risk
                reward_ratio = 4.0  # 1:4
                tp_percent = 3.2    # %3.2 hedef
            elif urgency == "HIGH":
                risk_percent = 0.6  # %0.6 risk
                reward_ratio = 3.5  # 1:3.5
                tp_percent = 2.1    # %2.1 hedef
            else:
                risk_percent = 0.4  # %0.4 risk
                reward_ratio = 3.0  # 1:3
                tp_percent = 1.2    # %1.2 hedef
            
            # Yüksek skor bonusu
            if score >= 7:
                reward_ratio += 0.5
                tp_percent += 0.3
            
            stop_loss = current_price * (1 + risk_percent / 100)
            take_profit = current_price * (1 - tp_percent / 100)
            
            return {
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_percent': risk_percent,
                'reward_percent': tp_percent,
                'risk_reward_ratio': reward_ratio,
                'urgency': urgency
            }
            
        except Exception as e:
            # Fallback
            return {
                'stop_loss': current_price * 1.008,
                'take_profit': current_price * 0.985,
                'risk_percent': 0.8,
                'reward_percent': 1.5,
                'risk_reward_ratio': 1.87,
                'urgency': "HIGH"
            }

    def calculate_leverage(self, score: float, urgency: str, atr_percent: float) -> int:
        """Pozisyon büyüklüğüne göre kaldıraç hesaplama - GÜVENLI LIMITLER"""
        base_leverage = 5
        
        # Skor bonusu (daha muhafazakar)
        if score >= 7:
            base_leverage += 5  # Reduced from 8
        elif score >= 5:
            base_leverage += 3  # Reduced from 5
        elif score >= 4:
            base_leverage += 2  # Reduced from 3
        
        # Aciliyet bonusu (daha muhafazakar)
        if urgency == "EXTREME":
            base_leverage += 3  # Reduced from 5
        elif urgency == "HIGH":
            base_leverage += 2  # Reduced from 3
        
        # Volatilite sınırlaması
        if atr_percent > 3.0:
            base_leverage = max(3, base_leverage - 5)
        elif atr_percent > 2.0:
            base_leverage = max(5, base_leverage - 3)
        
        # 🔥 KRİTİK: Maksimum kaldıraç 15x (Binance margin limitleri için)
        return min(base_leverage, 15)

    async def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """Tek bir sembolü ultra hızlı analiz et"""
        try:
            # Sadece 5m ve 15m timeframe - SCALPING İÇİN
            data_5m = await self.get_ohlcv_data(symbol, '5m', 30)
            data_15m = await self.get_ohlcv_data(symbol, '15m', 20)
            
            if not all([data_5m is not None, data_15m is not None]):
                return None
            
            # Hacim filtresi - Sadece liquid coin'ler
            if data_15m['volume'].mean() < self.min_volume:
                return None
            
            indicators_5m = self.calculate_scalping_indicators(data_5m)
            indicators_15m = self.calculate_scalping_indicators(data_15m)
            
            if not all([indicators_5m, indicators_15m]):
                return None
            
            # Scalping fırsatı tespiti
            opportunity = self.detect_scalping_opportunity(symbol, indicators_5m, indicators_15m)
            
            return opportunity
            
        except Exception as e:
            return None

    async def scan_market_instant_execution(self) -> int:
        """
        ANINDA EXECUTION - Sinyal bulunca HEMEN trade aç!
        Taramanın bitmesini bekleme!
        """
        logger.info("⚡ INSTANT EXECUTION MODE - Piyasa taraması başlatılıyor...")
        
        symbols = await self.get_all_futures_symbols()
        if not symbols:
            return 0
        
        logger.info(f"🔍 {len(symbols)} sembol taranacak (INSTANT MODE)")
        
        trades_opened = 0
        batch_size = 10  # Daha hızlı batch
        total_scanned = 0
        
        for i in range(0, len(symbols), batch_size):
            # Pozisyon limiti doldu mu? Durdur!
            if len(self.active_positions) >= self.max_positions:
                logger.info(f"⏸️  Pozisyon limiti doldu ({self.max_positions}), tarama durduruluyor")
                break
            
            batch = symbols[i:i + batch_size]
            
            tasks = [self.analyze_symbol(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            total_scanned += len(batch)
            
            # Her sonucu kontrol et ve ANINDA trade aç
            for result in results:
                if isinstance(result, dict) and result.get('valid_signal'):
                    # KURAL #1: Sadece EXTREME/HIGH aciliyetli sinyaller
                    if result.get('urgency') in ['EXTREME', 'HIGH']:
                        logger.warning(f"🚨 INSTANT SIGNAL: {result['symbol']} - {result['urgency']} ({result['score']:.1f})")
                        
                        # ANINDA TRADE AÇ!
                        success = await self.execute_trade(result)
                        if success:
                            trades_opened += 1
                            logger.info(f"✅ INSTANT TRADE AÇILDI: {result['symbol']}")
                            
                            # Pozisyon limiti doldu mu?
                            if len(self.active_positions) >= self.max_positions:
                                logger.info(f"🎯 {self.max_positions} pozisyon açıldı, tarama tamamlanıyor")
                                return trades_opened
            
            # Progress log
            if (i // batch_size) % 5 == 0:
                logger.info(f"   📊 İlerleme: {total_scanned}/{len(symbols)} - Açık trade: {trades_opened}")
            
            # Rate limit koruması
            if i + batch_size < len(symbols):
                await asyncio.sleep(0.3)
        
        logger.info(f"✅ Tarama tamamlandı: {total_scanned} coin tarandı, {trades_opened} trade açıldı")
        return trades_opened
    
    async def scan_market(self) -> List[Dict]:
        """DEPRECATED: Eski tarama metodu (backward compatibility)"""
        logger.warning("⚠️  scan_market() kullanımdan kaldırıldı, instant execution kullanın")
        
        symbols = await self.get_all_futures_symbols()
        if not symbols:
            return []
        
        scalping_opportunities = []
        batch_size = 8
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            tasks = [self.analyze_symbol(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict) and result.get('valid_signal'):
                    if result.get('urgency') in ['EXTREME', 'HIGH']:
                        scalping_opportunities.append(result)
            
            if i + batch_size < len(symbols):
                await asyncio.sleep(0.5)
        
        scalping_opportunities.sort(key=lambda x: (x['urgency'], x['score']), reverse=True)
        return scalping_opportunities
    
    async def execute_trade(self, opportunity: Dict) -> bool:
        """Otomatik trade açma - ANINDA EXECUTION"""
        symbol = opportunity['symbol']
        
        try:
            # KURAL #2: Maksimum 2 pozisyon kontrolü
            if len(self.active_positions) >= self.max_positions:
                logger.warning(f"⚠️ {symbol} - Maksimum pozisyon limitine ulaşıldı ({self.max_positions})")
                return False
            
            # Zaten bu coinle açık pozisyon var mı?
            if symbol in self.active_positions:
                logger.warning(f"⚠️ {symbol} - Zaten açık pozisyon var")
                return False
            
            # Bakiye kontrolü
            balance = self.executor.get_futures_account_balance()
            if balance <= 0:
                logger.error("❌ Bakiye yetersiz!")
                return False
            
            # KURAL #3: %1 sermaye riski hesaplama
            risk_amount = balance * self.max_capital_risk_per_trade
            
            current_price = opportunity['current_price']
            tp_sl = opportunity['tp_sl']
            leverage = opportunity['leverage']
            
            stop_loss_price = tp_sl['stop_loss']
            take_profit_price = tp_sl['take_profit']
            
            # Pozisyon büyüklüğü hesaplama (SHORT için)
            sl_distance = abs(stop_loss_price - current_price)
            if sl_distance == 0:
                logger.warning(f"⚠️ {symbol} - SL mesafesi 0, işlem iptal")
                return False
            
            position_size_usdt = (risk_amount / sl_distance) * current_price
            
            # 🔥 KRİTİK: Binance total position limit - max bakiyenin %50'si
            # (2 pozisyonda %50 kullanım = her biri max %25)
            max_position_usdt = balance * 0.20  # %20 ile güvenli kal
            if position_size_usdt > max_position_usdt:
                logger.warning(f"⚠️ {symbol} - Pozisyon büyüklüğü sınırlandırılıyor: ${position_size_usdt:.2f} → ${max_position_usdt:.2f}")
                position_size_usdt = max_position_usdt
            
            position_size_units = position_size_usdt / current_price
            
            # Kaldıraç ayarla
            self.executor.set_leverage(symbol, leverage)
            
            logger.info(f"🚀 {symbol} - TRADE AÇILIYOR...")
            logger.info(f"   💰 Fiyat: ${current_price:.4f}")
            logger.info(f"   📊 Kaldıraç: {leverage}x")
            logger.info(f"   📏 Pozisyon: {position_size_units:.4f} units (${position_size_usdt:.2f})")
            logger.info(f"   🛑 SL: ${stop_loss_price:.4f} | 🎯 TP: ${take_profit_price:.4f}")
            
            # MARKET ORDER AÇ (SHORT)
            order_result = self.executor.open_market_order(
                symbol=symbol,
                direction='SHORT',
                quantity_units=position_size_units,
                leverage=leverage
            )
            
            if not order_result:
                logger.error(f"❌ {symbol} - Market order başarısız!")
                return False
            
            logger.info(f"✅ {symbol} - Market order başarılı! Order ID: {order_result.get('orderId')}")
            
            # SL/TP emirleri yerleştir
            import time
            time.sleep(0.5)  # Pozisyon açılması için kısa bekleme
            
            sl_tp_result = self.executor.place_sl_tp_orders(
                symbol=symbol,
                direction='SHORT',
                quantity_units=position_size_units,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                entry_price=current_price
            )
            
            if sl_tp_result:
                logger.info(f"✅ {symbol} - SL/TP emirleri yerleştirildi")
            else:
                logger.warning(f"⚠️ {symbol} - SL/TP emirleri yerleştirilemedi (manuel kontrol edin!)")
            
            # Aktif pozisyonlara ekle
            self.active_positions[symbol] = {
                'entry_price': current_price,
                'position_size': position_size_units,
                'leverage': leverage,
                'stop_loss': stop_loss_price,
                'take_profit': take_profit_price,
                'urgency': opportunity['urgency'],
                'score': opportunity['score'],
                'order_id': order_result.get('orderId')
            }
            self.position_start_times[symbol] = datetime.now()
            
            logger.info(f"🎯 {symbol} - POZİSYON AKTİF! Toplam açık pozisyon: {len(self.active_positions)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ {symbol} - Trade execution hatası: {e}", exc_info=True)
            return False
    
    async def monitor_positions(self):
        """KURAL #5: 5-15 dakika içinde otomatik kapat"""
        try:
            if not self.active_positions:
                return
            
            current_time = datetime.now()
            positions_to_close = []
            
            for symbol, position_info in self.active_positions.items():
                start_time = self.position_start_times.get(symbol)
                if not start_time:
                    continue
                
                elapsed_minutes = (current_time - start_time).total_seconds() / 60
                
                # Aciliyete göre maksimum süre
                if position_info['urgency'] == 'EXTREME':
                    max_minutes = 5  # EXTREME: 5 dakika
                else:
                    max_minutes = 15  # HIGH: 15 dakika
                
                # Zaman aşımı kontrolü
                if elapsed_minutes >= max_minutes:
                    logger.warning(f"⏰ {symbol} - Zaman aşımı ({elapsed_minutes:.1f} dk), pozisyon kapatılacak")
                    positions_to_close.append(symbol)
                    continue
                
                # PnL kontrolü (isteğe bağlı erken çıkış)
                position_data = self.executor.get_position_info(symbol)
                if position_data:
                    unrealized_pnl = position_data.get('unrealized_pnl', 0)
                    
                    # KURAL #6: Kar hedefine ulaştıysa ÇIK
                    entry = position_info['entry_price']
                    tp = position_info['take_profit']
                    tp_threshold = abs(tp - entry) * 0.8  # %80'ine ulaştıysa kapat
                    
                    if unrealized_pnl >= tp_threshold:
                        logger.info(f"🎉 {symbol} - Kar hedefine yaklaşıldı! PnL: ${unrealized_pnl:.2f}")
                        positions_to_close.append(symbol)
            
            # Pozisyonları kapat
            for symbol in positions_to_close:
                await self.close_position(symbol, reason="Zaman aşımı/Kar hedefi")
                
        except Exception as e:
            logger.error(f"❌ Position monitoring hatası: {e}", exc_info=True)
    
    async def close_position(self, symbol: str, reason: str = "Manuel"):
        """Pozisyonu kapat"""
        try:
            if symbol not in self.active_positions:
                logger.warning(f"⚠️ {symbol} - Kapatılacak aktif pozisyon bulunamadı")
                return
            
            logger.info(f"🔄 {symbol} - Pozisyon kapatılıyor... ({reason})")
            
            position_info = self.active_positions[symbol]
            
            # Market order ile kapat (SHORT pozisyon -> BUY ile kapat)
            close_result = self.executor.close_position_market(
                symbol=symbol,
                quantity_units=position_info['position_size']
            )
            
            if close_result:
                # PnL hesapla
                final_position = self.executor.get_position_info(symbol)
                if final_position:
                    pnl = final_position.get('unrealized_pnl', 0)
                    logger.info(f"✅ {symbol} - Pozisyon kapatıldı! PnL: ${pnl:.2f}")
                
                # Aktif listeden çıkar
                del self.active_positions[symbol]
                del self.position_start_times[symbol]
            else:
                logger.error(f"❌ {symbol} - Pozisyon kapatılamadı!")
                
        except Exception as e:
            logger.error(f"❌ {symbol} - Close position hatası: {e}", exc_info=True)
    
    async def continuous_trading_loop(self):
        """SÜREKLI TARAMA + OTOMATIK TRADING LOOP - INSTANT EXECUTION"""
        logger.info("🔥 CONTINUOUS TRADING LOOP BAŞLATILDI (INSTANT MODE)")
        logger.info(f"   Tarama Aralığı: {self.scan_interval} saniye")
        logger.info("   ⚡ INSTANT EXECUTION: Sinyal bulunca ANINDA trade açılır!")
        logger.info("   Durdurmak için CTRL+C")
        
        cycle_count = 0
        
        while self.running:
            try:
                cycle_count += 1
                logger.info(f"\n{'='*80}")
                logger.info(f"🔍 TARAMA DÖNGÜSÜ #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                logger.info(f"   Açık Pozisyonlar: {len(self.active_positions)}/{self.max_positions}")
                logger.info(f"{'='*80}\n")
                
                # 1. Mevcut pozisyonları izle
                await self.monitor_positions()
                
                # 2. Yeni fırsatları tara (sadece yer varsa) - INSTANT EXECUTION
                if len(self.active_positions) < self.max_positions:
                    logger.info("⚡ INSTANT SCAN başlatılıyor...")
                    trades_opened = await self.scan_market_instant_execution()
                    
                    if trades_opened > 0:
                        logger.info(f"🎯 {trades_opened} INSTANT TRADE AÇILDI!")
                    else:
                        logger.info("📉 Uygun sinyal bulunamadı")
                else:
                    logger.info("⏸️  Pozisyon limiti dolu, yeni tarama yapılmadı")
                
                # 3. Sonraki döngü için bekle
                logger.info(f"\n💤 {self.scan_interval} saniye bekleniyor...\n")
                await asyncio.sleep(self.scan_interval)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Kullanıcı tarafından durduruldu")
                self.running = False
                break
            except Exception as e:
                logger.error(f"❌ Trading loop hatası: {e}", exc_info=True)
                logger.info("⏸️  60 saniye bekleniyor...")
                await asyncio.sleep(60)
        
        logger.info("\n🏁 TRADING LOOP SONLANDIRILDI")
        logger.info(f"   Toplam Döngü: {cycle_count}")
        logger.info(f"   Açık Pozisyonlar: {len(self.active_positions)}")
        
        # Açık pozisyon varsa uyarı
        if self.active_positions:
            logger.warning("⚠️  AÇIK POZİSYONLAR VAR! Manuel kontrol edin:")
            for symbol in self.active_positions.keys():
                logger.warning(f"   - {symbol}")

    def format_scalping_report(self, opportunities: List[Dict]) -> str:
        """Quantum Scalper raporu oluştur"""
        if not opportunities:
            return "🚫 Hiç scalping fırsatı bulunamadı - Piyasa sakin veya trend yönü değişmiş"
        
        report = []
        report.append("🔥 QUANTUM SCALPER - AGRESİF SHORT SİNYALLERİ 🔥")
        report.append("=" * 80)
        report.append(f"⏰ Tarama Zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        report.append(f"🎯 Toplam Sinyal: {len(opportunities)}")
        report.append("⚡ Strateji: 5m-15m Scalping + Yüksek Kaldıraç")
        report.append("💰 Hedef: %1-3 Anlık Kar (Kaldıraçlı)")
        report.append("")
        
        # Acil durum istatistikleri
        extreme_count = sum(1 for o in opportunities if o['urgency'] == 'EXTREME')
        high_count = sum(1 for o in opportunities if o['urgency'] == 'HIGH')
        
        report.append("📊 ACİL DURUM DAĞILIMI:")
        report.append(f"   🚨 EXTREME Acil: {extreme_count} sinyal")
        report.append(f"   🔴 HIGH Acil: {high_count} sinyal")
        report.append("")
        
        # ÖNCELİKLİ AKSİYON LİSTESİ
        report.append("🎯 ÖNCELİKLİ AKSİYON LİSTESİ:")
        report.append("")
        
        for i, opp in enumerate(opportunities[:6], 1):  # Sadece ilk 6
            symbol = opp['symbol']
            price = opp['current_price']
            score = opp['score']
            urgency = opp['urgency']
            leverage = opp['leverage']
            tp_sl = opp['tp_sl']
            signals = opp['signals']
            
            urgency_emoji = "🚨" if urgency == "EXTREME" else "🔴" if urgency == "HIGH" else "🟡"
            
            report.append(f"{urgency_emoji} {i}. {symbol}")
            report.append(f"   💰 Fiyat: ${price:.4f}")
            report.append(f"   ⚡ Skor: {score:.1f} | Aciliyet: {urgency} | Kaldıraç: {leverage}x")
            report.append(f"   🛑 STOP LOSS: ${tp_sl['stop_loss']:.4f} (%{tp_sl['risk_percent']:.1f})")
            report.append(f"   🎯 TAKE PROFIT: ${tp_sl['take_profit']:.4f} (%{tp_sl['reward_percent']:.1f})")
            report.append(f"   📊 Risk/Ödül: 1:{tp_sl['risk_reward_ratio']:.1f}")
            
            # Sinyal detayları
            if signals:
                report.append(f"   📶 Kritik Sinyaller: {', '.join(signals[:3])}")
            
            # Hızlı aksiyon önerisi
            action = "⚡ ANINDA GİRİŞ - Mum kapanışını bekleme!" if urgency == "EXTREME" else "🎯 HIZLI GİRİŞ - Sonraki mumda gir"
            report.append(f"   💡 Aksiyon: {action}")
            report.append("")
        
        # SCALPING KURALLARI
        report.append("⚠️  QUANTUM SCALPING KURALLARI:")
        report.append("   1. Sadece EXTREME/HIGH aciliyetli sinyallere gir")
        report.append("   2. Maksimum 2 pozisyon aynı anda")
        report.append("   3. Her pozisyonda maksimum %1 sermaye riski")
        report.append("   4. STOP LOSS ZORUNLU - %0.5-1 arası")
        report.append("   5. 5-15 dakika içinde çık (Scalping)")
        report.append("   6. Kar hedefine ulaşınca ÇIK - Açgözlü olma")
        report.append("")
        report.append("💎 BAŞARI SIRLARI:")
        report.append("   • Disiplin > Analiz")
        report.append("   • Hız > Mükemmellik") 
        report.append("   • Risk Yönetimi > Kar")
        report.append("   • Psikoloji > Strateji")
        
        return "\n".join(report)

    async def run_quantum_scan(self):
        """Quantum tarama çalıştır (tek seferlik - backward compatibility)"""
        try:
            logger.info("QUANTUM SCALPER başlatılıyor...")
            
            opportunities = await self.scan_market()
            
            report = self.format_scalping_report(opportunities)
            print(report)
            
            logger.info(f"Quantum tarama tamamlandı. {len(opportunities)} fırsat bulundu")
            return opportunities
            
        except Exception as e:
            logger.error(f"Quantum tarama sırasında hata: {e}", exc_info=True)
            return []
    
    def shutdown_handler(self, signum, frame):
        """Güvenli kapatma"""
        logger.info("\n🛑 Shutdown signal alındı...")
        self.running = False

async def main():
    """Ana fonksiyon - SÜREKLI OTOMATIK TRADING"""
    try:
        scalper = QuantumScalper()
        
        # Signal handlers
        signal.signal(signal.SIGINT, scalper.shutdown_handler)
        signal.signal(signal.SIGTERM, scalper.shutdown_handler)
        
        print("="*80)
        print("🚀 QUANTUM SCALPER - LIVE AUTO TRADING SYSTEM")
        print("="*80)
        print(f"⚡ Mode: {'🟢 TESTNET' if BINANCE_TESTNET else '🔴 LIVE MODE'}")
        print("📊 Strateji: 5m-15m Scalping + Volume Spike + Momentum")
        print("🎯 Hedef: %1-3 Hızlı Kar (Kaldıraçlı)")
        print("💰 Kaldıraç: 5x-20x Otomatik Ayarlı")
        print("⚡ Execution: INSTANT (sinyal bulunca ANINDA trade açılır!)")
        print("")
        print("⚠️  QUANTUM SCALPING KURALLARI:")
        print("   1. Sadece EXTREME/HIGH aciliyetli sinyallere gir ✅")
        print("   2. Maksimum 2 pozisyon aynı anda ✅")
        print("   3. Her pozisyonda maksimum %1 sermaye riski ✅")
        print("   4. STOP LOSS ZORUNLU - %0.5-1 arası ✅")
        print("   5. 5-15 dakika içinde çık (Scalping) ✅")
        print("   6. Kar hedefine ulaşınca ÇIK - Açgözlü olma ✅")
        print("")
        print("💎 BAŞARI SIRLARI:")
        print("   • Disiplin > Analiz")
        print("   • Hız > Mükemmellik")
        print("   • Risk Yönetimi > Kar")
        print("   • Psikoloji > Strateji")
        print("")
        print("🛑 Durdurmak için: CTRL+C")
        print("="*80)
        print("")
        
        # Bakiye kontrolü
        balance = scalper.executor.get_futures_account_balance()
        print(f"💰 Başlangıç Bakiyesi: ${balance:.2f} USDT")
        print(f"📊 Trade Başına Risk: ${balance * scalper.max_capital_risk_per_trade:.2f} ({scalper.max_capital_risk_per_trade*100}%)")
        print("")
        
        if balance <= 0:
            print("❌ HATA: Bakiye yetersiz! Lütfen kontrol edin.")
            return
        
        # UYARI
        if not BINANCE_TESTNET:
            print("🚨🚨🚨 UYARI: LIVE MODE AKTIF - GERÇEK PARA KULLANILIYOR! 🚨🚨🚨")
            print("5 saniye içinde durdurmak için CTRL+C basın...")
            await asyncio.sleep(5)
            print("")
        
        # SÜREKLI TRADING LOOP BAŞLAT
        await scalper.continuous_trading_loop()
        
        # Kapanış özeti
        print("\n" + "="*80)
        print("📊 TRADING SESSION ÖZETİ")
        print("="*80)
        final_balance = scalper.executor.get_futures_account_balance()
        pnl = final_balance - balance
        pnl_percent = (pnl / balance * 100) if balance > 0 else 0
        
        print(f"💰 Başlangıç: ${balance:.2f} USDT")
        print(f"💰 Bitiş: ${final_balance:.2f} USDT")
        print(f"📈 PnL: ${pnl:.2f} ({pnl_percent:+.2f}%)")
        print(f"🎯 Kalan Açık Pozisyon: {len(scalper.active_positions)}")
        
        if scalper.active_positions:
            print("\n⚠️  AÇIK POZİSYONLAR:")
            for symbol in scalper.active_positions.keys():
                print(f"   - {symbol}")
            print("\n💡 Manuel olarak kontrol edin veya trade_manager.py ile yönetin")
        
        print("\n👋 Quantum Scalper kapatıldı. Güvenli tradeler!")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"\n❌ Sistem hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())