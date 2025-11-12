"""
Backtest Runner - Main Orchestrator
CLI interface for running backtests with different strategies
"""

import os
import sys
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.backtesting.historical_data import HistoricalDataFetcher
from src.backtesting.engine import BacktestEngine
from src.backtesting.metrics import PerformanceMetrics
from src.technical_analyzer.indicators import calculate_indicators
from src.technical_analyzer.strategies import determine_regime
import src.config as config

logger = logging.getLogger(__name__)


class BacktestRunner:
    """
    Main backtest orchestrator
    - Fetches historical data
    - Applies strategies
    - Runs backtest engine
    - Generates performance reports
    """
    
    def __init__(
        self,
        symbol: str = 'BTCUSDT',
        start_date: str = '2024-05-01',
        end_date: Optional[str] = None,
        initial_capital: float = 1000.0,
        fixed_risk_usd: float = 5.0,
        max_positions: int = 3,
        strategy: str = 'AUTO'  # 'AUTO', 'PULLBACK', 'MEAN_REVERSION', 'BREAKOUT', 'ADVANCED_SCALP'
    ):
        """
        Args:
            symbol: Trading pair
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (None = today)
            initial_capital: Starting capital
            fixed_risk_usd: Fixed risk per trade
            max_positions: Max concurrent positions
            strategy: Strategy name or 'AUTO' for regime-based
        """
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        self.initial_capital = initial_capital
        self.fixed_risk_usd = fixed_risk_usd
        self.max_positions = max_positions
        self.strategy_name = strategy
        
        # Initialize components
        self.fetcher = HistoricalDataFetcher(use_cache=True)
        self.engine = BacktestEngine(
            initial_capital=initial_capital,
            fixed_risk_usd=fixed_risk_usd,
            max_positions=max_positions
        )
        
        # Data
        self.data_1d = None
        self.data_4h = None
        self.data_1h = None
        
        logger.info(f"🚀 Backtest Runner initialized: {symbol} | {start_date} → {self.end_date} | ${initial_capital} capital")
    
    def load_data(self):
        """Historical data yükle"""
        logger.info("📊 Loading historical data...")
        
        data = self.fetcher.fetch_multiple_timeframes(
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        self.data_1d = data.get('1d', pd.DataFrame())
        self.data_4h = data.get('4h', pd.DataFrame())
        self.data_1h = data.get('1h', pd.DataFrame())
        
        if self.data_1d.empty or self.data_4h.empty or self.data_1h.empty:
            raise ValueError("❌ Historical data yüklenemedi!")
        
        logger.info(f"   ✅ 1D: {len(self.data_1d)} candles")
        logger.info(f"   ✅ 4H: {len(self.data_4h)} candles")
        logger.info(f"   ✅ 1H: {len(self.data_1h)} candles")
    
    def calculate_indicators(self):
        """Technical indicators hesapla"""
        logger.info("🔬 Calculating technical indicators...")
        
        self.data_1d = calculate_indicators(self.data_1d)
        self.data_4h = calculate_indicators(self.data_4h)
        self.data_1h = calculate_indicators(self.data_1h)
        
        logger.info("   ✅ Indicators calculated")
    
    def get_strategy_signal(self, df_1d: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame, regime: str):
        """
        Apply strategy and get signal
        Simplified for backtest - generates basic signals based on regime
        
        Returns:
            dict with signal info or None
        """
        # Basitleştirilmiş sinyal üretimi
        # Gerçek stratejiler çok karmaşık olduğu için temel bir logic kullanıyoruz
        
        last_1h = df_1h.iloc[-1]
        current_price = last_1h['close']
        
        # Temel teknik göstergeler
        if 'rsi14' not in last_1h or pd.isna(last_1h['rsi14']):
            return None
        
        rsi = last_1h['rsi14']
        
        # Simple logic
        signal = None
        
        if regime == 'PULLBACK' and rsi < 35:  # Oversold
            signal = {
                'direction': 'LONG',
                'entry_price': current_price,
                'sl_price': current_price * 0.90,  # -10% SL
                'tp_price': current_price * 1.40,  # +40% TP
                'partial_tp_1_price': current_price * 1.20,  # +20% TP1
                'partial_tp_2_price': current_price * 1.40   # +40% TP2
            }
        elif regime == 'PULLBACK' and rsi > 65:  # Overbought
            signal = {
                'direction': 'SHORT',
                'entry_price': current_price,
                'sl_price': current_price * 1.10,  # +10% SL
                'tp_price': current_price * 0.60,  # -40% TP
                'partial_tp_1_price': current_price * 0.80,  # -20% TP1
                'partial_tp_2_price': current_price * 0.60   # -40% TP2
            }
        
        return signal
    
    def run(self):
        """Run backtest simulation"""
        logger.info("=" * 80)
        logger.info(f"🎯 BACKTEST BAŞLADI: {self.symbol} | {self.start_date} → {self.end_date}")
        logger.info("=" * 80)
        
        # Load data
        self.load_data()
        
        # Calculate indicators
        self.calculate_indicators()
        
        # Event-driven simulation (1H timeframe for execution)
        logger.info("\n🔄 Running event-driven simulation...")
        
        total_signals = 0
        signals_opened = 0
        
        for i in range(50, len(self.data_1h)):  # Start at 50 for indicator warmup
            current_row = self.data_1h.iloc[i]
            current_time = current_row['timestamp']
            current_price = current_row['close']
            
            # Check exits first
            self.engine.check_exits(current_time, current_price)
            
            # Get relevant 1D and 4H data up to this point
            df_1d_slice = self.data_1d[self.data_1d['timestamp'] <= current_time].copy()
            df_4h_slice = self.data_4h[self.data_4h['timestamp'] <= current_time].copy()
            df_1h_slice = self.data_1h.iloc[:i+1].copy()
            
            if len(df_1d_slice) < 50 or len(df_4h_slice) < 50:
                continue  # Not enough data for indicators
            
            # Determine regime
            regime = determine_regime(df_1d_slice, df_4h_slice)
            
            # Get strategy signal
            signal = self.get_strategy_signal(df_1d_slice, df_4h_slice, df_1h_slice, regime)
            
            if signal and signal.get('direction'):
                total_signals += 1
                
                # Try to open position
                opened = self.engine.open_position(
                    symbol=self.symbol,
                    direction=signal['direction'],
                    entry_price=current_price,
                    sl_price=signal.get('sl_price', current_price * 0.9),
                    tp_price=signal.get('tp_price', current_price * 1.4),
                    entry_time=current_time,
                    strategy=regime,
                    quality_grade='B',  # Simplified (no alpha in backtest)
                    partial_tp_1_price=signal.get('partial_tp_1_price'),
                    partial_tp_2_price=signal.get('partial_tp_2_price')
                )
                
                if opened:
                    signals_opened += 1
            
            # Update equity curve (every 100 candles to save memory)
            if i % 100 == 0:
                self.engine.update_equity_curve(current_time)
        
        # Final equity update
        self.engine.update_equity_curve(self.data_1h.iloc[-1]['timestamp'])
        
        # Close any remaining positions at final price
        final_price = self.data_1h.iloc[-1]['close']
        final_time = self.data_1h.iloc[-1]['timestamp']
        for pos in self.engine.open_positions[:]:  # Copy list to avoid modification during iteration
            self.engine.close_position(pos, final_price, final_time, 'BACKTEST_END')
        
        logger.info(f"\n📊 Signals: {total_signals} generated, {signals_opened} opened ({signals_opened/total_signals*100:.1f}%)" if total_signals > 0 else "\n📊 No signals generated")
        
        return self.engine
    
    def generate_report(self):
        """Generate performance report"""
        logger.info("\n" + "=" * 80)
        logger.info("📈 BACKTEST RESULTS")
        logger.info("=" * 80)
        
        # Get summary from engine
        engine_summary = self.engine.get_summary()
        
        # Get equity curve
        equity_df = pd.DataFrame(self.engine.equity_curve)
        
        if len(equity_df) > 0:
            # Calculate metrics
            report = PerformanceMetrics.generate_report(
                equity_curve=equity_df,
                trades=self.engine.closed_trades,
                initial_capital=self.initial_capital
            )
            
            # Print report
            print(f"\n💰 CAPITAL:")
            print(f"   Initial: ${report['initial_capital']:.2f}")
            print(f"   Final: ${report['final_capital']:.2f}")
            print(f"   Total Return: ${report['total_return']:.2f} ({report['total_return_pct']:.2f}%)")
            
            print(f"\n📊 PERFORMANCE:")
            print(f"   Sharpe Ratio: {report['sharpe_ratio']:.2f}")
            print(f"   Sortino Ratio: {report['sortino_ratio']:.2f}")
            print(f"   Calmar Ratio: {report['calmar_ratio']:.2f}")
            print(f"   Max Drawdown: ${report['max_drawdown']:.2f} ({report['max_drawdown_pct']:.2f}%)")
            print(f"   Max DD Duration: {report['max_drawdown_duration']} periods")
            
            print(f"\n🎲 TRADING STATS:")
            print(f"   Total Trades: {report['total_trades']}")
            print(f"   Win Rate: {report['win_rate']:.2f}%")
            print(f"   Profit Factor: {report['profit_factor']:.2f}")
            print(f"   Expectancy: ${report['expectancy']:.2f} per trade")
            
            # Save report to CSV
            report_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data',
                f'backtest_report_{self.symbol}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )
            
            report_df = pd.DataFrame([report])
            report_df.to_csv(report_file, index=False)
            logger.info(f"\n💾 Report saved: {report_file}")
            
            # Save trade history
            trades_file = report_file.replace('.csv', '_trades.csv')
            if self.engine.closed_trades:
                trades_data = []
                for t in self.engine.closed_trades:
                    trades_data.append({
                        'symbol': t.symbol,
                        'strategy': t.strategy,
                        'direction': t.direction,
                        'entry_price': t.entry_price,
                        'close_price': t.close_price,
                        'entry_time': t.entry_time,
                        'close_time': t.close_time,
                        'position_size': t.position_size,
                        'pnl_usd': t.pnl_usd,
                        'pnl_percent': t.pnl_percent,
                        'close_reason': t.close_reason
                    })
                trades_df = pd.DataFrame(trades_data)
                trades_df.to_csv(trades_file, index=False)
                logger.info(f"💾 Trades saved: {trades_file}")
        else:
            logger.warning("⚠️ No equity curve data to analyze")
        
        logger.info("\n" + "=" * 80)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='ChimeraBot Backtest Runner')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='Trading pair')
    parser.add_argument('--start', type=str, default='2024-05-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=1000.0, help='Initial capital')
    parser.add_argument('--risk', type=float, default=5.0, help='Fixed risk per trade (USD)')
    parser.add_argument('--max-positions', type=int, default=3, help='Max concurrent positions')
    parser.add_argument('--strategy', type=str, default='AUTO', 
                       choices=['AUTO', 'PULLBACK', 'MEAN_REVERSION', 'BREAKOUT', 'ADVANCED_SCALP'],
                       help='Strategy name or AUTO for regime-based')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )
    
    # Run backtest
    runner = BacktestRunner(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        fixed_risk_usd=args.risk,
        max_positions=args.max_positions,
        strategy=args.strategy
    )
    
    runner.run()
    runner.generate_report()


if __name__ == "__main__":
    main()
