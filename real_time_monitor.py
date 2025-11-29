#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-Time Live Test Monitor
Live test'i gerçek zamanlı izleme arayüzü
"""

import os
import sys
import sqlite3
import pandas as pd
import time
from datetime import datetime, timedelta
from pathlib import Path


def clear_screen():
    """Platform bağımsız ekran temizleme"""
    os.system('clear' if os.name != 'nt' else 'cls')


def get_db_connection():
    """Database bağlantısı"""
    db_path = Path('data/live_test_database.db')
    
    if not db_path.exists():
        print(f"❌ Database bulunamadı: {db_path}")
        print("💡 Önce live test başlatın: python3 run_live_test.py")
        return None
    
    return sqlite3.connect(str(db_path))


def format_duration(seconds):
    """Süreyi formatla"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m"
    else:
        hours = int(seconds/3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours}h {mins}m"


def format_pnl(pnl):
    """PnL formatla (renkli)"""
    if pnl > 0:
        return f"🟢 +${pnl:.2f}"
    elif pnl < 0:
        return f"🔴 ${pnl:.2f}"
    else:
        return f"⚪ ${pnl:.2f}"


def print_header():
    """Başlık yazdır"""
    print("╔" + "═"*78 + "╗")
    print("║" + " "*25 + "📊 LIVE TEST MONITOR" + " "*33 + "║")
    print("╚" + "═"*78 + "╝")


def print_performance_summary(conn):
    """Performance özeti"""
    try:
        perf_df = pd.read_sql_query('''
            SELECT * FROM test_performance 
            ORDER BY timestamp DESC LIMIT 1
        ''', conn)
        
        if perf_df.empty:
            print("\n⚠️  Henüz performans verisi yok\n")
            return
        
        perf = perf_df.iloc[0]
        
        print("\n💰 PORTFOLIO SUMMARY")
        print("─"*80)
        
        # Balance & PnL
        balance = perf['final_balance']
        initial = 1000  # Config'den al
        total_pnl = balance - initial
        total_pnl_pct = (total_pnl / initial) * 100
        
        print(f"  Balance:           ${balance:,.2f}")
        print(f"  Initial:           ${initial:,.2f}")
        print(f"  Total PnL:         {format_pnl(total_pnl)} ({total_pnl_pct:+.2f}%)")
        
        # Positions
        open_pos = perf.get('open_positions', 0)
        print(f"  Open Positions:    {open_pos}")
        
        # Win Rate
        total_trades = perf.get('total_trades', 0)
        winning_trades = perf.get('winning_trades', 0)
        
        if total_trades > 0:
            win_rate = (winning_trades / total_trades) * 100
            print(f"  Win Rate:          {win_rate:.1f}% ({winning_trades}/{total_trades})")
        
        # Max Drawdown
        max_dd = perf.get('max_drawdown_pct', 0)
        if max_dd:
            print(f"  Max Drawdown:      {max_dd:.2f}%")
        
        # Profit Factor
        pf = perf.get('profit_factor', 0)
        if pf:
            print(f"  Profit Factor:     {pf:.2f}")
        
    except Exception as e:
        print(f"\n⚠️  Performance verisi alınamadı: {e}\n")


def print_open_positions(conn):
    """Açık pozisyonlar"""
    try:
        positions_df = pd.read_sql_query('''
            SELECT * FROM test_trades 
            WHERE exit_price IS NULL
            ORDER BY entry_time DESC
        ''', conn)
        
        if positions_df.empty:
            print("\n🔓 OPEN POSITIONS: None")
            return
        
        print(f"\n🔓 OPEN POSITIONS ({len(positions_df)})")
        print("─"*80)
        
        for _, pos in positions_df.iterrows():
            symbol = pos['symbol']
            direction = pos['direction']
            entry_price = pos['entry_price']
            entry_time = pos['entry_time']
            
            # Stop loss & Take profit
            sl = pos.get('stop_loss', 0)
            tp1 = pos.get('take_profit_1', 0)
            
            # Duration
            if isinstance(entry_time, str):
                entry_dt = datetime.fromisoformat(entry_time)
                duration = (datetime.now() - entry_dt).total_seconds()
                duration_str = format_duration(duration)
            else:
                duration_str = "N/A"
            
            # Position size
            position_size = pos.get('position_size', 0)
            
            print(f"  {symbol:12} {direction:4} | Entry: ${entry_price:.4f} | "
                  f"Size: {position_size:.2f} | Duration: {duration_str}")
            print(f"               SL: ${sl:.4f} | TP1: ${tp1:.4f}")
        
    except Exception as e:
        print(f"\n⚠️  Pozisyon verisi alınamadı: {e}\n")


