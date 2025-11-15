# src/risk_manager/dynamic_position_sizer.py
"""
DYNAMIC POSITION SIZING - Kelly Criterion & Quality-Based Adjustment
=====================================================================

v12.0: Gelişmiş pozisyon boyutlandırma sistemi

Features:
- Kelly Criterion integration (optimal bet sizing)
- Quality grade-based multipliers (A/B/C/D grades)
- Win rate tracking per strategy
- Adaptive sizing based on recent performance
- Risk parity across correlation groups

Kelly Formula:
    f* = (p * b - q) / b
    
    Where:
    - f* = optimal bet fraction
    - p = win probability
    - q = loss probability (1 - p)
    - b = odds (average win / average loss)
    
Example:
    - Win rate: 60%, Avg Win: $30, Avg Loss: $15
    - b = 30/15 = 2.0
    - f* = (0.6 * 2 - 0.4) / 2 = 0.4 = 40%
    - But capped at KELLY_MAX_FRACTION (15%)
"""

import logging
import os
from typing import Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class DynamicPositionSizer:
    """
    Dinamik pozisyon boyutlandırma engine
    
    Quality-based ve Kelly Criterion ile optimal position sizing
    """
    
    def __init__(self, config):
        self.config = config
        
        # Base parameters
        self.min_margin = getattr(config, 'MIN_MARGIN_USD', 5.0)
        self.max_margin = getattr(config, 'MAX_MARGIN_USD', 5.0)
        self.leverage = getattr(config, 'FUTURES_LEVERAGE', 10)
        
        # Kelly parameters
        self.use_kelly = getattr(config, 'USE_KELLY_ADJUSTMENT', True)
        self.kelly_max_fraction = getattr(config, 'KELLY_MAX_FRACTION', 0.15)
        
        # Quality multipliers
        self.quality_multipliers = getattr(config, 'QUALITY_MARGIN_MULTIPLIERS', {
            'A': 1.5,
            'B': 1.0,
            'C': 0.6,
            'D': 0.0
        })
        
        # Performance tracking (simplified - would normally load from DB)
        self.default_win_rate = 0.55  # Default assumption: 55% win rate
        self.default_avg_win = 30.0   # Default $30 avg win
        self.default_avg_loss = 20.0  # Default $20 avg loss
        
        logger.info("📊 DynamicPositionSizer initialized")
        logger.info(f"   Base margin: ${self.min_margin}-${self.max_margin}")
        logger.info(f"   Leverage: {self.leverage}x")
        logger.info(f"   Kelly adjustment: {'ENABLED' if self.use_kelly else 'DISABLED'}")
        logger.info(f"   Quality multipliers: {self.quality_multipliers}")
    
    def calculate_position_size(
        self,
        balance_usd: float,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        quality_grade: str,
        symbol: str = "Unknown",
        strategy: str = None,
        confluence_score: float = None
    ) -> Dict:
        """
        Optimal pozisyon boyutu hesapla
        
        Args:
            balance_usd: Total account balance
            entry_price: Entry price
            sl_price: Stop loss price
            tp_price: Take profit price
            quality_grade: Signal quality (A/B/C/D)
            symbol: Trading symbol
            strategy: Strategy name (for performance tracking)
            confluence_score: Confluence score (optional boost)
        
        Returns:
            {
                'margin_usd': 7.5,  # Kullanılacak margin
                'quantity': 0.15,   # Position size in base currency
                'position_value_usd': 75.0,  # Total position value (margin * leverage)
                'risk_usd': 15.0,   # Risk amount
                'reward_usd': 30.0,  # Potential reward
                'kelly_fraction': 0.08,  # Kelly optimal fraction
                'quality_multiplier': 1.5,  # Grade-based multiplier
                'confidence_multiplier': 1.1,  # Confluence-based multiplier
                'final_multiplier': 1.65,  # Total multiplier
                'reasoning': 'Kelly + A-grade + High confluence'
            }
        """
        try:
            # 1. Base margin (from config)
            base_margin = self.min_margin
            
            # 2. Quality multiplier
            quality_multiplier = self.quality_multipliers.get(quality_grade, 0.0)
            
            if quality_multiplier == 0.0:
                logger.warning(f"❌ {symbol} Quality grade {quality_grade} = 0.0 multiplier, no position")
                return {
                    'margin_usd': 0.0,
                    'quantity': 0.0,
                    'position_value_usd': 0.0,
                    'risk_usd': 0.0,
                    'reward_usd': 0.0,
                    'kelly_fraction': 0.0,
                    'quality_multiplier': 0.0,
                    'confidence_multiplier': 0.0,
                    'final_multiplier': 0.0,
                    'reasoning': f'Quality grade {quality_grade} rejected'
                }
            
            # 3. Kelly Criterion adjustment (if enabled)
            kelly_fraction = 0.0
            kelly_multiplier = 1.0
            
            if self.use_kelly:
                kelly_fraction = self._calculate_kelly_fraction(strategy, symbol)
                
                # Kelly multiplier (0.5x - 1.5x range)
                # If Kelly suggests high bet (>10%), increase margin up to 1.5x
                # If Kelly suggests low bet (<5%), decrease margin to 0.5x
                if kelly_fraction > 0.10:
                    kelly_multiplier = min(1.5, 1.0 + (kelly_fraction - 0.10) * 5)
                elif kelly_fraction < 0.05:
                    kelly_multiplier = max(0.5, 0.5 + (kelly_fraction / 0.05) * 0.5)
                else:
                    kelly_multiplier = 1.0
            
            # 4. Confluence score bonus (if provided)
            confidence_multiplier = 1.0
            
            if confluence_score is not None:
                # High confluence (>8.0) = 1.2x multiplier
                # Medium confluence (5-8) = 1.0x multiplier
                # Low confluence (<5) = 0.8x multiplier
                if confluence_score >= 8.0:
                    confidence_multiplier = 1.2
                elif confluence_score >= 5.0:
                    confidence_multiplier = 1.0
                else:
                    confidence_multiplier = 0.8
            
            # 5. Final margin calculation
            final_multiplier = quality_multiplier * kelly_multiplier * confidence_multiplier
            margin_usd = base_margin * final_multiplier
            
            # Cap at max margin
            margin_usd = min(margin_usd, self.max_margin)
            margin_usd = max(margin_usd, self.min_margin * 0.5)  # Min floor: 50% of min_margin
            
            # 6. Calculate position details
            position_value_usd = margin_usd * self.leverage
            
            # Quantity in base currency
            quantity = position_value_usd / entry_price
            
            # Risk/Reward in USD
            risk_distance = abs(entry_price - sl_price)
            reward_distance = abs(tp_price - entry_price)
            
            risk_usd = quantity * risk_distance
            reward_usd = quantity * reward_distance
            
            # 7. Reasoning
            reasoning_parts = []
            if self.use_kelly and kelly_fraction > 0.05:
                reasoning_parts.append(f"Kelly {kelly_fraction:.1%}")
            reasoning_parts.append(f"Grade {quality_grade} ({quality_multiplier}x)")
            if confluence_score:
                reasoning_parts.append(f"Confluence {confluence_score:.1f}")
            
            reasoning = " + ".join(reasoning_parts)
            
            result = {
                'margin_usd': round(margin_usd, 2),
                'quantity': round(quantity, 8),
                'position_value_usd': round(position_value_usd, 2),
                'risk_usd': round(risk_usd, 2),
                'reward_usd': round(reward_usd, 2),
                'kelly_fraction': round(kelly_fraction, 3),
                'quality_multiplier': quality_multiplier,
                'confidence_multiplier': confidence_multiplier,
                'final_multiplier': round(final_multiplier, 2),
                'reasoning': reasoning
            }
            
            logger.info(f"💰 {symbol} Position Sizing:")
            logger.info(f"   Margin: ${margin_usd:.2f} (base ${base_margin} × {final_multiplier:.2f})")
            logger.info(f"   Quantity: {quantity:.8f}")
            logger.info(f"   Position Value: ${position_value_usd:.2f} ({self.leverage}x leverage)")
            logger.info(f"   Risk: ${risk_usd:.2f}, Reward: ${reward_usd:.2f}")
            logger.info(f"   Reasoning: {reasoning}")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Position sizing calculation error: {e}", exc_info=True)
            return {
                'margin_usd': self.min_margin,
                'quantity': 0.0,
                'position_value_usd': 0.0,
                'risk_usd': 0.0,
                'reward_usd': 0.0,
                'kelly_fraction': 0.0,
                'quality_multiplier': 1.0,
                'confidence_multiplier': 1.0,
                'final_multiplier': 1.0,
                'reasoning': 'Error fallback'
            }
    
    def _calculate_kelly_fraction(self, strategy: str = None, symbol: str = "Unknown") -> float:
        """
        Calculate Kelly Criterion optimal bet fraction
        
        Kelly Formula: f* = (p * b - q) / b
        
        Args:
            strategy: Strategy name (to lookup performance)
            symbol: Symbol name (for logging)
        
        Returns:
            Optimal bet fraction (capped at KELLY_MAX_FRACTION)
        """
        try:
            # TODO: Load actual win rate and avg win/loss from database
            # For now, use defaults
            win_rate = self.default_win_rate
            avg_win = self.default_avg_win
            avg_loss = self.default_avg_loss
            
            # Strategy-specific adjustments (if we have historical data)
            # This would be loaded from TradeHistory table in production
            if strategy == 'MOMENTUM_SCALP':
                # Scalping typically has higher win rate but smaller wins
                win_rate = 0.65
                avg_win = 20.0
                avg_loss = 15.0
            elif strategy == 'BREAKOUT':
                # Breakouts have lower win rate but bigger wins
                win_rate = 0.45
                avg_win = 50.0
                avg_loss = 20.0
            elif strategy == 'MEAN_REVERSION':
                # Mean reversion moderate win rate
                win_rate = 0.60
                avg_win = 25.0
                avg_loss = 18.0
            
            # Kelly calculation
            p = win_rate
            q = 1 - p
            b = avg_win / avg_loss if avg_loss > 0 else 2.0  # Odds
            
            kelly_fraction = (p * b - q) / b
            
            # Safety checks
            if kelly_fraction < 0:
                # Negative Kelly = negative edge, should not trade
                logger.warning(f"⚠️ {symbol} Negative Kelly fraction ({kelly_fraction:.2%}), edge is negative!")
                return 0.0
            
            # Cap at maximum fraction (risk management)
            kelly_fraction = min(kelly_fraction, self.kelly_max_fraction)
            
            logger.debug(f"   Kelly Criterion: {kelly_fraction:.1%} (win rate: {p:.1%}, odds: {b:.2f})")
            
            return kelly_fraction
        
        except Exception as e:
            logger.error(f"Kelly fraction calculation error: {e}")
            return 0.05  # Conservative default: 5%
    
    def update_performance_stats(
        self,
        strategy: str,
        symbol: str,
        win: bool,
        pnl: float
    ):
        """
        Update performance statistics (for Kelly calculation)
        
        In production, this would update database records.
        For now, it's a placeholder.
        
        Args:
            strategy: Strategy name
            symbol: Symbol
            win: True if win, False if loss
            pnl: P&L amount
        """
        # TODO: Implement database update
        # Update win_rate, avg_win, avg_loss per strategy
        logger.debug(f"Performance update: {strategy} {symbol} {'WIN' if win else 'LOSS'} ${pnl:.2f}")


# Global instance (singleton)
_position_sizer_instance = None


def get_position_sizer(config) -> DynamicPositionSizer:
    """
    Get or create DynamicPositionSizer singleton
    
    Args:
        config: Configuration object
    
    Returns:
        DynamicPositionSizer instance
    """
    global _position_sizer_instance
    
    if _position_sizer_instance is None:
        _position_sizer_instance = DynamicPositionSizer(config)
    
    return _position_sizer_instance
