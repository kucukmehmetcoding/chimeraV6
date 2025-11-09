"""
Dinamik risk hesaplama modülü - piyasa koşullarına göre risk ayarlar
"""
import logging
from typing import Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class DynamicRiskCalculator:
    """
    Çoklu faktöre dayalı dinamik risk hesaplayıcı
    """
    
    def __init__(self, config):
        self.config = config
        self.base_risk = config.POSITION_RISK_PERCENT  # Varsayılan: 2.0
        self.max_risk = config.get('MAX_POSITION_RISK', 4.0)  # Maksimum: 4.0
        self.min_risk = config.get('MIN_POSITION_RISK', 0.5)  # Minimum: 0.5
    
    def calculate_adjusted_risk(
        self,
        signal_quality: str,
        rr_ratio: float,
        volatility_score: float,
        sentiment_alignment: float,
        correlation_group_exposure: float
    ) -> Dict[str, float]:
        """
        Çoklu faktör bazlı risk hesaplama
        
        Args:
            signal_quality: 'A', 'B', 'C', 'D' kalite notu
            rr_ratio: Risk/Reward oranı
            volatility_score: ATR bazlı volatilite skoru (0-1)
            sentiment_alignment: Sinyal-sentiment uyum skoru (-1 ile 1)
            correlation_group_exposure: Grup içindeki mevcut risk yüzdesi
            
        Returns:
            {
                'risk_percent': float,  # Kullanılacak risk yüzdesi
                'multipliers': dict,    # Her faktörün çarpanı
                'reasoning': str        # Açıklama
            }
        """
        multipliers = {}
        reasoning_parts = []
        
        # 1. Kalite Çarpanı (güçlendirilmiş)
        quality_mult = {
            'A': 1.5,   # A sinyallere %50 daha fazla risk
            'B': 1.0,   # Standart
            'C': 0.6,   # C sinyallere %40 azaltılmış risk
            'D': 0.0    # D hiç açılmaz
        }.get(signal_quality, 0.0)
        multipliers['quality'] = quality_mult
        reasoning_parts.append(f"Kalite {signal_quality}: x{quality_mult:.2f}")
        
        # 2. RR Oranı Çarpanı (YENİ - yüksek RR ödüllendirilir)
        if rr_ratio >= 3.0:
            rr_mult = 1.3
            reasoning_parts.append(f"Yüksek RR ({rr_ratio:.1f}): x1.3")
        elif rr_ratio >= 2.0:
            rr_mult = 1.15
            reasoning_parts.append(f"İyi RR ({rr_ratio:.1f}): x1.15")
        elif rr_ratio >= 1.5:
            rr_mult = 1.0
            reasoning_parts.append(f"Normal RR ({rr_ratio:.1f}): x1.0")
        else:
            rr_mult = 0.85
            reasoning_parts.append(f"Düşük RR ({rr_ratio:.1f}): x0.85")
        multipliers['rr_ratio'] = rr_mult
        
        # 3. Volatilite Çarpanı (YENİ - düşük volatilite = daha fazla risk)
        if volatility_score < 0.3:  # Düşük volatilite
            vol_mult = 1.2
            reasoning_parts.append("Düşük volatilite: x1.2")
        elif volatility_score < 0.6:  # Orta volatilite
            vol_mult = 1.0
            reasoning_parts.append("Orta volatilite: x1.0")
        else:  # Yüksek volatilite
            vol_mult = 0.75
            reasoning_parts.append("Yüksek volatilite: x0.75")
        multipliers['volatility'] = vol_mult
        
        # 4. Sentiment Uyum Çarpanı (YENİ)
        if sentiment_alignment > 0.5:  # Güçlü uyum
            sent_mult = 1.2
            reasoning_parts.append(f"Güçlü sentiment uyumu ({sentiment_alignment:.2f}): x1.2")
        elif sentiment_alignment > 0.0:  # Zayıf uyum
            sent_mult = 1.0
            reasoning_parts.append(f"Orta sentiment uyumu ({sentiment_alignment:.2f}): x1.0")
        else:  # Ters sentiment
            sent_mult = 0.7
            reasoning_parts.append(f"Zayıf sentiment uyumu ({sentiment_alignment:.2f}): x0.7")
        multipliers['sentiment'] = sent_mult
        
        # 5. Korelasyon Grubu Doluluk Çarpanı (YENİ - diversifikasyon ödülü)
        max_group_risk = self.config.MAX_RISK_PER_GROUP  # Varsayılan: 5.0
        group_usage = correlation_group_exposure / max_group_risk if max_group_risk > 0 else 0
        
        if group_usage < 0.3:  # Grup boş, agresif olabilir
            group_mult = 1.1
            reasoning_parts.append(f"Grup az dolu ({group_usage*100:.0f}%): x1.1")
        elif group_usage < 0.6:  # Grup orta dolu
            group_mult = 1.0
            reasoning_parts.append(f"Grup orta dolu ({group_usage*100:.0f}%): x1.0")
        else:  # Grup neredeyse dolu, dikkatli ol
            group_mult = 0.8
            reasoning_parts.append(f"Grup dolu ({group_usage*100:.0f}%): x0.8")
        multipliers['group_exposure'] = group_mult
        
        # Toplam çarpan hesaplama
        total_multiplier = (
            quality_mult * 
            rr_mult * 
            vol_mult * 
            sent_mult * 
            group_mult
        )
        
        # Risk yüzdesini hesapla ve limitle
        adjusted_risk = self.base_risk * total_multiplier
        adjusted_risk = max(self.min_risk, min(self.max_risk, adjusted_risk))
        
        reasoning = " | ".join(reasoning_parts)
        reasoning += f" → Toplam çarpan: x{total_multiplier:.2f} → Risk: {adjusted_risk:.2f}%"
        
        logger.info(f"Risk hesaplandı: {reasoning}")
        
        return {
            'risk_percent': adjusted_risk,
            'multipliers': multipliers,
            'reasoning': reasoning
        }
    
    def calculate_volatility_score(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        ATR bazlı normalized volatilite skoru (0-1 arası)
        
        Args:
            df: OHLCV dataframe (ATR14 kolonu olmalı)
            period: ATR periyodu
            
        Returns:
            0-1 arası volatilite skoru (1 = çok volatil)
        """
        if df.empty or 'atr14' not in df.columns or 'close' not in df.columns:
            return 0.5  # Varsayılan orta volatilite
        
        try:
            # ATR'yi close fiyatına normalize et
            atr_pct = (df['atr14'] / df['close']).iloc[-1]
            
            # 0-1 arası ölçekle (tipik kripto volatilite: %0.5 - %8)
            # %0.5 -> 0.0 (çok düşük)
            # %4.0 -> 0.5 (orta)
            # %8.0 -> 1.0 (çok yüksek)
            min_vol, max_vol = 0.005, 0.08
            normalized = (atr_pct - min_vol) / (max_vol - min_vol)
            
            return max(0.0, min(1.0, normalized))
            
        except Exception as e:
            logger.warning(f"Volatilite hesaplama hatası: {e}")
            return 0.5
    
    def calculate_sentiment_alignment(
        self,
        signal_direction: str,
        fear_greed_index: Optional[int],
        news_sentiment: Optional[float],
        reddit_sentiment: Optional[float]
    ) -> float:
        """
        Sinyal yönü ile sentiment uyumunu hesaplar (-1 ile 1 arası)
        
        Args:
            signal_direction: 'LONG' veya 'SHORT'
            fear_greed_index: 0-100 arası F&G değeri
            news_sentiment: -1 ile 1 arası haber sentimenti
            reddit_sentiment: -1 ile 1 arası Reddit sentimenti
            
        Returns:
            -1 (tam ters) ile 1 (tam uyumlu) arası skor
        """
        scores = []
        
        # Fear & Greed alignment
        if fear_greed_index is not None:
            if signal_direction == 'LONG':
                # LONG için düşük F&G iyi (korku = alım fırsatı)
                fg_score = (50 - fear_greed_index) / 50.0
            else:  # SHORT
                # SHORT için yüksek F&G iyi (aşırı heyecan = satış fırsatı)
                fg_score = (fear_greed_index - 50) / 50.0
            scores.append(fg_score)
        
        # News sentiment alignment
        if news_sentiment is not None:
            if signal_direction == 'LONG':
                scores.append(news_sentiment)
            else:  # SHORT
                scores.append(-news_sentiment)
        
        # Reddit sentiment alignment
        if reddit_sentiment is not None:
            if signal_direction == 'LONG':
                scores.append(reddit_sentiment)
            else:  # SHORT
                scores.append(-reddit_sentiment)
        
        if not scores:
            return 0.0  # Sentiment verisi yok, nötr
        
        # Ortalama al
        return sum(scores) / len(scores)
