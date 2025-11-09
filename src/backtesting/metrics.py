"""
Performance Metrics Calculator
Sharpe Ratio, Sortino Ratio, Max Drawdown, Profit Factor, vb.
"""

import numpy as np
import pandas as pd
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """
    Professional trading performance metrics
    - Sharpe Ratio (risk-adjusted return)
    - Sortino Ratio (downside risk-adjusted return)
    - Maximum Drawdown
    - Calmar Ratio
    - Win Rate, Profit Factor
    - Average R:R ratio
    """
    
    @staticmethod
    def calculate_returns(equity_curve: pd.DataFrame) -> pd.Series:
        """
        Equity curve'den returns hesapla
        
        Args:
            equity_curve: DataFrame with 'total_equity' column
        
        Returns:
            Series of percentage returns
        """
        if 'total_equity' not in equity_curve.columns:
            raise ValueError("equity_curve must have 'total_equity' column")
        
        returns = equity_curve['total_equity'].pct_change().fillna(0)
        return returns
    
    @staticmethod
    def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
        """
        Sharpe Ratio hesapla
        
        Args:
            returns: Return series
            risk_free_rate: Annual risk-free rate (örn: 0.02 = 2%)
            periods_per_year: 252 for daily, 52 for weekly
        
        Returns:
            Sharpe ratio
        """
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / periods_per_year)
        sharpe = np.sqrt(periods_per_year) * (excess_returns.mean() / excess_returns.std())
        return sharpe
    
    @staticmethod
    def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
        """
        Sortino Ratio hesapla (sadece downside volatility)
        
        Args:
            returns: Return series
            risk_free_rate: Annual risk-free rate
            periods_per_year: 252 for daily
        
        Returns:
            Sortino ratio
        """
        if len(returns) == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / periods_per_year)
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return float('inf') if excess_returns.mean() > 0 else 0.0
        
        sortino = np.sqrt(periods_per_year) * (excess_returns.mean() / downside_returns.std())
        return sortino
    
    @staticmethod
    def max_drawdown(equity_curve: pd.DataFrame) -> Dict:
        """
        Maximum Drawdown hesapla
        
        Args:
            equity_curve: DataFrame with 'total_equity' column
        
        Returns:
            dict with max_drawdown, max_drawdown_pct, drawdown_duration
        """
        if 'total_equity' not in equity_curve.columns:
            raise ValueError("equity_curve must have 'total_equity' column")
        
        equity = equity_curve['total_equity']
        
        # Running maximum
        running_max = equity.expanding().max()
        
        # Drawdown
        drawdown = equity - running_max
        drawdown_pct = (drawdown / running_max) * 100
        
        max_dd = drawdown.min()
        max_dd_pct = drawdown_pct.min()
        
        # Drawdown duration (periods)
        is_underwater = drawdown < 0
        duration = 0
        max_duration = 0
        current_duration = 0
        
        for underwater in is_underwater:
            if underwater:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0
        
        return {
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'max_drawdown_duration': max_duration
        }
    
    @staticmethod
    def calmar_ratio(total_return: float, max_drawdown_pct: float) -> float:
        """
        Calmar Ratio = Annual Return / Max Drawdown
        
        Args:
            total_return: Total return percentage
            max_drawdown_pct: Max drawdown percentage (negative)
        
        Returns:
            Calmar ratio
        """
        if max_drawdown_pct == 0:
            return float('inf') if total_return > 0 else 0.0
        
        return total_return / abs(max_drawdown_pct)
    
    @staticmethod
    def win_rate(trades: List) -> float:
        """
        Win rate hesapla
        
        Args:
            trades: List of Trade objects (must have pnl_usd attribute)
        
        Returns:
            Win rate percentage (0-100)
        """
        if len(trades) == 0:
            return 0.0
        
        winning_trades = sum(1 for t in trades if t.pnl_usd > 0)
        return (winning_trades / len(trades)) * 100
    
    @staticmethod
    def profit_factor(trades: List) -> float:
        """
        Profit Factor = Gross Profit / Gross Loss
        
        Args:
            trades: List of Trade objects
        
        Returns:
            Profit factor
        """
        if len(trades) == 0:
            return 0.0
        
        gross_profit = sum(t.pnl_usd for t in trades if t.pnl_usd > 0)
        gross_loss = abs(sum(t.pnl_usd for t in trades if t.pnl_usd < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    @staticmethod
    def average_rr_ratio(trades: List) -> float:
        """
        Average Risk:Reward ratio (realized)
        
        Args:
            trades: List of Trade objects with pnl_percent
        
        Returns:
            Average R:R ratio
        """
        if len(trades) == 0:
            return 0.0
        
        # Simplified: PnL percent / risk percent (assume 10% SL)
        avg_return = np.mean([t.pnl_percent for t in trades])
        assumed_risk = 10.0  # 10% SL
        
        return avg_return / assumed_risk if assumed_risk > 0 else 0.0
    
    @staticmethod
    def expectancy(trades: List) -> float:
        """
        Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        
        Args:
            trades: List of Trade objects
        
        Returns:
            Expected value per trade (USD)
        """
        if len(trades) == 0:
            return 0.0
        
        wins = [t.pnl_usd for t in trades if t.pnl_usd > 0]
        losses = [t.pnl_usd for t in trades if t.pnl_usd < 0]
        
        win_rate = len(wins) / len(trades)
        loss_rate = len(losses) / len(trades)
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        
        return (win_rate * avg_win) + (loss_rate * avg_loss)
    
    @staticmethod
    def generate_report(equity_curve: pd.DataFrame, trades: List, initial_capital: float) -> Dict:
        """
        Comprehensive performance report
        
        Args:
            equity_curve: DataFrame with timestamp, total_equity
            trades: List of Trade objects
            initial_capital: Starting capital
        
        Returns:
            Dict with all metrics
        """
        if len(equity_curve) == 0:
            return {}
        
        final_capital = equity_curve['total_equity'].iloc[-1]
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100
        
        returns = PerformanceMetrics.calculate_returns(equity_curve)
        
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
        sortino = PerformanceMetrics.sortino_ratio(returns)
        
        dd_metrics = PerformanceMetrics.max_drawdown(equity_curve)
        calmar = PerformanceMetrics.calmar_ratio(total_return_pct, dd_metrics['max_drawdown_pct'])
        
        win_rt = PerformanceMetrics.win_rate(trades)
        pf = PerformanceMetrics.profit_factor(trades)
        exp = PerformanceMetrics.expectancy(trades)
        
        return {
            'initial_capital': initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': dd_metrics['max_drawdown'],
            'max_drawdown_pct': dd_metrics['max_drawdown_pct'],
            'max_drawdown_duration': dd_metrics['max_drawdown_duration'],
            'calmar_ratio': calmar,
            'total_trades': len(trades),
            'win_rate': win_rt,
            'profit_factor': pf,
            'expectancy': exp
        }


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Simulated equity curve
    equity_data = {
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='D'),
        'total_equity': np.cumsum(np.random.randn(100) * 10 + 2) + 1000
    }
    equity_curve = pd.DataFrame(equity_data)
    
    # Simulated trades
    from dataclasses import dataclass
    
    @dataclass
    class DummyTrade:
        pnl_usd: float
        pnl_percent: float
    
    trades = [
        DummyTrade(pnl_usd=10, pnl_percent=5),
        DummyTrade(pnl_usd=-5, pnl_percent=-2.5),
        DummyTrade(pnl_usd=15, pnl_percent=7.5),
        DummyTrade(pnl_usd=-3, pnl_percent=-1.5),
    ]
    
    report = PerformanceMetrics.generate_report(equity_curve, trades, initial_capital=1000.0)
    
    print("\n" + "=" * 60)
    print("PERFORMANCE METRICS TEST")
    print("=" * 60)
    for key, value in report.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
