"""
Backtest Engine - Event-Driven Simulation
Position tracking, PnL calculation, slippage/commission modeling
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Backtest position model"""
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    entry_time: datetime
    position_size: float  # Units
    sl_price: float
    tp_price: float
    
    # Partial TP
    partial_tp_1_price: Optional[float] = None
    partial_tp_2_price: Optional[float] = None
    partial_tp_1_taken: bool = False
    partial_tp_2_taken: bool = False
    original_size: float = field(init=False)
    
    # Strategy metadata
    strategy: str = 'UNKNOWN'
    quality_grade: str = 'C'
    
    def __post_init__(self):
        self.original_size = self.position_size
    
    def is_closed(self) -> bool:
        """Pozisyon tamamen kapandı mı?"""
        return self.position_size <= 0


@dataclass
class Trade:
    """Closed trade record"""
    symbol: str
    strategy: str
    direction: str
    entry_price: float
    close_price: float
    entry_time: datetime
    close_time: datetime
    position_size: float
    pnl_usd: float
    pnl_percent: float
    close_reason: str  # 'SL', 'TP', 'PARTIAL_TP_1', 'PARTIAL_TP_2'
    quality_grade: str = 'C'


class BacktestEngine:
    """
    Event-driven backtest engine
    - Candle-by-candle replay
    - Position management (SL/TP/Partial TP)
    - Commission and slippage modeling
    - Equity curve tracking
    """
    
    def __init__(
        self,
        initial_capital: float = 1000.0,
        commission_rate: float = 0.0004,  # 0.04% Binance Futures maker/taker avg
        slippage_pct: float = 0.0005,  # 0.05% slippage
        max_positions: int = 3,
        fixed_risk_usd: float = 5.0
    ):
        """
        Args:
            initial_capital: Starting capital in USD
            commission_rate: Commission per trade (0.0004 = 0.04%)
            slippage_pct: Price slippage percentage
            max_positions: Maximum concurrent positions
            fixed_risk_usd: Fixed risk per position
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_pct = slippage_pct
        self.max_positions = max_positions
        self.fixed_risk_usd = fixed_risk_usd
        
        # State
        self.open_positions: List[Position] = []
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        
        # Metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        logger.info(f"🚀 Backtest Engine initialized: ${initial_capital} capital, {max_positions} max positions")
    
    def apply_slippage(self, price: float, direction: str) -> float:
        """
        Slippage uygula
        LONG entry: price artışı (daha pahalı al)
        SHORT entry: price azalışı (daha ucuz sat)
        """
        if direction == 'LONG':
            return price * (1 + self.slippage_pct)
        else:
            return price * (1 - self.slippage_pct)
    
    def calculate_commission(self, notional: float) -> float:
        """Commission hesapla (notional value üzerinden)"""
        return notional * self.commission_rate
    
    def can_open_position(self) -> bool:
        """Yeni pozisyon açılabilir mi?"""
        return len(self.open_positions) < self.max_positions
    
    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        entry_time: datetime,
        strategy: str = 'UNKNOWN',
        quality_grade: str = 'C',
        partial_tp_1_price: Optional[float] = None,
        partial_tp_2_price: Optional[float] = None
    ) -> bool:
        """
        Pozisyon aç
        
        Returns:
            True if position opened successfully
        """
        if not self.can_open_position():
            logger.debug(f"   ⏭️  Max positions reached ({self.max_positions})")
            return False
        
        # Slippage uygula
        actual_entry = self.apply_slippage(entry_price, direction)
        
        # Position sizing (fixed risk)
        sl_distance = abs(actual_entry - sl_price)
        position_size = self.fixed_risk_usd / sl_distance if sl_distance > 0 else 0
        
        if position_size <= 0:
            logger.warning(f"   ⚠️ Invalid position size: {position_size}")
            return False
        
        # Notional value
        notional = actual_entry * position_size
        
        # Commission
        commission = self.calculate_commission(notional)
        self.capital -= commission
        
        # Create position
        pos = Position(
            symbol=symbol,
            direction=direction,
            entry_price=actual_entry,
            entry_time=entry_time,
            position_size=position_size,
            sl_price=sl_price,
            tp_price=tp_price,
            partial_tp_1_price=partial_tp_1_price,
            partial_tp_2_price=partial_tp_2_price,
            strategy=strategy,
            quality_grade=quality_grade
        )
        
        self.open_positions.append(pos)
        self.total_trades += 1
        
        logger.debug(f"   ✅ OPENED: {symbol} {direction} @ ${actual_entry:.4f} | Size: {position_size:.4f} | SL: ${sl_price:.4f} | TP: ${tp_price:.4f}")
        
        return True
    
    def close_position(
        self,
        pos: Position,
        close_price: float,
        close_time: datetime,
        close_reason: str,
        partial_close: bool = False,
        partial_size: Optional[float] = None
    ):
        """
        Pozisyon kapat (tam veya kısmi)
        
        Args:
            pos: Position object
            close_price: Kapanış fiyatı
            close_time: Kapanış zamanı
            close_reason: 'SL', 'TP', 'PARTIAL_TP_1', 'PARTIAL_TP_2'
            partial_close: Kısmi kapanış mı?
            partial_size: Kapatılacak size (partial ise)
        """
        # Slippage uygula (closing direction opposite of entry)
        close_direction = 'SHORT' if pos.direction == 'LONG' else 'LONG'
        actual_close = self.apply_slippage(close_price, close_direction)
        
        # Kapatılacak size
        size_to_close = partial_size if partial_close else pos.position_size
        
        # PnL hesapla
        if pos.direction == 'LONG':
            pnl_usd = (actual_close - pos.entry_price) * size_to_close
        else:  # SHORT
            pnl_usd = (pos.entry_price - actual_close) * size_to_close
        
        # Commission
        notional = actual_close * size_to_close
        commission = self.calculate_commission(notional)
        pnl_usd -= commission
        
        # Capital update
        self.capital += pnl_usd
        
        # PnL percentage
        pnl_percent = (pnl_usd / (pos.entry_price * size_to_close)) * 100
        
        # Create trade record
        trade = Trade(
            symbol=pos.symbol,
            strategy=pos.strategy,
            direction=pos.direction,
            entry_price=pos.entry_price,
            close_price=actual_close,
            entry_time=pos.entry_time,
            close_time=close_time,
            position_size=size_to_close,
            pnl_usd=pnl_usd,
            pnl_percent=pnl_percent,
            close_reason=close_reason,
            quality_grade=pos.quality_grade
        )
        
        self.closed_trades.append(trade)
        
        # Update stats
        if pnl_usd > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Partial close ise position'ı güncelle
        if partial_close:
            pos.position_size -= size_to_close
            logger.debug(f"   🎯 PARTIAL CLOSE: {pos.symbol} {close_reason} @ ${actual_close:.4f} | Size: {size_to_close:.4f} | PnL: ${pnl_usd:.2f} ({pnl_percent:.2f}%)")
        else:
            # Tam kapanış - listeden çıkar
            if pos in self.open_positions:
                self.open_positions.remove(pos)
            logger.debug(f"   🔴 CLOSED: {pos.symbol} {close_reason} @ ${actual_close:.4f} | PnL: ${pnl_usd:.2f} ({pnl_percent:.2f}%)")
    
    def check_exits(self, current_time: datetime, current_price: float):
        """
        Açık pozisyonları kontrol et, SL/TP/Partial TP tetiklenmiş mi?
        
        Args:
            current_time: Current candle timestamp
            current_price: Current close price (or high/low for accuracy)
        """
        positions_to_close = []
        
        for pos in self.open_positions:
            # TP1 check
            if pos.partial_tp_1_price and not pos.partial_tp_1_taken:
                if (pos.direction == 'LONG' and current_price >= pos.partial_tp_1_price) or \
                   (pos.direction == 'SHORT' and current_price <= pos.partial_tp_1_price):
                    # Partial close: 50%
                    partial_size = pos.original_size * 0.5
                    self.close_position(pos, pos.partial_tp_1_price, current_time, 'PARTIAL_TP_1', partial_close=True, partial_size=partial_size)
                    pos.partial_tp_1_taken = True
                    continue
            
            # TP2 check (only if TP1 taken)
            if pos.partial_tp_2_price and pos.partial_tp_1_taken and not pos.partial_tp_2_taken:
                if (pos.direction == 'LONG' and current_price >= pos.partial_tp_2_price) or \
                   (pos.direction == 'SHORT' and current_price <= pos.partial_tp_2_price):
                    # Close remaining position
                    positions_to_close.append((pos, pos.partial_tp_2_price, 'PARTIAL_TP_2'))
                    continue
            
            # SL check
            if (pos.direction == 'LONG' and current_price <= pos.sl_price) or \
               (pos.direction == 'SHORT' and current_price >= pos.sl_price):
                positions_to_close.append((pos, pos.sl_price, 'STOP_LOSS'))
                continue
            
            # Full TP check
            if (pos.direction == 'LONG' and current_price >= pos.tp_price) or \
               (pos.direction == 'SHORT' and current_price <= pos.tp_price):
                positions_to_close.append((pos, pos.tp_price, 'TAKE_PROFIT'))
        
        # Close positions
        for pos, price, reason in positions_to_close:
            self.close_position(pos, price, current_time, reason)
    
    def update_equity_curve(self, timestamp: datetime):
        """Equity curve güncelle"""
        # Unrealized PnL hesapla (open positions için)
        unrealized_pnl = 0.0
        # Simplified - gerçekte current price gerekli
        
        self.equity_curve.append({
            'timestamp': timestamp,
            'capital': self.capital,
            'unrealized_pnl': unrealized_pnl,
            'total_equity': self.capital + unrealized_pnl,
            'open_positions': len(self.open_positions)
        })
    
    def get_summary(self) -> Dict:
        """Backtest özeti"""
        total_pnl = self.capital - self.initial_capital
        total_return_pct = (total_pnl / self.initial_capital) * 100
        
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        avg_win = np.mean([t.pnl_usd for t in self.closed_trades if t.pnl_usd > 0]) if self.winning_trades > 0 else 0
        avg_loss = np.mean([t.pnl_usd for t in self.closed_trades if t.pnl_usd < 0]) if self.losing_trades > 0 else 0
        
        profit_factor = abs(avg_win * self.winning_trades / (avg_loss * self.losing_trades)) if self.losing_trades > 0 else float('inf')
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    engine = BacktestEngine(initial_capital=1000.0, fixed_risk_usd=5.0)
    
    # Simulated trade
    from datetime import datetime
    
    # Open LONG
    engine.open_position(
        symbol='BTCUSDT',
        direction='LONG',
        entry_price=100.0,
        sl_price=90.0,
        tp_price=140.0,
        entry_time=datetime.now(),
        strategy='TEST',
        quality_grade='A',
        partial_tp_1_price=120.0,
        partial_tp_2_price=140.0
    )
    
    # Simulate TP1 hit
    engine.check_exits(datetime.now(), 120.0)
    
    # Simulate TP2 hit
    engine.check_exits(datetime.now(), 140.0)
    
    # Summary
    summary = engine.get_summary()
    print("\n" + "=" * 60)
    print("BACKTEST SUMMARY")
    print("=" * 60)
    for key, value in summary.items():
        print(f"{key}: {value}")
