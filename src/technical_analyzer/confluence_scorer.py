# src/technical_analyzer/confluence_scorer.py
"""
v11.3: CONFLUENCE SCORING SYSTEM
=================================

Multi-timeframe sinyalleri birleştirip 0-10 arası kalite skoru hesaplar.
Win rate artırmak için minimum threshold (7.0) uygular.

Scoring Formula:
    Total Score = (HTF_Score * 0.6) + (LTF_Score * 0.4) + Sentiment_Bonus

HTF Score (1H - Max 6 points):
    - EMA Alignment (5>20>50): +2 pts
    - ADX > 25 (strong trend): +2 pts
    - RSI extremes (<30 or >70): +1 pt
    - MACD histogram aligned: +1 pt

LTF Score (15M - Max 5 points):
    - EMA crossover present: +2 pts
    - Volume spike (>1.5x avg): +2 pts
    - BB squeeze breakout: +1 pt

Sentiment Bonus (0-3 points):
    - Quality A: +3 pts
    - Quality B: +2 pts
    - Quality C: +1 pt
    - Quality D: 0 pts

Threshold: MIN_CONFLUENCE_SCORE = 7.0/10
"""

import logging
import pandas as pd
from typing import Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class ConfluenceScorer:
    """
    Multi-timeframe confluence scoring engine
    """
    
    def __init__(self, config):
        self.config = config
        
        # Weights for final score calculation
        self.htf_weight = 0.6  # 1H influence
        self.ltf_weight = 0.4  # 15M influence
        
        # Quality grade to sentiment bonus mapping
        self.sentiment_bonus = {
            'A': 3.0,
            'B': 2.0,
            'C': 1.0,
            'D': 0.0
        }
        
        # Minimum score threshold (configurable)
        self.min_score = getattr(config, 'MIN_CONFLUENCE_SCORE', 5.0)
        
        logger.info(f"📊 ConfluenceScorer initialized")
        logger.info(f"   HTF weight: {self.htf_weight}, LTF weight: {self.ltf_weight}")
        logger.info(f"   Minimum score threshold: {self.min_score}/10")
    
    def calculate_htf_score(
        self,
        df_1h: pd.DataFrame,
        signal_direction: str
    ) -> Dict:
        """
        HTF (1H) scoring - Max 6 points
        
        Args:
            df_1h: 1H OHLCV dataframe with indicators
            signal_direction: 'LONG' or 'SHORT'
        
        Returns:
            {
                'total': 5.0,
                'ema_alignment': 2.0,
                'adx_strength': 2.0,
                'rsi_extreme': 1.0,
                'macd_histogram': 0.0
            }
        """
        if df_1h is None or len(df_1h) < 2:
            return {'total': 0.0, 'details': 'insufficient_data'}
        
        last_row = df_1h.iloc[-1]
        score_components = {}
        
        # 1. EMA Alignment (2 points)
        ema5 = last_row.get('ema5', 0)
        ema20 = last_row.get('ema20', 0)
        ema50 = last_row.get('ema50', 0)
        
        # NaN/None check
        if pd.isna(ema5) or pd.isna(ema20) or pd.isna(ema50):
            return {'total': 0.0, 'details': 'missing_ema_data'}
        
        if signal_direction == 'LONG':
            # LONG: EMA5 > EMA20 > EMA50
            if ema5 > ema20 > ema50:
                score_components['ema_alignment'] = 2.0
            elif ema5 > ema20:
                score_components['ema_alignment'] = 1.0
            else:
                score_components['ema_alignment'] = 0.0
        else:  # SHORT
            # SHORT: EMA5 < EMA20 < EMA50
            if ema5 < ema20 < ema50:
                score_components['ema_alignment'] = 2.0
            elif ema5 < ema20:
                score_components['ema_alignment'] = 1.0
            else:
                score_components['ema_alignment'] = 0.0
        
        # 2. ADX Strength (2 points)
        adx = last_row.get('adx14', 0)
        if pd.isna(adx):
            adx = 0
        if adx >= 30:
            score_components['adx_strength'] = 2.0
        elif adx >= 25:
            score_components['adx_strength'] = 1.5
        elif adx >= 20:
            score_components['adx_strength'] = 1.0
        else:
            score_components['adx_strength'] = 0.0
        
        # 3. RSI Extremes (1 point)
        rsi = last_row.get('rsi14', 50)
        if pd.isna(rsi):
            rsi = 50
        if signal_direction == 'LONG':
            # LONG: RSI oversold (<30) favors buy
            if rsi < 30:
                score_components['rsi_extreme'] = 1.0
            elif rsi < 40:
                score_components['rsi_extreme'] = 0.5
            else:
                score_components['rsi_extreme'] = 0.0
        else:  # SHORT
            # SHORT: RSI overbought (>70) favors sell
            if rsi > 70:
                score_components['rsi_extreme'] = 1.0
            elif rsi > 60:
                score_components['rsi_extreme'] = 0.5
            else:
                score_components['rsi_extreme'] = 0.0
        
        # 4. MACD Histogram (1 point)
        macd_hist = last_row.get('macd_hist', 0)
        if pd.isna(macd_hist):
            macd_hist = 0
        if signal_direction == 'LONG':
            # LONG: positive histogram
            if macd_hist > 0:
                score_components['macd_histogram'] = 1.0
            else:
                score_components['macd_histogram'] = 0.0
        else:  # SHORT
            # SHORT: negative histogram
            if macd_hist < 0:
                score_components['macd_histogram'] = 1.0
            else:
                score_components['macd_histogram'] = 0.0
        
        total = sum(score_components.values())
        score_components['total'] = round(total, 1)
        
        return score_components
    
    def calculate_ltf_score(
        self,
        df_15m: pd.DataFrame,
        signal_direction: str,
        volume_data: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        LTF (15M) scoring - Max 5 points
        
        Args:
            df_15m: 15M OHLCV dataframe with indicators
            signal_direction: 'LONG' or 'SHORT'
            volume_data: Optional volume analysis data
        
        Returns:
            {
                'total': 4.0,
                'ema_crossover': 2.0,
                'volume_spike': 2.0,
                'bb_squeeze': 0.0
            }
        """
        if df_15m is None or len(df_15m) < 3:
            return {'total': 0.0, 'details': 'insufficient_data'}
        
        last_row = df_15m.iloc[-1]
        prev_row = df_15m.iloc[-2]
        score_components = {}
        
        # 1. EMA Crossover (2 points)
        ema5_curr = last_row.get('ema5', 0)
        ema20_curr = last_row.get('ema20', 0)
        ema5_prev = prev_row.get('ema5', 0)
        ema20_prev = prev_row.get('ema20', 0)
        
        # NaN/None check
        if any(pd.isna(x) for x in [ema5_curr, ema20_curr, ema5_prev, ema20_prev]):
            return {'total': 0.0, 'details': 'missing_ema_data'}
        
        if signal_direction == 'LONG':
            # LONG: bullish crossover (EMA5 crosses above EMA20)
            if ema5_curr > ema20_curr and ema5_prev <= ema20_prev:
                score_components['ema_crossover'] = 2.0
            elif ema5_curr > ema20_curr:
                score_components['ema_crossover'] = 1.0
            else:
                score_components['ema_crossover'] = 0.0
        else:  # SHORT
            # SHORT: bearish crossover (EMA5 crosses below EMA20)
            if ema5_curr < ema20_curr and ema5_prev >= ema20_prev:
                score_components['ema_crossover'] = 2.0
            elif ema5_curr < ema20_curr:
                score_components['ema_crossover'] = 1.0
            else:
                score_components['ema_crossover'] = 0.0
        
        # 2. Volume Spike (2 points)
        if 'volume' in df_15m.columns:
            volume_avg = df_15m['volume'].rolling(window=20).mean().iloc[-1]
            current_volume = last_row.get('volume', 0)
            
            if current_volume > volume_avg * 2.0:
                score_components['volume_spike'] = 2.0
            elif current_volume > volume_avg * 1.5:
                score_components['volume_spike'] = 1.5
            elif current_volume > volume_avg * 1.2:
                score_components['volume_spike'] = 1.0
            else:
                score_components['volume_spike'] = 0.0
        else:
            score_components['volume_spike'] = 0.0
        
        # 3. BB Squeeze Breakout (1 point)
        bb_upper = last_row.get('bb_upper', 0)
        bb_lower = last_row.get('bb_lower', 0)
        close = last_row.get('close', 0)
        
        if bb_upper > 0 and bb_lower > 0:
            bb_width = (bb_upper - bb_lower) / close if close > 0 else 0
            
            # Check for squeeze (narrow bands) followed by breakout
            if bb_width < 0.02:  # Tight squeeze (<2%)
                if signal_direction == 'LONG' and close > bb_upper:
                    score_components['bb_squeeze'] = 1.0
                elif signal_direction == 'SHORT' and close < bb_lower:
                    score_components['bb_squeeze'] = 1.0
                else:
                    score_components['bb_squeeze'] = 0.5  # Squeeze present but no breakout yet
            else:
                score_components['bb_squeeze'] = 0.0
        else:
            score_components['bb_squeeze'] = 0.0
        
        total = sum(score_components.values())
        score_components['total'] = round(total, 1)
        
        return score_components
    
    def calculate_confluence_score(
        self,
        htf_score_data: Dict,
        ltf_score_data: Dict,
        quality_grade: str
    ) -> Dict:
        """
        Final confluence score hesapla
        
        Args:
            htf_score_data: calculate_htf_score() output
            ltf_score_data: calculate_ltf_score() output
            quality_grade: 'A', 'B', 'C', or 'D'
        
        Returns:
            {
                'total_score': 8.5,
                'htf_score': 5.0,
                'ltf_score': 4.0,
                'sentiment_bonus': 3.0,
                'weighted_score': 8.5,
                'passed_threshold': True,
                'recommendation': 'STRONG_SIGNAL'
            }
        """
        htf_total = htf_score_data.get('total', 0)
        ltf_total = ltf_score_data.get('total', 0)
        sentiment = self.sentiment_bonus.get(quality_grade, 0)
        
        # Weighted calculation
        weighted = (htf_total * self.htf_weight) + (ltf_total * self.ltf_weight) + sentiment
        
        # Normalize to 0-10 scale
        # Max possible: (6 * 0.6) + (5 * 0.4) + 3 = 3.6 + 2.0 + 3.0 = 8.6
        # We'll keep this as is, max score ~8.6
        final_score = round(weighted, 1)
        
        passed = final_score >= self.min_score
        
        # Recommendation based on score
        if final_score >= 8.0:
            recommendation = 'STRONG_SIGNAL'
        elif final_score >= 7.0:
            recommendation = 'GOOD_SIGNAL'
        elif final_score >= 5.0:
            recommendation = 'MODERATE_SIGNAL'
        else:
            recommendation = 'WEAK_SIGNAL'
        
        result = {
            'total_score': final_score,
            'htf_score': round(htf_total, 1),
            'ltf_score': round(ltf_total, 1),
            'sentiment_bonus': round(sentiment, 1),
            'weighted_score': final_score,
            'passed_threshold': passed,
            'min_threshold': self.min_score,
            'recommendation': recommendation,
            'htf_details': htf_score_data,
            'ltf_details': ltf_score_data
        }
        
        logger.info(f"📊 Confluence Score: {final_score}/10 (HTF: {htf_total}, LTF: {ltf_total}, Sentiment: {sentiment})")
        logger.info(f"   Threshold: {self.min_score} → {'✅ PASSED' if passed else '❌ REJECTED'}")
        
        return result


# Singleton instance
_confluence_scorer_instance: Optional[ConfluenceScorer] = None


def get_confluence_scorer(config):
    """Get or create ConfluenceScorer singleton"""
    global _confluence_scorer_instance
    
    if _confluence_scorer_instance is None:
        _confluence_scorer_instance = ConfluenceScorer(config)
    
    return _confluence_scorer_instance


def reset_confluence_scorer():
    """Reset singleton (for testing)"""
    global _confluence_scorer_instance
    _confluence_scorer_instance = None
