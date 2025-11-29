#!/usr/bin/env python3
"""
Fibonacci Bot - Portfolio Manager
Portföy risk yönetimi ve pozisyon takibi
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger('fibonacci_bot.portfolio')


class PortfolioManager:
    """Portföy yöneticisi"""
    
    def __init__(self, database, max_total_budget: float = 1000.0, max_budget_per_coin: float = 100.0):
        """
        Args:
            database: FibonacciDatabase instance
            max_total_budget: Maksimum toplam bütçe (USD)
            max_budget_per_coin: Coin başına maksimum bütçe (USD)
        """
        self.db = database
        self.MAX_TOTAL_BUDGET = max_total_budget
        self.MAX_BUDGET_PER_COIN = max_budget_per_coin
    
    def get_portfolio_summary(self) -> Dict:
        """Portföy özetini al"""
        try:
            summary = self.db.get_portfolio_summary()
            
            if not summary:
                return {
                    'total_positions': 0,
                    'total_invested': 0.0,
                    'available_budget': self.MAX_TOTAL_BUDGET,
                    'budget_usage_pct': 0.0,
                    'positions_by_symbol': {}
                }
            
            # Toplam yatırım
            total_invested = sum(s['total_spent'] for s in summary)
            
            # Kullanılabilir bütçe
            available_budget = self.MAX_TOTAL_BUDGET - total_invested
            
            # Bütçe kullanım yüzdesi
            budget_usage_pct = (total_invested / self.MAX_TOTAL_BUDGET) * 100
            
            # Symbol bazlı grupla ve pozisyon sayısını hesapla
            positions_by_symbol = {}
            for s in summary:
                symbol = s['symbol']
                open_positions = self.db.get_open_positions(symbol)
                positions_by_symbol[symbol] = {
                    'position_count': len(open_positions),
                    'total_quantity': s['total_quantity'],
                    'average_cost': s['avg_cost'],
                    'total_cost': s['total_spent']
                }
            
            return {
                'total_positions': len(summary),
                'total_invested': total_invested,
                'available_budget': max(0, available_budget),
                'budget_usage_pct': budget_usage_pct,
                'positions_by_symbol': positions_by_symbol
            }
            
        except Exception as e:
            logger.error(f"❌ Portföy özet hatası: {e}")
            return {
                'total_positions': 0,
                'total_invested': 0.0,
                'available_budget': self.MAX_TOTAL_BUDGET,
                'budget_usage_pct': 0.0,
                'positions_by_symbol': {}
            }
    
    def can_open_position(self, symbol: str, required_budget: float) -> tuple[bool, str]:
        """Yeni pozisyon açılabilir mi?"""
        summary = self.get_portfolio_summary()
        
        # 1. Toplam bütçe kontrolü
        if summary['available_budget'] < required_budget:
            return False, f"Yetersiz bütçe (Kalan: ${summary['available_budget']:.2f}, Gerekli: ${required_budget:.2f})"
        
        # 2. Coin bazlı bütçe kontrolü
        symbol_positions = summary['positions_by_symbol'].get(symbol)
        
        if symbol_positions:
            current_investment = symbol_positions['total_cost']
            
            if current_investment + required_budget > self.MAX_BUDGET_PER_COIN:
                return False, f"{symbol} için maksimum bütçe aşılıyor (Mevcut: ${current_investment:.2f}, Limit: ${self.MAX_BUDGET_PER_COIN:.2f})"
        
        return True, "OK"
    
    def log_portfolio_status(self):
        """Portföy durumunu logla"""
        summary = self.get_portfolio_summary()
        
        logger.info("\n" + "="*60)
        logger.info("💼 PORTFÖY DURUMU")
        logger.info("="*60)
        logger.info(f"Toplam Pozisyon: {summary['total_positions']}")
        logger.info(f"Toplam Yatırım:  ${summary['total_invested']:.2f}")
        logger.info(f"Kalan Bütçe:     ${summary['available_budget']:.2f}")
        logger.info(f"Kullanım Oranı:  {summary['budget_usage_pct']:.1f}%")
        
        if summary['positions_by_symbol']:
            logger.info("\n📊 Symbol Bazlı Pozisyonlar:")
            for symbol, data in summary['positions_by_symbol'].items():
                logger.info(f"  {symbol}:")
                logger.info(f"    Pozisyon Sayısı: {data['position_count']}")
                logger.info(f"    Toplam Miktar:   {data['total_quantity']:.6f}")
                logger.info(f"    Ortalama Maliyet: ${data['average_cost']:.4f}")
                logger.info(f"    Toplam Yatırım:  ${data['total_cost']:.2f}")
        
        logger.info("="*60 + "\n")
    
    def get_statistics(self) -> Dict:
        """Portföy istatistiklerini al"""
        try:
            stats = self.db.get_statistics()
            
            if not stats:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'avg_pnl': 0.0,
                    'avg_win': 0.0,
                    'avg_loss': 0.0
                }
            
            total = stats['total_trades']
            wins = stats['winning_trades']
            losses = stats['losing_trades']
            
            win_rate = (wins / total * 100) if total > 0 else 0.0
            avg_pnl = (stats['total_pnl'] / total) if total > 0 else 0.0
            avg_win = (stats['total_wins'] / wins) if wins > 0 else 0.0
            avg_loss = (stats['total_losses'] / losses) if losses > 0 else 0.0
            
            return {
                'total_trades': total,
                'winning_trades': wins,
                'losing_trades': losses,
                'win_rate': win_rate,
                'total_pnl': stats['total_pnl'],
                'avg_pnl': avg_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss
            }
            
        except Exception as e:
            logger.error(f"❌ İstatistik hatası: {e}")
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0
            }
    
    def log_statistics(self):
        """İstatistikleri logla"""
        stats = self.get_statistics()
        
        logger.info("\n" + "="*60)
        logger.info("📈 PERFORMANS İSTATİSTİKLERİ")
        logger.info("="*60)
        logger.info(f"Toplam Trade:    {stats['total_trades']}")
        logger.info(f"Kazanan:         {stats['winning_trades']}")
        logger.info(f"Kaybeden:        {stats['losing_trades']}")
        logger.info(f"Win Rate:        {stats['win_rate']:.1f}%")
        logger.info(f"Toplam PnL:      ${stats['total_pnl']:.2f}")
        logger.info(f"Ortalama PnL:    ${stats['avg_pnl']:.2f}")
        logger.info(f"Ortalama Kazanç: ${stats['avg_win']:.2f}")
        logger.info(f"Ortalama Kayıp:  ${stats['avg_loss']:.2f}")
        logger.info("="*60 + "\n")
    
    def check_risk_limits(self, symbol: str, required_budget: float) -> tuple[bool, str]:
        """Risk limitlerini kontrol et"""
        # can_open_position ile aynı mantık
        return self.can_open_position(symbol, required_budget)


if __name__ == "__main__":
    """Test modu"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    from database import FibonacciDatabase
    
    db = FibonacciDatabase()
    portfolio = PortfolioManager(db, max_total_budget=1000.0, max_budget_per_coin=100.0)
    
    print("\n" + "="*60)
    print("💼 PORTFOLIO MANAGER TEST")
    print("="*60)
    
    # Portföy durumu
    portfolio.log_portfolio_status()
    
    # İstatistikler
    portfolio.log_statistics()
    
    # Risk kontrolü
    can_open, msg = portfolio.can_open_position('BTCUSDT', 50.0)
    print(f"\nBTCUSDT için 50 USD pozisyon açılabilir mi? {can_open}")
    print(f"Mesaj: {msg}")
