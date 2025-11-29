#!/usr/bin/env python3
"""
Trend Finder Debug - Koşulları detaylı gösteren versiyon
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional


class TechnicalIndicators:
    """Basit teknik gösterge hesaplayıcı"""
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI hesapla"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
        """EMA hesapla"""
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_macd(prices: pd.Series) -> Dict:
        """MACD hesapla"""
        ema_12 = prices.ewm(span=12, adjust=False).mean()
        ema_26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        
        return {
            'macd': macd,
            'signal': signal,
            'histogram': histogram
        }


class TrendFinderDebug:
    """
    Debug trend tespit sistemi
    Tüm koşulları detaylı gösterir
    """
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
        
    def generate_sample_data(self, symbol: str, trend_type: str = "up") -> pd.DataFrame:
        """Örnek veri oluştur"""
        np.random.seed(42)
        
        if trend_type == "up":
            # Çok güçlü yukarı trend
            base_price = 100
            trend = np.cumsum(np.random.normal(2.0, 1.0, 100))  # Çok güçlü pozitif trend
        else:
            # Aşağı trend
            base_price = 100
            trend = np.cumsum(np.random.normal(-2.0, 1.0, 100))  # Çok güçlü negatif trend
        
        prices = base_price + trend
        
        # OHLCV verisi oluştur
        dates = pd.date_range(start='2024-01-01', periods=100, freq='H')
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices + np.random.normal(0, 0.3, 100),
            'high': prices + np.abs(np.random.normal(0.5, 0.3, 100)),
            'low': prices - np.abs(np.random.normal(0.5, 0.3, 100)),
            'close': prices,
            'volume': np.random.uniform(10000, 50000, 100)  # Çok yüksek hacim
        })
        
        df.set_index('timestamp', inplace=True)
        return df
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> Dict:
        """Teknik göstergeleri hesapla"""
        try:
            if df is None or len(df) < 50:
                return {}
            
            # RSI hesapla
            df['rsi'] = self.indicators.calculate_rsi(df['close'], period=14)
            
            # MACD hesapla
            macd_data = self.indicators.calculate_macd(df['close'])
            df['macd'] = macd_data['macd']
            df['macd_signal'] = macd_data['signal']
            df['macd_histogram'] = macd_data['histogram']
            
            # EMA'ları hesapla
            df['ema_9'] = self.indicators.calculate_ema(df['close'], period=9)
            df['ema_21'] = self.indicators.calculate_ema(df['close'], period=21)
            df['ema_50'] = self.indicators.calculate_ema(df['close'], period=50)
            
            # Son değerleri al
            latest = df.iloc[-1]
            prev_1 = df.iloc[-2] if len(df) > 1 else latest
            prev_2 = df.iloc[-3] if len(df) > 2 else prev_1
            prev_3 = df.iloc[-4] if len(df) > 3 else prev_2
            
            return {
                'current_price': latest['close'],
                'rsi': latest['rsi'],
                'macd_histogram': latest['macd_histogram'],
                'macd_signal': latest['macd_signal'],
                'ema_9': latest['ema_9'],
                'ema_21': latest['ema_21'],
                'ema_50': latest['ema_50'],
                'volume': latest['volume'],
                
                # Trend analizi için geçmiş değerler
                'prev_rsi': prev_1['rsi'],
                'prev_macd_hist': prev_1['macd_histogram'],
                'prev_ema_9': prev_1['ema_9'],
                'prev_ema_21': prev_1['ema_21'],
                
                'prev2_rsi': prev_2['rsi'],
                'prev2_macd_hist': prev_2['macd_histogram'],
                'prev2_ema_9': prev_2['ema_9'],
                'prev2_ema_21': prev_2['ema_21'],
                
                'prev3_rsi': prev_3['rsi'],
                'prev3_macd_hist': prev_3['macd_histogram'],
                'prev3_ema_9': prev_3['ema_9'],
                'prev3_ema_21': prev_3['ema_21'],
            }
            
        except Exception as e:
            print(f"❌ Teknik göstergeler hesaplanırken hata: {e}")
            return {}
    
    def analyze_trend_conditions_debug(self, symbol: str, indicators: Dict):
        """
        Trend koşullarını debug modda analiz et
        """
        if not indicators:
            print("❌ Göstergeler yok")
            return
        
        print(f"\n🔍 {symbol} DEBUG ANALİZİ:")
        print("-" * 40)
        
        # RSI koşulu
        rsi_condition = indicators['rsi'] > 60
        print(f"📈 RSI: {indicators['rsi']:.1f} > 60? {rsi_condition} ({'✅' if rsi_condition else '❌'})")
        
        # MACD koşulu
        macd_condition = (indicators['macd_histogram'] > 0 and 
                        indicators['macd_histogram'] > indicators['prev_macd_hist'])
        print(f"📊 MACD Histogram: {indicators['macd_histogram']:.4f}")
        print(f"   Önceki MACD: {indicators['prev_macd_hist']:.4f}")
        print(f"   MACD > 0 ve artıyor? {macd_condition} ({'✅' if macd_condition else '❌'})")
        
        # EMA cross koşulu
        current_ema9_above_ema21 = indicators['ema_9'] > indicators['ema_21']
        prev_ema9_above_ema21 = indicators['prev_ema_9'] > indicators['prev_ema_21']
        prev2_ema9_above_ema21 = indicators['prev2_ema_9'] > indicators['prev2_ema_21']
        prev3_ema9_above_ema21 = indicators['prev3_ema_9'] > indicators['prev3_ema_21']
        
        print(f"📉 EMA9: {indicators['ema_9']:.2f}")
        print(f"📉 EMA21: {indicators['ema_21']:.2f}")
        print(f"📉 EMA50: {indicators['ema_50']:.2f}")
        print(f"   EMA9 > EMA21? {current_ema9_above_ema21}")
        print(f"   Önceki EMA9 > EMA21? {prev_ema9_above_ema21}")
        print(f"   2 önceki EMA9 > EMA21? {prev2_ema9_above_ema21}")
        print(f"   3 önceki EMA9 > EMA21? {prev3_ema9_above_ema21}")
        
        # Cross tespiti
        ema_cross_condition = False
        ema_trend_strength = 0
        
        if not prev3_ema9_above_ema21 and prev2_ema9_above_ema21:
            ema_cross_condition = True
            ema_trend_strength = 3
            print(f"   ✅ EMA Cross: 3 mum önce oluşmuş")
        elif not prev2_ema9_above_ema21 and prev_ema9_above_ema21:
            ema_cross_condition = True
            ema_trend_strength = 2
            print(f"   ✅ EMA Cross: 2 mum önce oluşmuş")
        elif not prev_ema9_above_ema21 and current_ema9_above_ema21:
            ema_cross_condition = True
            ema_trend_strength = 1
            print(f"   ✅ EMA Cross: 1 mum önce oluşmuş")
        else:
            print(f"   ❌ EMA Cross: Son 3 mumda cross yok")
        
        # EMA hizalama
        ema_alignment = (indicators['ema_9'] > indicators['ema_21'] > indicators['ema_50'])
        print(f"🎯 EMA Hizalama (9>21>50)? {ema_alignment} ({'✅' if ema_alignment else '❌'})")
        
        # Sonuç
        all_conditions_met = rsi_condition and macd_condition and ema_cross_condition
        print(f"\n🎯 TÜM KOŞULLAR SAĞLANDI MI? {all_conditions_met}")
        
        if all_conditions_met:
            print("🚀 TREND TESPİT EDİLDİ!")
        else:
            print("❌ Trend tespit edilemedi")
            
        print("-" * 40)
    
    def analyze_symbol_debug(self, symbol: str, trend_type: str = "up"):
        """Tek bir sembolü debug modda analiz et"""
        try:
            # Örnek veri oluştur
            df = self.generate_sample_data(symbol, trend_type)
            
            # Teknik göstergeleri hesapla
            indicators = self.calculate_technical_indicators(df)
            if not indicators:
                print(f"❌ {symbol} için göstergeler hesaplanamadı")
                return
            
            # Debug analizi yap
            self.analyze_trend_conditions_debug(symbol, indicators)
            
        except Exception as e:
            print(f"❌ {symbol} analiz edilirken hata: {e}")


def main():
    """Ana fonksiyon"""
    print("🚀 Trend Finder Debug Başlatılıyor...")
    print("Debug mod: Tüm koşullar detaylı gösterilecek")
    print("=" * 60)
    
    finder = TrendFinderDebug()
    
    # Test sembolleri
    test_symbols = [
        ("BTCUSDT", "up"),      # Yukarı trend
        ("ETHUSDT", "up"),      # Yukarı trend  
        ("ADAUSDT", "down"),    # Aşağı trend
    ]
    
    for symbol, trend_type in test_symbols:
        finder.analyze_symbol_debug(symbol, trend_type)
    
    print("\n" + "=" * 60)
    print("💡 Yarı otomatik mod: Algoritma tespit eder, siz karar verirsiniz!")
    print("Gerçek veriler için trend_finder.py kullanın.")


if __name__ == "__main__":
    main()