def print_recent_trades(conn, limit=10):
    """Son işlemler"""
    try:
        trades_df = pd.read_sql_query(f'''
            SELECT * FROM test_trades 
            WHERE exit_price IS NOT NULL
            ORDER BY exit_time DESC LIMIT {limit}
        ''', conn)
        
        if trades_df.empty:
            print("\n📜 RECENT TRADES: None")
            return
        
        print(f"\n📜 RECENT TRADES (Last {min(limit, len(trades_df))})")
        print("─"*80)
        
        for _, trade in trades_df.iterrows():
            symbol = trade['symbol']
            direction = trade['direction']
            entry_price = trade['entry_price']
            exit_price = trade['exit_price']
            pnl = trade.get('pnl', 0)
            pnl_pct = trade.get('pnl_pct', 0)
            exit_reason = trade.get('exit_reason', 'Unknown')
            
            # PnL emoji
            pnl_emoji = "🟢" if pnl > 0 else "🔴"
            
            print(f"  {pnl_emoji} {symbol:12} {direction:4} | "
                  f"Entry: ${entry_price:.4f} → Exit: ${exit_price:.4f} | "
                  f"PnL: {pnl:+.2f} ({pnl_pct:+.2f}%) | {exit_reason}")
        
    except Exception as e:
        print(f"\n⚠️  Trade verisi alınamadı: {e}\n")


def print_daily_stats(conn):
    """Günlük istatistikler"""
    try:
        stats_df = pd.read_sql_query('''
            SELECT * FROM test_daily_stats 
            ORDER BY date DESC LIMIT 1
        ''', conn)
        
        if stats_df.empty:
            return
        
        stats = stats_df.iloc[0]
        
        print("\n📅 TODAY'S STATS")
        print("─"*80)
        
        trades_today = stats.get('trades_count', 0)
        pnl_today = stats.get('total_pnl', 0)
        
        print(f"  Trades:            {trades_today}")
        print(f"  PnL:               {format_pnl(pnl_today)}")
        
    except Exception as e:
        pass  # Daily stats optional


def monitor_live_test(refresh_interval=30):
    """Live test'i gerçek zamanlı izle"""
    
    print("\n🚀 Real-Time Monitor başlatılıyor...")
    print(f"⏱️  Refresh interval: {refresh_interval} seconds")
    print("⚠️  Ctrl+C ile durdurun\n")
    
    time.sleep(2)
    
    iteration = 0
    
    try:
        while True:
            # Ekranı temizle
            clear_screen()
            
            # Header
            print_header()
            print(f"\n⏰ Son Güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🔄 Iteration: {iteration + 1}")
            
            # Database bağlantısı
            conn = get_db_connection()
            
            if conn is None:
                print("\n❌ Database bağlantısı kurulamadı!")
                print("Bekleniyor...")
                time.sleep(refresh_interval)
                continue
            
            try:
                # Performance özeti
                print_performance_summary(conn)
                
                # Açık pozisyonlar
                print_open_positions(conn)
                
                # Son işlemler
                print_recent_trades(conn, limit=5)
                
                # Günlük stats (optional)
                print_daily_stats(conn)
                
            finally:
                conn.close()
            
            # Footer
            print("\n" + "─"*80)
            print(f"⏱️  Sonraki güncelleme: {refresh_interval} saniye | "
                  f"⏹️  Durdurmak için: Ctrl+C")
            print("═"*80)
            
            # Bekle
            time.sleep(refresh_interval)
            iteration += 1
            
    except KeyboardInterrupt:
        print("\n\n" + "╔" + "═"*78 + "╗")
        print("║" + " "*28 + "⏹️  MONITOR DURDURULDU" + " "*29 + "║")
        print("╚" + "═"*78 + "╝\n")
        print("✅ Monitor kapatıldı\n")
    
    except Exception as e:
        print(f"\n❌ Monitor hatası: {e}\n")
        import traceback
        traceback.print_exc()


def main():
    """Ana fonksiyon"""
    print("\n╔" + "═"*78 + "╗")
    print("║" + " "*25 + "📊 LIVE TEST MONITOR" + " "*33 + "║")
    print("╚" + "═"*78 + "╝\n")
    
    # Argüman kontrolü
    if len(sys.argv) > 1:
        try:
            refresh_interval = int(sys.argv[1])
            if refresh_interval < 5:
                print("⚠️  Minimum refresh interval: 5 saniye")
                refresh_interval = 5
        except ValueError:
            print("⚠️  Geçersiz interval, varsayılan (30s) kullanılıyor")
            refresh_interval = 30
    else:
        refresh_interval = 30
    
    print(f"⚙️  Refresh Interval: {refresh_interval} seconds")
    print(f"📁 Database: data/live_test_database.db")
    print(f"⏹️  Durdurmak için: Ctrl+C\n")
    
    # Monitor başlat
    monitor_live_test(refresh_interval)


if __name__ == "__main__":
    main()
