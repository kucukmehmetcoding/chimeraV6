#!/usr/bin/env python3
"""
Performance Analyzer - Detaylı Kar/Zarar Analizi
ChimeraBot v10.7 için gelişmiş performans metrikleri
"""

import sys
from datetime import datetime, timedelta
from tabulate import tabulate
import pandas as pd

from src.database.models import db_session, OpenPosition, TradeHistory
from src.data_fetcher.binance_fetcher import get_current_price

class PerformanceAnalyzer:
    """Detaylı performans analiz sınıfı"""
    
    def __init__(self):
        self.db = db_session()
    
    def __del__(self):
        db_session.remove()
    
    def get_all_open_positions(self):
        """Tüm açık pozisyonları çek"""
        return self.db.query(OpenPosition).filter(OpenPosition.status == 'OPEN').all()
    
    def get_all_closed_trades(self):
        """Tüm kapalı trade'leri çek"""
        return self.db.query(TradeHistory).all()
    
    def calculate_unrealized_pnl(self):
        """Gerçekleşmemiş kar/zarar hesapla"""
        positions = self.get_all_open_positions()
        
        total_unrealized = 0
        position_details = []
        
        for pos in positions:
            current_price = get_current_price(pos.symbol)
            
            if current_price is None:
                current_price = pos.entry_price
            
            # PnL hesapla
            if pos.direction == 'LONG':
                pnl_percent = ((current_price - pos.entry_price) / pos.entry_price) * 100
            else:
                pnl_percent = ((pos.entry_price - current_price) / pos.entry_price) * 100
            
            # Kaldıraçlı PnL
            pnl_percent_lev = pnl_percent * pos.leverage
            
            # USD bazında
            position_value = pos.entry_price * pos.amount
            pnl_usd = (position_value * pnl_percent_lev) / 100
            
            total_unrealized += pnl_usd
            
            # Açılış zamanı
            open_ts = pos.open_time / 1000 if pos.open_time > 1000000000000 else pos.open_time
            duration = datetime.now() - datetime.fromtimestamp(open_ts)
            
            position_details.append({
                'id': pos.id,
                'symbol': pos.symbol,
                'direction': pos.direction,
                'entry': pos.entry_price,
                'current': current_price,
                'pnl_usd': pnl_usd,
                'pnl_percent': pnl_percent_lev,
                'amount': pos.amount,
                'leverage': pos.leverage,
                'duration_hours': duration.total_seconds() / 3600,
                'score': pos.hybrid_score,
                'strategy': pos.strategy
            })
        
        return total_unrealized, position_details
    
    def calculate_realized_pnl(self):
        """Gerçekleşen kar/zarar hesapla"""
        trades = self.get_all_closed_trades()
        
        if not trades:
            return None
        
        total_pnl = 0
        wins = []
        losses = []
        
        for trade in trades:
            total_pnl += trade.pnl_usd
            
            if trade.pnl_usd > 0:
                wins.append(trade)
            else:
                losses.append(trade)
        
        # İstatistikler
        win_count = len(wins)
        loss_count = len(losses)
        total_trades = win_count + loss_count
        
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        total_win_pnl = sum(t.pnl_usd for t in wins)
        total_loss_pnl = sum(abs(t.pnl_usd) for t in losses)
        
        avg_win = total_win_pnl / win_count if win_count > 0 else 0
        avg_loss = total_loss_pnl / loss_count if loss_count > 0 else 0
        
        profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else float('inf')
        
        # Max win/loss
        max_win = max((t.pnl_usd for t in wins), default=0)
        max_loss = min((t.pnl_usd for t in losses), default=0)
        
        # Consecutive wins/losses
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        
        sorted_trades = sorted(trades, key=lambda x: x.close_time)
        for trade in sorted_trades:
            if trade.pnl_usd > 0:
                consecutive_wins += 1
                consecutive_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            else:
                consecutive_losses += 1
                consecutive_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        
        return {
            'total_pnl': total_pnl,
            'total_trades': total_trades,
            'win_count': win_count,
            'loss_count': loss_count,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_win': max_win,
            'max_loss': max_loss,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'wins': wins,
            'losses': losses
        }
    
    def calculate_sharpe_ratio(self, trades, risk_free_rate=0):
        """Sharpe Ratio hesapla"""
        if not trades or len(trades) < 2:
            return None
        
        returns = [t.pnl_percent for t in trades]
        
        avg_return = sum(returns) / len(returns)
        std_dev = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
        
        if std_dev == 0:
            return None
        
        sharpe = (avg_return - risk_free_rate) / std_dev
        return sharpe
    
    def calculate_max_drawdown(self, trades):
        """Maximum Drawdown hesapla"""
        if not trades:
            return 0, []
        
        sorted_trades = sorted(trades, key=lambda x: x.close_time)
        
        cumulative_pnl = []
        running_total = 0
        
        for trade in sorted_trades:
            running_total += trade.pnl_usd
            cumulative_pnl.append(running_total)
        
        max_dd = 0
        peak = cumulative_pnl[0]
        
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd, cumulative_pnl
    
    def analyze_by_direction(self, trades):
        """Direction bazında analiz"""
        long_trades = [t for t in trades if t.direction == 'LONG']
        short_trades = [t for t in trades if t.direction == 'SHORT']
        
        def calc_stats(trades_list):
            if not trades_list:
                return None
            
            total = len(trades_list)
            wins = len([t for t in trades_list if t.pnl_usd > 0])
            total_pnl = sum(t.pnl_usd for t in trades_list)
            win_rate = (wins / total * 100) if total > 0 else 0
            
            return {
                'total': total,
                'wins': wins,
                'losses': total - wins,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': total_pnl / total if total > 0 else 0
            }
        
        return {
            'long': calc_stats(long_trades),
            'short': calc_stats(short_trades)
        }
    
    def analyze_by_strategy(self, trades):
        """Strategy bazında analiz"""
        strategies = {}
        
        for trade in trades:
            strategy = trade.strategy or 'unknown'
            
            if strategy not in strategies:
                strategies[strategy] = []
            
            strategies[strategy].append(trade)
        
        results = {}
        for strategy, trade_list in strategies.items():
            total = len(trade_list)
            wins = len([t for t in trade_list if t.pnl_usd > 0])
            total_pnl = sum(t.pnl_usd for t in trade_list)
            
            results[strategy] = {
                'total': total,
                'wins': wins,
                'win_rate': (wins / total * 100) if total > 0 else 0,
                'total_pnl': total_pnl
            }
        
        return results
    
    def print_summary_report(self):
        """Özet rapor yazdır"""
        print("\n" + "="*100)
        print("📊 CHIMERABOT v10.7 - DETAYLI PERFORMANS ANALİZİ")
        print("="*100)
        
        # AÇIK POZİSYONLAR
        unrealized_pnl, open_positions = self.calculate_unrealized_pnl()
        
        print("\n🔴 AÇIK POZİSYONLAR")
        print("-"*100)
        
        if open_positions:
            for pos in open_positions:
                status_emoji = "🟢" if pos['pnl_usd'] >= 0 else "🔴"
                print(f"{status_emoji} {pos['symbol']} {pos['direction']} {pos['leverage']}x")
                print(f"   Entry: ${pos['entry']:.4f} → Current: ${pos['current']:.4f}")
                print(f"   PnL: ${pos['pnl_usd']:.2f} ({pos['pnl_percent']:.2f}%)")
                print(f"   Süre: {pos['duration_hours']:.1f}h | Score: {pos['score']:.1f}")
            
            print(f"\n💵 Toplam Gerçekleşmemiş PnL: ${unrealized_pnl:.2f}")
        else:
            print("❌ Açık pozisyon yok")
        
        # KAPALI TRADE'LER
        realized = self.calculate_realized_pnl()
        
        if realized:
            print("\n" + "="*100)
            print("📈 GERÇEKLEŞEN TRADE İSTATİSTİKLERİ")
            print("-"*100)
            
            print(f"📊 Toplam Trade: {realized['total_trades']}")
            print(f"✅ Kazanan: {realized['win_count']} ({realized['win_rate']:.1f}%)")
            print(f"❌ Kaybeden: {realized['loss_count']}")
            print(f"💰 Toplam Gerçekleşen PnL: ${realized['total_pnl']:.2f}")
            print(f"📈 Ortalama Kazanç: ${realized['avg_win']:.2f}")
            print(f"📉 Ortalama Kayıp: ${realized['avg_loss']:.2f}")
            print(f"⚖️  Profit Factor: {realized['profit_factor']:.2f}")
            print(f"🏆 Max Kazanç: ${realized['max_win']:.2f}")
            print(f"💔 Max Kayıp: ${realized['max_loss']:.2f}")
            print(f"🔥 Max Ardışık Kazanç: {realized['max_consecutive_wins']}")
            print(f"❄️  Max Ardışık Kayıp: {realized['max_consecutive_losses']}")
            
            # Sharpe Ratio
            all_trades = self.get_all_closed_trades()
            sharpe = self.calculate_sharpe_ratio(all_trades)
            if sharpe:
                print(f"📐 Sharpe Ratio: {sharpe:.2f}")
            
            # Max Drawdown
            max_dd, _ = self.calculate_max_drawdown(all_trades)
            print(f"📉 Maximum Drawdown: ${max_dd:.2f}")
            
            # Direction Analysis
            direction_stats = self.analyze_by_direction(all_trades)
            
            print("\n" + "="*100)
            print("📊 DIRECTION BAZINDA ANALİZ")
            print("-"*100)
            
            if direction_stats['long']:
                long = direction_stats['long']
                print(f"📈 LONG Trades:")
                print(f"   Total: {long['total']} | Wins: {long['wins']} | Win Rate: {long['win_rate']:.1f}%")
                print(f"   Total PnL: ${long['total_pnl']:.2f} | Avg: ${long['avg_pnl']:.2f}")
            
            if direction_stats['short']:
                short = direction_stats['short']
                print(f"📉 SHORT Trades:")
                print(f"   Total: {short['total']} | Wins: {short['wins']} | Win Rate: {short['win_rate']:.1f}%")
                print(f"   Total PnL: ${short['total_pnl']:.2f} | Avg: ${short['avg_pnl']:.2f}")
            
            # Strategy Analysis
            strategy_stats = self.analyze_by_strategy(all_trades)
            
            print("\n" + "="*100)
            print("🎯 STRATEGY BAZINDA ANALİZ")
            print("-"*100)
            
            for strategy, stats in strategy_stats.items():
                print(f"📌 {strategy}:")
                print(f"   Total: {stats['total']} | Wins: {stats['wins']} | Win Rate: {stats['win_rate']:.1f}%")
                print(f"   Total PnL: ${stats['total_pnl']:.2f}")
        
        else:
            print("\n❌ Hiç kapalı trade yok")
        
        # NET TOPLAM
        print("\n" + "="*100)
        print("💎 GENEL DURUM")
        print("-"*100)
        
        net_pnl = (realized['total_pnl'] if realized else 0) + unrealized_pnl
        
        print(f"💰 Gerçekleşen PnL: ${realized['total_pnl']:.2f}" if realized else "💰 Gerçekleşen PnL: $0.00")
        print(f"💵 Gerçekleşmemiş PnL: ${unrealized_pnl:.2f}")
        print(f"💎 NET TOPLAM PnL: ${net_pnl:.2f}")
        
        if net_pnl > 0:
            print(f"\n✅ SİSTEM KÂRLI! +${net_pnl:.2f}")
        elif net_pnl < 0:
            print(f"\n❌ SİSTEM ZARARDA! ${net_pnl:.2f}")
        else:
            print(f"\n⚖️  SİSTEM BAŞABAŞ")
        
        print("\n" + "="*100)
        print(f"🕒 Rapor Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*100 + "\n")


def main():
    """Ana fonksiyon"""
    analyzer = PerformanceAnalyzer()
    analyzer.print_summary_report()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Analiz iptal edildi")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
