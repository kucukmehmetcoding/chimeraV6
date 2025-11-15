# src/technical_analyzer/regime_detector.py
"""
REGIME DETECTION SYSTEM - Market Durumu Tespit Sistemi (v2.0)
==============================================================

Gradient-based scoring (0-100) ile piyasa rejimini tespit eder.
Binary threshold yerine sürekli skor sistemi kullanır.

Market Rejimleri:
- TRENDING (Trend Takip): Güçlü yönlü hareket
- RANGING (Aralık): Yan yönlü hareket
- VOLATILE (Volatil): Yüksek volatilite, belirsiz yön
- BREAKOUT (Kırılım): Aralıktan çıkış

Scoring Components:
1. Trend Strength (ADX14) - 0-35 puan
2. Volatility (BBW, ATR) - 0-25 puan
3. Volume Profile - 0-20 puan
4. BTC Correlation - 0-20 puan

Total Score: 0-100
- 70-100: TRENDING
- 40-70: RANGING
- 20-40: VOLATILE
- 0-20: CHOPPY (kaçınılmalı)
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from collections import deque

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Market regime detection with gradient scoring
    """
    
    def __init__(self, smoothing_window: int = 5):
        """
        Args:
            smoothing_window: Regime smoothing için kaç ölçüm saklanacak
        """
        self.smoothing_window = smoothing_window
        self.regime_history = deque(maxlen=smoothing_window)
        self.score_history = deque(maxlen=smoothing_window)
        
        # Score thresholds (gradient system)
        self.thresholds = {
            'TRENDING': 70,     # Strong directional movement
            'RANGING': 40,      # Sideways movement
            'VOLATILE': 20,     # High volatility, unclear direction
            'CHOPPY': 0         # Avoid trading
        }
        
        logger.info("📊 RegimeDetector initialized (Gradient Scoring v2.0)")
        logger.info(f"   Smoothing window: {smoothing_window}")
        logger.info(f"   Thresholds: {self.thresholds}")
    
    def detect_regime(
        self,
        df_1d: pd.DataFrame,
        df_4h: Optional[pd.DataFrame] = None,
        btc_df: Optional[pd.DataFrame] = None,
        symbol: str = "Unknown"
    ) -> Dict:
        """
        Detect market regime with gradient scoring
        
        Args:
            df_1d: Daily timeframe data with indicators
            df_4h: 4H timeframe data (optional, for volatility check)
            btc_df: BTC data for correlation analysis (optional)
            symbol: Symbol name for logging
        
        Returns:
            {
                'regime': 'TRENDING' | 'RANGING' | 'VOLATILE' | 'CHOPPY',
                'score': 75.5,
                'confidence': 0.85,
                'components': {
                    'trend_strength': 30.0,
                    'volatility': 20.0,
                    'volume_profile': 15.0,
                    'btc_correlation': 10.5
                },
                'smoothed_regime': 'TRENDING',
                'recommendation': 'USE_TREND_FOLLOWING'
            }
        """
        try:
            if df_1d is None or len(df_1d) < 50:
                logger.warning(f"{symbol}: Insufficient data for regime detection")
                return self._get_default_regime()
            
            # Component scores
            components = {}
            
            # 1. Trend Strength (ADX14) - 0-35 points
            components['trend_strength'] = self._score_trend_strength(df_1d)
            
            # 2. Volatility (BBW, ATR) - 0-25 points
            components['volatility'] = self._score_volatility(df_1d, df_4h)
            
            # 3. Volume Profile - 0-20 points
            components['volume_profile'] = self._score_volume_profile(df_1d)
            
            # 4. BTC Correlation - 0-20 points
            components['btc_correlation'] = self._score_btc_correlation(df_1d, btc_df, symbol)
            
            # Total score (0-100)
            total_score = sum(components.values())
            
            # Determine regime based on score
            regime = self._score_to_regime(total_score)
            
            # Calculate confidence (how far from threshold boundaries)
            confidence = self._calculate_confidence(total_score, regime)
            
            # Apply smoothing
            self.regime_history.append(regime)
            self.score_history.append(total_score)
            smoothed_regime = self._get_smoothed_regime()
            
            # Strategy recommendation
            recommendation = self._get_strategy_recommendation(smoothed_regime, total_score)
            
            result = {
                'regime': regime,
                'score': round(total_score, 1),
                'confidence': round(confidence, 2),
                'components': {k: round(v, 1) for k, v in components.items()},
                'smoothed_regime': smoothed_regime,
                'recommendation': recommendation
            }
            
            logger.info(f"🎯 {symbol} Regime: {smoothed_regime} (score: {total_score:.1f}, confidence: {confidence:.2f})")
            logger.debug(f"   Components: {components}")
            logger.debug(f"   Recommendation: {recommendation}")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ {symbol} regime detection error: {e}", exc_info=True)
            return self._get_default_regime()
    
    def _score_trend_strength(self, df: pd.DataFrame) -> float:
        """
        Score trend strength using ADX (0-35 points)
        
        ADX > 50: Very strong trend → 35 pts
        ADX 40-50: Strong trend → 28-35 pts
        ADX 30-40: Medium trend → 21-28 pts
        ADX 20-30: Weak trend → 14-21 pts
        ADX 10-20: Very weak → 7-14 pts
        ADX < 10: No trend → 0-7 pts
        """
        try:
            last_row = df.iloc[-1]
            adx = last_row.get('adx14', 0)
            
            if pd.isna(adx):
                return 0.0
            
            # Gradient scoring
            if adx >= 50:
                score = 35.0
            elif adx >= 40:
                score = 28 + (7 * (adx - 40) / 10)
            elif adx >= 30:
                score = 21 + (7 * (adx - 30) / 10)
            elif adx >= 20:
                score = 14 + (7 * (adx - 20) / 10)
            elif adx >= 10:
                score = 7 + (7 * (adx - 10) / 10)
            else:
                score = 7 * (adx / 10)
            
            logger.debug(f"   Trend Strength (ADX={adx:.1f}): {score:.1f}/35 pts")
            return score
        
        except Exception as e:
            logger.error(f"Trend strength scoring error: {e}")
            return 0.0
    
    def _score_volatility(self, df_1d: pd.DataFrame, df_4h: Optional[pd.DataFrame]) -> float:
        """
        Score volatility using BBW and ATR (0-25 points)
        
        Optimal volatility = medium (not too tight, not too wide)
        - Very tight (BBW < 0.01): Breakout imminent → 20 pts
        - Tight (BBW 0.01-0.02): Low volatility → 15 pts
        - Medium (BBW 0.02-0.04): Optimal → 25 pts
        - Wide (BBW 0.04-0.06): High volatility → 15 pts
        - Very wide (BBW > 0.06): Too volatile → 5 pts
        """
        try:
            last_row = df_1d.iloc[-1]
            bbw = last_row.get('bbw', 0)
            
            if pd.isna(bbw):
                # Fallback to ATR calculation
                atr = last_row.get('atr14', 0)
                close = last_row.get('close', 1)
                if not pd.isna(atr) and close > 0:
                    bbw = atr / close
                else:
                    return 0.0
            
            # Gradient scoring (optimal = medium volatility)
            if bbw < 0.01:
                # Very tight - potential breakout
                score = 20.0
            elif bbw < 0.02:
                # Tight - good for mean reversion
                score = 15.0
            elif bbw < 0.04:
                # Medium - optimal for trend trading
                score = 25.0
            elif bbw < 0.06:
                # Wide - higher risk
                score = 15.0
            else:
                # Very wide - too volatile
                score = 5.0
            
            logger.debug(f"   Volatility (BBW={bbw:.4f}): {score:.1f}/25 pts")
            return score
        
        except Exception as e:
            logger.error(f"Volatility scoring error: {e}")
            return 0.0
    
    def _score_volume_profile(self, df: pd.DataFrame) -> float:
        """
        Score volume profile (0-20 points)
        
        Analyzes volume distribution to identify accumulation/distribution
        - Increasing volume with trend: Strong → 20 pts
        - Stable volume: Medium → 12 pts
        - Decreasing volume: Weak → 5 pts
        - Very low volume: Avoid → 0 pts
        """
        try:
            if 'volume' not in df.columns:
                return 10.0  # Neutral if no volume data
            
            # Last 20 periods volume analysis
            recent_volume = df['volume'].tail(20)
            
            if len(recent_volume) < 10:
                return 10.0
            
            # Calculate volume trend (linear regression slope)
            x = np.arange(len(recent_volume))
            y = recent_volume.values
            
            # Remove NaN values
            valid_mask = ~np.isnan(y)
            if valid_mask.sum() < 5:
                return 10.0
            
            x_valid = x[valid_mask]
            y_valid = y[valid_mask]
            
            # Linear regression
            slope, _ = np.polyfit(x_valid, y_valid, 1)
            
            # Calculate average volume
            avg_volume = recent_volume.mean()
            current_volume = recent_volume.iloc[-1]
            
            # Relative volume
            rel_volume = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Scoring
            if slope > 0 and rel_volume > 1.5:
                # Increasing volume with high current volume
                score = 20.0
            elif slope > 0 and rel_volume > 1.0:
                # Moderate increasing volume
                score = 15.0
            elif abs(slope) < 0.1 and rel_volume > 0.8:
                # Stable volume
                score = 12.0
            elif rel_volume < 0.5:
                # Very low volume - avoid
                score = 0.0
            else:
                # Decreasing volume
                score = 5.0
            
            logger.debug(f"   Volume Profile (trend={slope:.2e}, rel={rel_volume:.2f}): {score:.1f}/20 pts")
            return score
        
        except Exception as e:
            logger.error(f"Volume profile scoring error: {e}")
            return 10.0  # Neutral on error
    
    def _score_btc_correlation(
        self,
        df: pd.DataFrame,
        btc_df: Optional[pd.DataFrame],
        symbol: str
    ) -> float:
        """
        Score BTC correlation (0-20 points)
        
        For altcoins:
        - High correlation (>0.8): BTC drives movement → 20 pts (follow BTC regime)
        - Medium correlation (0.5-0.8): Partial influence → 10-20 pts
        - Low correlation (<0.5): Independent movement → 5-10 pts
        - Negative correlation: Counter-trend → 0 pts
        
        For BTC:
        - Always return 15 pts (neutral)
        """
        try:
            # BTC itself gets neutral score
            if 'BTC' in symbol.upper():
                return 15.0
            
            # If no BTC data provided, return neutral
            if btc_df is None or len(btc_df) < 20:
                return 10.0
            
            # Ensure both dataframes have same length
            min_len = min(len(df), len(btc_df))
            if min_len < 20:
                return 10.0
            
            # Calculate correlation of returns
            df_recent = df.tail(min_len)
            btc_recent = btc_df.tail(min_len)
            
            # Calculate returns
            df_returns = df_recent['close'].pct_change().dropna()
            btc_returns = btc_recent['close'].pct_change().dropna()
            
            # Align lengths
            min_len_returns = min(len(df_returns), len(btc_returns))
            if min_len_returns < 10:
                return 10.0
            
            df_returns = df_returns.tail(min_len_returns)
            btc_returns = btc_returns.tail(min_len_returns)
            
            # Calculate correlation
            correlation = df_returns.corr(btc_returns)
            
            if pd.isna(correlation):
                return 10.0
            
            # Scoring based on correlation strength
            if correlation > 0.8:
                score = 20.0
            elif correlation > 0.6:
                score = 10 + (10 * (correlation - 0.6) / 0.2)
            elif correlation > 0.4:
                score = 5 + (5 * (correlation - 0.4) / 0.2)
            elif correlation > 0.0:
                score = 5 * (correlation / 0.4)
            else:
                # Negative correlation
                score = 0.0
            
            logger.debug(f"   BTC Correlation ({symbol}): {correlation:.2f} → {score:.1f}/20 pts")
            return score
        
        except Exception as e:
            logger.error(f"BTC correlation scoring error: {e}")
            return 10.0  # Neutral on error
    
    def _score_to_regime(self, score: float) -> str:
        """Convert score to regime name"""
        if score >= self.thresholds['TRENDING']:
            return 'TRENDING'
        elif score >= self.thresholds['RANGING']:
            return 'RANGING'
        elif score >= self.thresholds['VOLATILE']:
            return 'VOLATILE'
        else:
            return 'CHOPPY'
    
    def _calculate_confidence(self, score: float, regime: str) -> float:
        """
        Calculate confidence based on distance from threshold boundaries
        
        Confidence = 1.0 when far from boundaries, 0.5 when near boundaries
        """
        try:
            # Get regime boundaries
            if regime == 'TRENDING':
                lower_bound = self.thresholds['TRENDING']
                upper_bound = 100
            elif regime == 'RANGING':
                lower_bound = self.thresholds['RANGING']
                upper_bound = self.thresholds['TRENDING']
            elif regime == 'VOLATILE':
                lower_bound = self.thresholds['VOLATILE']
                upper_bound = self.thresholds['RANGING']
            else:  # CHOPPY
                lower_bound = 0
                upper_bound = self.thresholds['VOLATILE']
            
            # Calculate distance from nearest boundary
            mid_point = (lower_bound + upper_bound) / 2
            range_size = upper_bound - lower_bound
            
            if range_size == 0:
                return 1.0
            
            # Distance from center (normalized)
            distance_from_center = abs(score - mid_point)
            max_distance = range_size / 2
            
            # Confidence: higher when further from boundaries
            confidence = 1.0 - (distance_from_center / max_distance) * 0.5
            
            return max(0.5, min(1.0, confidence))
        
        except Exception as e:
            logger.error(f"Confidence calculation error: {e}")
            return 0.7  # Default medium confidence
    
    def _get_smoothed_regime(self) -> str:
        """
        Get smoothed regime using majority vote from history
        
        Prevents rapid regime flipping
        """
        if len(self.regime_history) == 0:
            return 'RANGING'  # Default
        
        # Count occurrences
        from collections import Counter
        counts = Counter(self.regime_history)
        
        # Return most common regime
        smoothed = counts.most_common(1)[0][0]
        
        return smoothed
    
    def _get_strategy_recommendation(self, regime: str, score: float) -> str:
        """
        Recommend trading strategy based on regime
        """
        recommendations = {
            'TRENDING': 'USE_TREND_FOLLOWING',
            'RANGING': 'USE_RANGE_TRADING',
            'VOLATILE': 'USE_BREAKOUT_STRATEGY',
            'CHOPPY': 'AVOID_TRADING'
        }
        
        recommendation = recommendations.get(regime, 'USE_TREND_FOLLOWING')
        
        # Add confidence modifier
        if score < self.thresholds['TRENDING'] + 5:
            # Near boundary - be cautious
            recommendation += '_WITH_CAUTION'
        
        return recommendation
    
    def _get_default_regime(self) -> Dict:
        """Return default regime when detection fails"""
        return {
            'regime': 'RANGING',
            'score': 50.0,
            'confidence': 0.5,
            'components': {
                'trend_strength': 12.5,
                'volatility': 12.5,
                'volume_profile': 12.5,
                'btc_correlation': 12.5
            },
            'smoothed_regime': 'RANGING',
            'recommendation': 'USE_RANGE_TRADING_WITH_CAUTION'
        }
    
    def reset_history(self):
        """Reset smoothing history (e.g., when changing timeframe)"""
        self.regime_history.clear()
        self.score_history.clear()
        logger.info("Regime history reset")


# Global instance (singleton pattern)
_regime_detector_instance = None


def get_regime_detector(smoothing_window: int = 5) -> RegimeDetector:
    """
    Get or create RegimeDetector singleton instance
    
    Args:
        smoothing_window: History window for smoothing
    
    Returns:
        RegimeDetector instance
    """
    global _regime_detector_instance
    
    if _regime_detector_instance is None:
        _regime_detector_instance = RegimeDetector(smoothing_window)
    
    return _regime_detector_instance
