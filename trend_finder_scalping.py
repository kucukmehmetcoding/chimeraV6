#!/usr/bin/env python3
"""
QUANTUM SCALPER - Ultra Aggressive Trading System
High-frequency, high-leverage scalping with instant execution
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import sys
import os

# Proje modüllerini ekle
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET,
    BLACKLISTED_SYMBOLS, PRE_SCREEN_MIN_VOLUME_USD
)
from src.data_fetcher.binance_fetcher import get_binance_klines, get_all_futures_usdt_symbols
from src.technical_analyzer.indicators import calculate_indicators

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
    5m-15m timeframe + Yüksek kaldıraç + Anlık execution
    """
    
    def __init__(self):
        self.detected_setups = []
        self.analysis_timeframes = ['5m', '15m']  # Scalping için optimize
        self.min_volume = 5000000  # 5M USD minimum hacim
        self.leverage = 10  # Varsayılan kaldıraç
        
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
        """Pozisyon büyüklüğüne göre kaldıraç hesaplama"""
        base_leverage = 5
        
        # Skor bonusu
        if score >= 7:
            base_leverage += 8
        elif score >= 5:
            base_leverage += 5
        elif score >= 4:
            base_leverage += 3
        
        # Aciliyet bonusu
        if urgency == "EXTREME":
            base_leverage += 5
        elif urgency == "HIGH":
            base_leverage += 3
        
        # Volatilite sınırlaması
        if atr_percent > 3.0:
            base_leverage = max(3, base_leverage - 5)
        elif atr_percent > 2.0:
            base_leverage = max(5, base_leverage - 3)
        
        return min(base_leverage, 20)  # Maksimum 20x kaldıraç

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

    async def scan_market(self) -> List[Dict]:
        """Tüm piyasayı ultra hızlı tarama"""
        logger.info("QUANTUM SCALPER piyasa taraması başlatılıyor...")
        
        symbols = await self.get_all_futures_symbols()
        if not symbols:
            return []
        
        logger.info(f"{len(symbols)} sembol taranacak")
        
        scalping_opportunities = []
        batch_size = 8  # Daha hızlı tarama
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            
            tasks = [self.analyze_symbol(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict) and result.get('valid_signal'):
                    scalping_opportunities.append(result)
            
            # Çok hızlı tarama için minimum bekleme
            if i + batch_size < len(symbols):
                await asyncio.sleep(0.5)
        
        # Skora ve aciliyete göre sırala
        scalping_opportunities.sort(key=lambda x: (x['urgency'], x['score']), reverse=True)
        
        logger.info(f"Tarama tamamlandı. {len(scalping_opportunities)} scalping fırsatı bulundu")
        return scalping_opportunities

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
        """Quantum tarama çalıştır"""
        try:
            logger.info("QUANTUM SCALPER başlatılıyor...")
            
            opportunities = await self.scan_market()
            
            report = self.format_scalping_report(opportunities)
            print(report)
            
            logger.info(f"Quantum tarama tamamlandı. {len(opportunities)} fırsat bulundu")
            return opportunities
            
        except Exception as e:
            logger.error(f"Quantum tarama sırasında hata: {e}")
            return []

async def main():
    """Ana fonksiyon"""
    try:
        scalper = QuantumScalper()
        
        print("🚀 QUANTUM SCALPER - Ultra Agresif Trading Bot")
        print("Binance Futures - Yüksek Kaldıraçlı Scalping")
        print("=" * 80)
        print("⚡ Sistem: 5m-15m Anlık Sinyal + Volume Spike + Momentum")
        print("🎯 Hedef: %1-3 Hızlı Kar (Kaldıraçlı)")
        print("💰 Kaldıraç: 5x-20x Otomatik Ayarlı")
        print("⏰ Pozisyon Süresi: 5-15 dakika")
        print("")
        print("⚠️  UYARI: Bu sistem YÜKSEK RİSK içerir!")
        print("    Sadece deneyimli trader'lar kullanmalıdır")
        print("")
        
        opportunities = await scalper.run_quantum_scan()
        
        if opportunities:
            extreme_ops = [o for o in opportunities if o['urgency'] == 'EXTREME']
            high_ops = [o for o in opportunities if o['urgency'] == 'HIGH']
            
            print(f"\n🎉 QUANTUM TARAMA TAMAMLANDI!")
            print(f"🚨 EXTREME Acil: {len(extreme_ops)} sinyal")
            print(f"🔴 HIGH Acil: {len(high_ops)} sinyal")
            print(f"💰 Toplam: {len(opportunities)} scalping fırsatı")
            print("\n⚡ 'ÖNCELİKLİ AKSİYON LİSTESİ'nden hemen işleme başlayabilirsiniz!")
            print("💎 Unutmayın: HIZ ve DİSİPLİN en önemli faktörlerdir!")
        else:
            print("\n📉 Hiç scalping fırsatı bulunamadı.")
            print("💡 Piyasa koşulları scalping için uygun değil.")
            print("   • Daha sonra tekrar deneyin")
            print("   • Trend yönü değişmiş olabilir")
            print("   • Piyasa çok sakin veya aşırı volatil")
            
    except Exception as e:
        print(f"❌ Sistem hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())