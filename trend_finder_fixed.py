#!/usr/bin/env python3
"""
Trend Finder Fixed - Düzeltilmiş ve optimize edilmiş versiyon
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional


class TechnicalIndicators:
    """Optimize edilmiş teknik gösterge hesaplayıcı"""
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI hesapla - düzeltilmiş versiyon"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)  # NaN değerleri 50 ile doldur
    
    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
        """EMA hesapla"""
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_macd(prices: pd.Series) -> Dict:
        """MACD hesapla - düzeltilmiş versiyon"""
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


class TrendFinderFixed:
    """
    Düzeltilmiş trend tespit sistemi
    - Daha gerçekçi koşullar
    - Daha iyi veri kalitesi
    - Optimize edilmiş algoritma
    """
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
        
    def generate_realistic_data(self, symbol: str, trend_type: str = "up") -> pd.DataFrame:
        """Gerçekçi örnek veri oluştur"""
        np.random.seed(42)
        
        if trend_type == "up":
            # Gerçekçi yukarı trend
            base_price = 100
            # Daha yumuşak trend
            trend = np.cumsum(np.random.normal(0.3, 1.2, 200))  # Daha uzun, daha yumuşak
        else:
            # Gerçekçi aşağı trend
            base_price = 100
            trend = np.cumsum(np.random.normal(-0.3, 1.2, 200))  # Daha uzun, daha yumuşak
        
        prices = base_price + trend
        
        # OHLCV verisi oluştur - daha gerçekçi
        dates = pd.date_range(start='2024-01-01', periods=200, freq='H')
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices + np.random.normal(0, 0.8, 200),
            'high': prices + np.abs(np.random.normal(1.5, 0.8, 200)),
            'low': prices - np.abs(np.random.normal(1.5, 0.8, 200)),
            'close': prices,
            'volume': np.random.uniform(5000, 30000, 200)
        })
        
        df.set_index('timestamp', inplace=True)
        return df
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> Dict:
        """Teknik göstergeleri hesapla - optimize edilmiş"""
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
            prev_4 = df.iloc[-5] if len(df) > 4 else prev_3
            
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
                
                'prev4_rsi': prev_4['rsi'],
                'prev4_macd_hist': prev_4['macd_histogram'],
                'prev4_ema_9': prev_4['ema_9'],
                'prev4_ema_21': prev_4['ema_21'],
            }
            
        except Exception as e:
            print(f"❌ Teknik göstergeler hesaplanırken hata: {e}")
            return {}
    
    def analyze_trend_conditions_fixed(self, symbol: str, indicators: Dict) -> Dict:
        """
        Düzeltilmiş trend koşulları analizi
        - Daha gerçekçi MACD koşulu
        - Daha esnek EMA cross koşulu
        - Güven skoru optimizasyonu
        """
        if not indicators:
            return {}
        
        try:
            # RSI koşulu - 55-70 arası ideal
            rsi_condition = 55 < indicators['rsi'] < 70
            
            # MACD koşulu - histogram pozitif OLMALI ve artıyor OLMALI
            # Ama çok katı değil, sadece pozitif olması yeterli
            macd_condition = indicators['macd_histogram'] > 0
            
            # EMA cross koşulu - son 5 mumda cross oluşmuş olabilir
            ema_cross_condition = False
            ema_trend_strength = 0
            
            # Mevcut ve geçmiş durumlar
            current_ema9_above_ema21 = indicators['ema_9'] > indicators['ema_21']
            prev_ema9_above_ema21 = indicators['prev_ema_9'] > indicators['prev_ema_21']
            prev2_ema9_above_ema21 = indicators['prev2_ema_9'] > indicators['prev2_ema_21']
            prev3_ema9_above_ema21 = indicators['prev3_ema_9'] > indicators['prev3_ema_21']
            prev4_ema9_above_ema21 = indicators['prev4_ema_9'] > indicators['prev4_ema_21']
            
            # Cross tespiti - son 5 mumda
            if not prev4_ema9_above_ema21 and prev3_ema9_above_ema21:
                ema_cross_condition = True
                ema_trend_strength = 4
            elif not prev3_ema9_above_ema21 and prev2_ema9_above_ema21:
                ema_cross_condition = True
                ema_trend_strength = 3
            elif not prev2_ema9_above_ema21 and prev_ema9_above_ema21:
                ema_cross_condition = True
                ema_trend_strength = 2
            elif not prev_ema9_above_ema21 and current_ema9_above_ema21:
                ema_cross_condition = True
                ema_trend_strength = 1
            
            # EMA hizalama - bonus puan için
            ema_alignment = (indicators['ema_9'] > indicators['ema_21'] > indicators['ema_50'])
            
            # Trend yönü belirleme - 2/3 koşul yeterli
            conditions_met = sum([rsi_condition, macd_condition, ema_cross_condition])
            trend_direction = "YUKARI" if conditions_met >= 2 else "BEKLİYOR"
            
            # Güven skoru (0-100) - daha dengeli
            confidence_score = 0
            if rsi_condition:
                confidence_score += 25
                # RSI ideal aralıkta mı?
                if 60 <= indicators['rsi'] <= 65:
                    confidence_score += 10
            if macd_condition:
                confidence_score += 25
                # MACD güçlü mü?
                if indicators['macd_histogram'] > indicators['prev_macd_hist']:
                    confidence_score += 10
            if ema_cross_condition:
                confidence_score += 25
                # Yeni cross daha iyi
                if ema_trend_strength <= 2:
                    confidence_score += 10
            if ema_alignment:
                confidence_score += 15
            
            return {
                'symbol': symbol,
                'trend_direction': trend_direction,
                'confidence_score': min(confidence_score, 100),  # Maksimum 100
                'current_price': indicators['current_price'],
                'volume': indicators['volume'],
                'conditions': {
                    'rsi_condition': rsi_condition,
                    'rsi_value': indicators['rsi'],
                    'macd_condition': macd_condition,
                    'macd_histogram': indicators['macd_histogram'],
                    'ema_cross_condition': ema_cross_condition,
                    'ema_trend_strength': ema_trend_strength,
                    'ema_alignment': ema_alignment,
                    'ema_9': indicators['ema_9'],
                    'ema_21': indicators['ema_21'],
                    'ema_50': indicators['ema_50'],
                    'conditions_met': conditions_met,
                    'total_conditions': 3
                },
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            print(f"❌ {symbol} trend analizi sırasında hata: {e}")
            return {}
    
    def analyze_symbol_fixed(self, symbol: str, trend_type: str = "up") -> Optional[Dict]:
        """Tek bir sembolü düzeltilmiş algoritma ile analiz et"""
        try:
            # Gerçekçi veri oluştur
            df = self.generate_realistic_data(symbol, trend_type)
            
            # Teknik göstergeleri hesapla
            indicators = self.calculate_technical_indicators(df)
            if not indicators:
                return None
            
            # Trend analizi yap
            trend_analysis = self.analyze_trend_conditions_fixed(symbol, indicators)
            
            return trend_analysis
            
        except Exception as e:
            print(f"❌ {symbol} analiz edilirken hata: {e}")
            return None
    
    def run_fixed_scan(self):
        """Düzeltilmiş tarama çalıştır"""
        print("🚀 Trend Finder Fixed Başlatılıyor...")
        print("Düzeltilmiş trend tespit sistemi")
        print("Kriterler: RSI 55-70, MACD pozitif, EMA cross son 5 mum")
        print("2/3 koşul yeterli")
        print("=" * 60)
        
        # Test sembolleri
        test_symbols = [
            ("BTCUSDT", "up"),      # Yukarı trend
            ("ETHUSDT", "up"),      # Yukarı trend  
            ("ADAUSDT", "down"),    # Aşağı trend
            ("SOLUSDT", "up"),      # Yukarı trend
            ("DOTUSDT", "down"),    # Aşağı trend
            ("BNBUSDT", "up"),      # Yukarı trend
        ]
        
        detected_trends = []
        
        for symbol, trend_type in test_symbols:
            print(f"🔍 {symbol} analiz ediliyor...")
            result = self.analyze_symbol_fixed(symbol, trend_type)
            
            if result and result.get('trend_direction') == "YUKARI":
                detected_trends.append(result)
                conditions = result['conditions']
                print(f"  ✅ Trend tespit edildi! Güven: {result['confidence_score']}/100")
                print(f"     Koşullar: {conditions['conditions_met']}/{conditions['total_conditions']}")
            else:
                print(f"  ❌ Trend tespit edilmedi")
        
        # Rapor oluştur
        print("\n" + "=" * 60)
        print("🎯 DÜZELTİLMİŞ TREND TESPİT RAPORU")
        print("=" * 60)
        
        if detected_trends:
            print(f"🎉 Toplam {len(detected_trends)} trend bulundu!")
            print("\nDetaylı Rapor:")
            
            for i, trend in enumerate(detected_trends, 1):
                symbol = trend['symbol']
                confidence = trend['confidence_score']
                price = trend['current_price']
                conditions = trend['conditions']
                
                print(f"\n{i}. {symbol}")
                print(f"   💰 Fiyat: ${price:.2f}")
                print(f"   🎯 Güven: {confidence}/100")
                print(f"   📈 RSI: {conditions['rsi_value']:.1f} {'✅' if conditions['rsi_condition'] else '❌'}")
                print(f"   📊 MACD: {conditions['macd_histogram']:.4f} {'✅' if conditions['macd_condition'] else '❌'}")
                print(f"   📉 EMA Cross: {conditions['ema_trend_strength']} mum önce {'✅' if conditions['ema_cross_condition'] else '❌'}")
                print(f"   🎯 EMA Hizalama: {'✅' if conditions['ema_alignment'] else '❌'}")
                print(f"   📋 Koşullar: {conditions['conditions_met']}/{conditions['total_conditions']}")
        else:
            print("❌ Hiç trend bulunamadı.")
        
        print("\n" + "=" * 60)
        print("💡 Yarı otomatik mod: Algoritma tespit eder, siz karar verirsiniz!")
        print("Gerçek veriler için trend_finder.py kullanın.")


def main():
    """Ana fonksiyon"""
    try:
        finder = TrendFinderFixed()
        finder.run_fixed_scan()
            
    except Exception as e:
        print(f"❌ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
