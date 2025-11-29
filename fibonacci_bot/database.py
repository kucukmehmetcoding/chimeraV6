#!/usr/bin/env python3
"""
Fibonacci Bot - Database Manager
SQLite veritabanı yönetimi
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional
import os

logger = logging.getLogger('fibonacci_bot.database')


class FibonacciDatabase:
    """Fibonacci Bot için SQLite veritabanı yöneticisi"""
    
    def __init__(self, db_path: str = "data/fibonacci_bot.db"):
        self.db_path = db_path
        
        # Data klasörünü oluştur
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Veritabanı ve tabloları oluştur"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Dict-like access
        
        cursor = self.conn.cursor()
        
        # Pozisyonlar tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_level TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity REAL NOT NULL,
                spent_usd REAL NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'OPEN',
                exit_price REAL,
                exit_timestamp TEXT,
                pnl_usd REAL,
                pnl_percent REAL
            )
        """)
        
        # Fibonacci seviyeleri tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fibonacci_levels (
                symbol TEXT PRIMARY KEY,
                swing_high REAL NOT NULL,
                swing_low REAL NOT NULL,
                swing_high_date TEXT,
                swing_low_date TEXT,
                level_618 REAL NOT NULL,
                level_786 REAL NOT NULL,
                level_1000 REAL NOT NULL,
                calculated_at TEXT NOT NULL,
                adx REAL,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Alım seviyeleri durumu tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS level_status (
                symbol TEXT NOT NULL,
                level TEXT NOT NULL,
                filled INTEGER DEFAULT 0,
                filled_at TEXT,
                PRIMARY KEY (symbol, level)
            )
        """)
        
        # Portföy özeti tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_summary (
                symbol TEXT PRIMARY KEY,
                total_quantity REAL DEFAULT 0,
                total_spent REAL DEFAULT 0,
                avg_cost REAL DEFAULT 0,
                current_value REAL DEFAULT 0,
                unrealized_pnl REAL DEFAULT 0,
                unrealized_pnl_percent REAL DEFAULT 0,
                last_updated TEXT
            )
        """)
        
        self.conn.commit()
        logger.info(f"✅ Database initialized: {self.db_path}")
    
    # ==================== FIBONACCI LEVELS ====================
    
    def save_fibonacci_levels(self, symbol: str, levels: Dict):
        """Fibonacci seviyelerini kaydet"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO fibonacci_levels 
            (symbol, swing_high, swing_low, swing_high_date, swing_low_date,
             level_618, level_786, level_1000, calculated_at, adx, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            symbol,
            levels['swing_high'],
            levels['swing_low'],
            levels.get('swing_high_date', ''),
            levels.get('swing_low_date', ''),
            levels['level_618'],
            levels['level_786'],
            levels['level_1000'],
            datetime.now().isoformat(),
            levels.get('adx', 0)
        ))
        
        self.conn.commit()
        logger.info(f"💾 Fibonacci levels saved: {symbol}")
    
    def get_fibonacci_levels(self, symbol: str) -> Optional[Dict]:
        """Bir coin için Fibonacci seviyelerini getir"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM fibonacci_levels WHERE symbol = ? AND is_active = 1
        """, (symbol,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_all_active_fibonacci_levels(self) -> List[Dict]:
        """Tüm aktif Fibonacci seviyelerini getir"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM fibonacci_levels WHERE is_active = 1
            ORDER BY calculated_at DESC
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== POSITIONS ====================
    
    def add_position(self, symbol: str, level: str, entry_price: float, 
                     quantity: float, spent_usd: float):
        """Yeni pozisyon ekle"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO positions 
            (symbol, entry_level, entry_price, quantity, spent_usd, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN')
        """, (symbol, level, entry_price, quantity, spent_usd, datetime.now().isoformat()))
        
        self.conn.commit()
        
        # Level status güncelle
        self.mark_level_filled(symbol, level)
        
        # Portfolio özeti güncelle
        self.update_portfolio_summary(symbol)
        
        logger.info(f"✅ Position added: {symbol} @ {level} - {quantity} coins @ ${entry_price}")
        
        return cursor.lastrowid
    
    def get_open_positions(self, symbol: str = None) -> List[Dict]:
        """Açık pozisyonları getir"""
        cursor = self.conn.cursor()
        
        if symbol:
            cursor.execute("""
                SELECT * FROM positions WHERE symbol = ? AND status = 'OPEN'
                ORDER BY timestamp ASC
            """, (symbol,))
        else:
            cursor.execute("""
                SELECT * FROM positions WHERE status = 'OPEN'
                ORDER BY timestamp ASC
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close_position(self, position_id: int, exit_price: float):
        """Pozisyon kapat"""
        cursor = self.conn.cursor()
        
        # Pozisyon bilgilerini al
        cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
        pos = cursor.fetchone()
        
        if not pos:
            logger.error(f"❌ Position not found: {position_id}")
            return False
        
        # PnL hesapla
        entry_price = pos['entry_price']
        quantity = pos['quantity']
        spent = pos['spent_usd']
        
        exit_value = exit_price * quantity
        pnl_usd = exit_value - spent
        pnl_percent = (pnl_usd / spent) * 100
        
        # Güncelle
        cursor.execute("""
            UPDATE positions 
            SET status = 'CLOSED',
                exit_price = ?,
                exit_timestamp = ?,
                pnl_usd = ?,
                pnl_percent = ?
            WHERE id = ?
        """, (exit_price, datetime.now().isoformat(), pnl_usd, pnl_percent, position_id))
        
        self.conn.commit()
        
        # Portfolio özeti güncelle
        self.update_portfolio_summary(pos['symbol'])
        
        logger.info(f"✅ Position closed: ID {position_id} - PnL: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)")
        
        return True
    
    # ==================== LEVEL STATUS ====================
    
    def mark_level_filled(self, symbol: str, level: str):
        """Seviye dolduruldu olarak işaretle"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO level_status (symbol, level, filled, filled_at)
            VALUES (?, ?, 1, ?)
        """, (symbol, level, datetime.now().isoformat()))
        
        self.conn.commit()
    
    def is_level_filled(self, symbol: str, level: str) -> bool:
        """Seviye daha önce doldurulmuş mu?"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT filled FROM level_status WHERE symbol = ? AND level = ?
        """, (symbol, level))
        
        row = cursor.fetchone()
        return row and row['filled'] == 1
    
    def reset_level_status(self, symbol: str):
        """Bir coin için tüm seviyeleri sıfırla"""
        cursor = self.conn.cursor()
        
        cursor.execute("DELETE FROM level_status WHERE symbol = ?", (symbol,))
        self.conn.commit()
        
        logger.info(f"🔄 Level status reset: {symbol}")
    
    # ==================== PORTFOLIO SUMMARY ====================
    
    def update_portfolio_summary(self, symbol: str):
        """Portföy özetini güncelle"""
        cursor = self.conn.cursor()
        
        # Açık pozisyonları topla
        cursor.execute("""
            SELECT 
                SUM(quantity) as total_quantity,
                SUM(spent_usd) as total_spent
            FROM positions
            WHERE symbol = ? AND status = 'OPEN'
        """, (symbol,))
        
        row = cursor.fetchone()
        
        total_quantity = row['total_quantity'] or 0
        total_spent = row['total_spent'] or 0
        avg_cost = (total_spent / total_quantity) if total_quantity > 0 else 0
        
        cursor.execute("""
            INSERT OR REPLACE INTO portfolio_summary 
            (symbol, total_quantity, total_spent, avg_cost, last_updated)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol, total_quantity, total_spent, avg_cost, datetime.now().isoformat()))
        
        self.conn.commit()
    
    def get_portfolio_summary(self, symbol: str = None) -> List[Dict]:
        """Portföy özetini getir"""
        cursor = self.conn.cursor()
        
        if symbol:
            cursor.execute("""
                SELECT * FROM portfolio_summary WHERE symbol = ?
            """, (symbol,))
        else:
            cursor.execute("""
                SELECT * FROM portfolio_summary WHERE total_quantity > 0
                ORDER BY total_spent DESC
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_portfolio_current_values(self, symbol: str, current_price: float):
        """Güncel fiyata göre portföy değerini güncelle"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT total_quantity, total_spent, avg_cost
            FROM portfolio_summary WHERE symbol = ?
        """, (symbol,))
        
        row = cursor.fetchone()
        if not row or row['total_quantity'] == 0:
            return
        
        current_value = row['total_quantity'] * current_price
        unrealized_pnl = current_value - row['total_spent']
        unrealized_pnl_percent = (unrealized_pnl / row['total_spent']) * 100 if row['total_spent'] > 0 else 0
        
        cursor.execute("""
            UPDATE portfolio_summary
            SET current_value = ?,
                unrealized_pnl = ?,
                unrealized_pnl_percent = ?,
                last_updated = ?
            WHERE symbol = ?
        """, (current_value, unrealized_pnl, unrealized_pnl_percent, 
              datetime.now().isoformat(), symbol))
        
        self.conn.commit()
    
    # ==================== STATISTICS ====================
    
    def get_total_stats(self) -> Dict:
        """Toplam istatistikler"""
        cursor = self.conn.cursor()
        
        # Açık pozisyonlar
        cursor.execute("""
            SELECT COUNT(*) as count, SUM(spent_usd) as total_invested
            FROM positions WHERE status = 'OPEN'
        """)
        open_stats = dict(cursor.fetchone())
        
        # Kapalı pozisyonlar
        cursor.execute("""
            SELECT 
                COUNT(*) as count,
                SUM(pnl_usd) as total_pnl,
                AVG(pnl_percent) as avg_pnl_percent
            FROM positions WHERE status = 'CLOSED'
        """)
        closed_stats = dict(cursor.fetchone())
        
        # Portföy özeti
        cursor.execute("""
            SELECT 
                SUM(total_spent) as total_invested,
                SUM(current_value) as total_value,
                SUM(unrealized_pnl) as total_unrealized_pnl
            FROM portfolio_summary
        """)
        portfolio_stats = dict(cursor.fetchone())
        
        return {
            'open_positions': open_stats['count'] or 0,
            'open_invested': open_stats['total_invested'] or 0,
            'closed_positions': closed_stats['count'] or 0,
            'realized_pnl': closed_stats['total_pnl'] or 0,
            'avg_pnl_percent': closed_stats['avg_pnl_percent'] or 0,
            'total_invested': portfolio_stats['total_invested'] or 0,
            'total_value': portfolio_stats['total_value'] or 0,
            'unrealized_pnl': portfolio_stats['total_unrealized_pnl'] or 0
        }
    
    def get_statistics(self) -> Dict:
        """Performans istatistikleri (portfolio_manager için)"""
        cursor = self.conn.cursor()
        
        # Kapalı pozisyonlar istatistiği
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(pnl_usd) as total_pnl,
                SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END) as total_wins,
                SUM(CASE WHEN pnl_usd <= 0 THEN pnl_usd ELSE 0 END) as total_losses
            FROM positions WHERE status = 'CLOSED'
        """)
        
        stats = dict(cursor.fetchone())
        
        return {
            'total_trades': stats['total_trades'] or 0,
            'winning_trades': stats['winning_trades'] or 0,
            'losing_trades': stats['losing_trades'] or 0,
            'total_pnl': stats['total_pnl'] or 0.0,
            'total_wins': stats['total_wins'] or 0.0,
            'total_losses': stats['total_losses'] or 0.0
        }
    
    def close(self):
        """Veritabanı bağlantısını kapat"""
        if self.conn:
            self.conn.close()
            logger.info("📴 Database connection closed")
