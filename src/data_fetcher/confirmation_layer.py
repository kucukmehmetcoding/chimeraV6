# src/data_fetcher/confirmation_layer.py
"""
v10.6: 1H CONFIRMATION LAYER - Phase 3
========================================

Bu modül, 15m timeframe'de tespit edilen EMA crossover sinyallerini
1H timeframe'de doğrular ve 0-100 arası güvenilirlik skoru hesaplar.

Scoring Algorithm (100 points total):
- Trend Alignment (30 pts): 1H'de EMA5 vs EMA20 pozisyonu
- Strength (25 pts): ADX14 değeri (trend gücü)
- Momentum (25 pts): MACD histogram (momentum yönü)
- RSI (20 pts): RSI14 değeri (aşırı alım/satım kontrolü)

Score Interpretation:
- 70-100: HIGH confidence → Market order (hızlı giriş)
- 50-69:  MEDIUM confidence → Partial fill (50% market + 50% limit)
- 0-49:   LOW confidence → Limit order only (agresif fiyat bekleme)
"""

import logging
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfirmationLayer:
    """
    1H timeframe'de multi-indicator analiz ve skorlama
    
    İş Akışı:
    1. 15m'de crossover tespit edildi
    2. ConfirmationLayer.analyze() çağrılır
    3. 1H data çekilir (son 50 mum)
    4. Indikatörler hesaplanır
    5. Signal direction ile uyum kontrol edilir
    6. 0-100 skor hesaplanır
    7. Execution strategy belirlenir
    """
    
    def __init__(self, config):
        self.config = config
        
        # Scoring weights (total = 100)
        self.weights = {
            'trend': 30,      # EMA5 vs EMA20 alignment
            'strength': 25,   # ADX14 strength
            'momentum': 25,   # MACD histogram
            'rsi': 20         # RSI14 overbought/oversold
        }
        
        # Thresholds
        self.adx_strong_threshold = 25  # ADX > 25 = güçlü trend
        self.adx_weak_threshold = 15    # ADX < 15 = zayıf trend
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
        logger.info("📊 ConfirmationLayer initialized")
        logger.info(f"   Weights: Trend={self.weights['trend']}, "
                   f"Strength={self.weights['strength']}, "
                   f"Momentum={self.weights['momentum']}, "
                   f"RSI={self.weights['rsi']}")
    
    def analyze(
        self,
        symbol: str,
        signal_direction: str,  # 'bullish' or 'bearish'
        timeframe: str = '1h'
    ) -> Dict:
        """
        1H timeframe'de confirmation analizi yap
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            signal_direction: '15m'de tespit edilen crossover yönü
            timeframe: Confirmation timeframe (default: '1h')
        
        Returns:
            {
                'symbol': 'BTCUSDT',
                'signal_direction': 'bullish',
                'score': 75,  # 0-100
                'execution_strategy': 'market',  # 'market', 'partial', 'limit'
                'components': {
                    'trend_score': 30,
                    'strength_score': 20,
                    'momentum_score': 15,
                    'rsi_score': 10
                },
                'indicators': {
                    'ema5': 103500.0,
                    'ema20': 103200.0,
                    'adx14': 28.5,
                    'macd_hist': 15.3,
                    'rsi14': 58.2
                },
                'recommendation': 'STRONG BUY'
            }
        """
        try:
            logger.info(f"🔍 Analyzing {symbol} on {timeframe} for {signal_direction} signal")
            
            # Fetch 1H data
            df = self._fetch_timeframe_data(symbol, timeframe, limit=50)
            
            if df is None or len(df) < 30:
                logger.warning(f"⚠️ Insufficient data for {symbol} on {timeframe}")
                return self._get_default_result(symbol, signal_direction, 0)
            
            # Calculate indicators
            indicators = self._calculate_indicators(df)
            
            if not self._validate_indicators(indicators):
                logger.warning(f"⚠️ Invalid indicators for {symbol}")
                return self._get_default_result(symbol, signal_direction, 0)
            
            # Calculate component scores
            trend_score = self._score_trend(indicators, signal_direction)
            strength_score = self._score_strength(indicators)
            momentum_score = self._score_momentum(indicators, signal_direction)
            rsi_score = self._score_rsi(indicators, signal_direction)
            
            # Total score
            total_score = trend_score + strength_score + momentum_score + rsi_score
            
            # Determine execution strategy
            execution_strategy = self._determine_execution_strategy(total_score)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(total_score, signal_direction)
            
            result = {
                'symbol': symbol,
                'signal_direction': signal_direction,
                'timeframe': timeframe,
                'score': round(total_score, 1),
                'execution_strategy': execution_strategy,
                'components': {
                    'trend_score': round(trend_score, 1),
                    'strength_score': round(strength_score, 1),
                    'momentum_score': round(momentum_score, 1),
                    'rsi_score': round(rsi_score, 1)
                },
                'indicators': {
                    'ema5': round(indicators['ema5'], 2),
                    'ema20': round(indicators['ema20'], 2),
                    'adx14': round(indicators['adx14'], 2),
                    'macd_hist': round(indicators['macd_hist'], 4),
                    'rsi14': round(indicators['rsi14'], 2)
                },
                'recommendation': recommendation,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Confirmation analysis complete:")
            logger.info(f"   Score: {result['score']}/100")
            logger.info(f"   Strategy: {execution_strategy}")
            logger.info(f"   Recommendation: {recommendation}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error analyzing {symbol}: {e}", exc_info=True)
            return self._get_default_result(symbol, signal_direction, 0)
    
    def _fetch_timeframe_data(self, symbol: str, timeframe: str, limit: int = 50) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for given timeframe"""
        try:
            # Import fetch function
            from src.data_fetcher.binance_fetcher import get_binance_klines
            
            df = get_binance_klines(symbol, timeframe, limit=limit)
            
            if df is None or df.empty:
                logger.warning(f"⚠️ No data fetched for {symbol} {timeframe}")
                return None
            
            logger.debug(f"📊 Fetched {len(df)} candles for {symbol} {timeframe}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching {symbol} {timeframe}: {e}")
            return None
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate all required indicators"""
        try:
            from src.technical_analyzer.indicators import calculate_indicators
            
            # Calculate all indicators at once
            df = calculate_indicators(df)
            
            # Check if we have enough data
            if df.empty or len(df) < 2:
                logger.warning("⚠️ Insufficient data after indicator calculation")
                return {}
            
            # Get last values
            last_row = df.iloc[-1]
            
            # Check for required indicators
            required = ['ema5', 'ema20', 'adx14', 'macd_hist', 'rsi14']
            missing = [col for col in required if col not in last_row or pd.isna(last_row[col])]
            
            if missing:
                logger.warning(f"⚠️ Missing or NaN indicators: {missing}")
                return {}
            
            indicators = {
                'ema5': last_row['ema5'],
                'ema20': last_row['ema20'],
                'adx14': last_row['adx14'],
                'macd_hist': last_row['macd_hist'],
                'rsi14': last_row['rsi14']
            }
            
            return indicators
            
        except Exception as e:
            logger.error(f"❌ Error calculating indicators: {e}", exc_info=True)
            return {}
    
    def _validate_indicators(self, indicators: Dict) -> bool:
        """Validate that all indicators are present and valid"""
        required = ['ema5', 'ema20', 'adx14', 'macd_hist', 'rsi14']
        
        for key in required:
            if key not in indicators:
                logger.warning(f"⚠️ Missing indicator: {key}")
                return False
            
            value = indicators[key]
            if value is None or pd.isna(value):
                logger.warning(f"⚠️ Invalid indicator value for {key}: {value}")
                return False
        
        return True
    
    def _score_trend(self, indicators: Dict, signal_direction: str) -> float:
        """
        Score trend alignment (30 points max)
        
        LONG signal (bullish):
        - EMA5 > EMA20: Full points (30)
        - EMA5 < EMA20: Zero points (0)
        
        SHORT signal (bearish):
        - EMA5 < EMA20: Full points (30)
        - EMA5 > EMA20: Zero points (0)
        """
        max_points = self.weights['trend']
        
        ema5 = indicators['ema5']
        ema20 = indicators['ema20']
        
        if signal_direction == 'bullish':
            # LONG signal - want EMA5 > EMA20
            if ema5 > ema20:
                score = max_points
                logger.debug(f"   ✅ Trend aligned for LONG (EMA5 > EMA20): {score} pts")
            else:
                score = 0
                logger.debug(f"   ❌ Trend NOT aligned for LONG (EMA5 < EMA20): {score} pts")
        
        else:  # bearish
            # SHORT signal - want EMA5 < EMA20
            if ema5 < ema20:
                score = max_points
                logger.debug(f"   ✅ Trend aligned for SHORT (EMA5 < EMA20): {score} pts")
            else:
                score = 0
                logger.debug(f"   ❌ Trend NOT aligned for SHORT (EMA5 > EMA20): {score} pts")
        
        return score
    
    def _score_strength(self, indicators: Dict) -> float:
        """
        Score trend strength via ADX (25 points max) - V12.0 SMOOTH TRANSITIONS
        
        Uses sigmoid curve instead of binary thresholds for smooth scoring
        
        ADX transition curve:
        - < 10: Very weak (0-5 pts)
        - 10-20: Weak to medium (5-15 pts) - SMOOTH
        - 20-30: Medium to strong (15-22 pts) - SMOOTH
        - > 30: Very strong (22-25 pts)
        """
        max_points = self.weights['strength']
        adx = indicators['adx14']
        
        # V12.0: Sigmoid-based smooth scoring
        import math
        
        if adx >= 30:
            # Very strong trend - full points
            score = max_points
        elif adx >= 20:
            # Strong trend zone - smooth transition
            # Sigmoid curve from 15 to 22 points
            ratio = (adx - 20) / 10  # 0 to 1 over 20-30 range
            score = 15 + (7 * self._sigmoid(ratio * 4 - 2))  # Smooth 15-22
        elif adx >= 10:
            # Medium trend zone - smooth transition  
            # Sigmoid curve from 5 to 15 points
            ratio = (adx - 10) / 10  # 0 to 1 over 10-20 range
            score = 5 + (10 * self._sigmoid(ratio * 4 - 2))  # Smooth 5-15
        else:
            # Weak trend - minimal points
            ratio = adx / 10  # 0 to 1 over 0-10 range
            score = 5 * ratio  # Linear 0-5
        
        logger.debug(f"   {'✅' if score > 15 else '⚠️' if score > 8 else '❌'} Trend strength (ADX={adx:.1f}): {score:.1f} pts")
        
        return score
    
    def _sigmoid(self, x: float) -> float:
        """
        Sigmoid activation function for smooth transitions
        
        Returns value between 0 and 1
        """
        import math
        return 1 / (1 + math.exp(-x))
    
    def _score_momentum(self, indicators: Dict, signal_direction: str) -> float:
        """
        Score momentum via MACD histogram (25 points max)
        
        LONG signal:
        - MACD hist > 0 (bullish momentum): Full points
        - MACD hist < 0 (bearish momentum): Zero points
        
        SHORT signal:
        - MACD hist < 0 (bearish momentum): Full points
        - MACD hist > 0 (bullish momentum): Zero points
        
        Scale based on histogram magnitude
        """
        max_points = self.weights['momentum']
        macd_hist = indicators['macd_hist']
        
        if signal_direction == 'bullish':
            if macd_hist > 0:
                # Positive momentum for LONG
                # Scale: larger positive = more points
                # Use tanh to normalize (0.01 hist = ~63% points, 0.05 hist = ~99% points)
                import math
                ratio = math.tanh(abs(macd_hist) * 100)
                score = max_points * ratio
                logger.debug(f"   ✅ Bullish momentum (MACD_hist={macd_hist:.4f}): {score:.1f} pts")
            else:
                score = 0
                logger.debug(f"   ❌ Bearish momentum for LONG (MACD_hist={macd_hist:.4f}): {score} pts")
        
        else:  # bearish
            if macd_hist < 0:
                # Negative momentum for SHORT
                import math
                ratio = math.tanh(abs(macd_hist) * 100)
                score = max_points * ratio
                logger.debug(f"   ✅ Bearish momentum (MACD_hist={macd_hist:.4f}): {score:.1f} pts")
            else:
                score = 0
                logger.debug(f"   ❌ Bullish momentum for SHORT (MACD_hist={macd_hist:.4f}): {score} pts")
        
        return score
    
    def _score_rsi(self, indicators: Dict, signal_direction: str) -> float:
        """
        Score RSI positioning (20 points max)
        
        LONG signal:
        - RSI < 30 (oversold): Full points (20) - great buy opportunity
        - RSI 30-50: Good (10-20 points)
        - RSI 50-70: Neutral (5-10 points)
        - RSI > 70 (overbought): Low points (0-5)
        
        SHORT signal:
        - RSI > 70 (overbought): Full points (20) - great sell opportunity
        - RSI 50-70: Good (10-20 points)
        - RSI 30-50: Neutral (5-10 points)
        - RSI < 30 (oversold): Low points (0-5)
        """
        max_points = self.weights['rsi']
        rsi = indicators['rsi14']
        
        if signal_direction == 'bullish':
            # LONG signal - prefer low RSI (oversold)
            if rsi < self.rsi_oversold:
                # Oversold - excellent for LONG
                score = max_points
                logger.debug(f"   ✅ RSI oversold for LONG (RSI={rsi:.1f}): {score} pts")
            
            elif rsi < 50:
                # Good zone (30-50)
                ratio = (50 - rsi) / (50 - self.rsi_oversold)
                score = max_points * 0.5 + (max_points * 0.5 * ratio)  # 10-20 points
                logger.debug(f"   ✅ RSI good for LONG (RSI={rsi:.1f}): {score:.1f} pts")
            
            elif rsi < self.rsi_overbought:
                # Neutral zone (50-70)
                ratio = (self.rsi_overbought - rsi) / (self.rsi_overbought - 50)
                score = max_points * 0.25 + (max_points * 0.25 * ratio)  # 5-10 points
                logger.debug(f"   ⚠️ RSI neutral for LONG (RSI={rsi:.1f}): {score:.1f} pts")
            
            else:
                # Overbought - risky for LONG
                ratio = max(0, (100 - rsi) / (100 - self.rsi_overbought))
                score = max_points * 0.25 * ratio  # 0-5 points
                logger.debug(f"   ❌ RSI overbought for LONG (RSI={rsi:.1f}): {score:.1f} pts")
        
        else:  # bearish
            # SHORT signal - prefer high RSI (overbought)
            if rsi > self.rsi_overbought:
                # Overbought - excellent for SHORT
                score = max_points
                logger.debug(f"   ✅ RSI overbought for SHORT (RSI={rsi:.1f}): {score} pts")
            
            elif rsi > 50:
                # Good zone (50-70)
                ratio = (rsi - 50) / (self.rsi_overbought - 50)
                score = max_points * 0.5 + (max_points * 0.5 * ratio)  # 10-20 points
                logger.debug(f"   ✅ RSI good for SHORT (RSI={rsi:.1f}): {score:.1f} pts")
            
            elif rsi > self.rsi_oversold:
                # Neutral zone (30-50)
                ratio = (rsi - self.rsi_oversold) / (50 - self.rsi_oversold)
                score = max_points * 0.25 + (max_points * 0.25 * ratio)  # 5-10 points
                logger.debug(f"   ⚠️ RSI neutral for SHORT (RSI={rsi:.1f}): {score:.1f} pts")
            
            else:
                # Oversold - risky for SHORT
                ratio = max(0, rsi / self.rsi_oversold)
                score = max_points * 0.25 * ratio  # 0-5 points
                logger.debug(f"   ❌ RSI oversold for SHORT (RSI={rsi:.1f}): {score:.1f} pts")
        
        return score
    
    def _determine_execution_strategy(self, score: float) -> str:
        """
        Determine execution strategy based on score
        
        70-100: HIGH confidence → 'market' (fast entry)
        50-69:  MEDIUM confidence → 'partial' (50% market + 50% limit)
        0-49:   LOW confidence → 'limit' (wait for better price)
        """
        if score >= 70:
            return 'market'
        elif score >= 50:
            return 'partial'
        else:
            return 'limit'
    
    def _generate_recommendation(self, score: float, signal_direction: str) -> str:
        """Generate human-readable recommendation"""
        if score >= 70:
            strength = "STRONG"
        elif score >= 50:
            strength = "MODERATE"
        else:
            strength = "WEAK"
        
        action = "BUY" if signal_direction == 'bullish' else "SELL"
        
        return f"{strength} {action}"
    
    def _get_default_result(self, symbol: str, signal_direction: str, score: float) -> Dict:
        """Return default result structure with minimal data"""
        return {
            'symbol': symbol,
            'signal_direction': signal_direction,
            'timeframe': '1h',
            'score': score,
            'execution_strategy': 'limit',  # Safe default
            'components': {
                'trend_score': 0,
                'strength_score': 0,
                'momentum_score': 0,
                'rsi_score': 0
            },
            'indicators': {},
            'recommendation': 'NO TRADE',
            'timestamp': datetime.now().isoformat()
        }


# Module-level singleton
_confirmation_layer_instance: Optional[ConfirmationLayer] = None


def get_confirmation_layer(config) -> ConfirmationLayer:
    """Get or create ConfirmationLayer instance (singleton)"""
    global _confirmation_layer_instance
    
    if _confirmation_layer_instance is None:
        _confirmation_layer_instance = ConfirmationLayer(config)
    
    return _confirmation_layer_instance


def reset_confirmation_layer():
    """Reset singleton instance (for testing)"""
    global _confirmation_layer_instance
    _confirmation_layer_instance = None
