#!/usr/bin/env python3
"""
Real-time Position Monitor
v10.7 Adaptive Scanner için pozisyon ve performans izleme aracı
"""

import sys
import os
from datetime import datetime
from tabulate import tabulate

# ChimeraBot modüllerini import et
from src.database.models import db_session, OpenPosition, TradeHistory
from src.data_fetcher.binance_fetcher import get_current_price

def get_open_positions_with_pnl():
    """Açık pozisyonları gerçek zamanlı PnL ile göster"""
    db = db_session()
    try:
        positions = db.query(OpenPosition).all()
        
        if not positions:
            return None, None
        
        position_data = []
        total_unrealized_pnl = 0
        
        for pos in positions:
            # Gerçek zamanlı fiyat al
            current_price = get_current_price(pos.symbol)
            
            if current_price is None:
                current_price = pos.entry_price
                pnl_usd = 0
                pnl_percent = 0
            else:
                # PnL hesapla
                if pos.direction == 'LONG':
                    pnl_percent = ((current_price - pos.entry_price) / pos.entry_price) * 100
                else:  # SHORT
                    pnl_percent = ((pos.entry_price - current_price) / pos.entry_price) * 100
                
                # Kaldıraçlı PnL
                pnl_percent_leveraged = pnl_percent * pos.leverage
                
                # USD cinsinden PnL
                position_value = pos.entry_price * pos.amount
                pnl_usd = (position_value * pnl_percent_leveraged) / 100
                
                total_unrealized_pnl += pnl_usd
            
            # SL/TP mesafesi hesapla
            if pos.direction == 'LONG':
                sl_distance = ((pos.entry_price - pos.sl_price) / pos.entry_price) * 100
                tp_distance = ((pos.tp_price - pos.entry_price) / pos.entry_price) * 100
            else:
                sl_distance = ((pos.sl_price - pos.entry_price) / pos.entry_price) * 100
                tp_distance = ((pos.entry_price - pos.tp_price) / pos.entry_price) * 100
            
            # Açılış zamanı düzelt (milisaniye -> saniye)
            open_timestamp = pos.open_time / 1000 if pos.open_time > 1000000000000 else pos.open_time
            open_time = datetime.fromtimestamp(open_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            position_data.append({
                'Symbol': pos.symbol,
                'Direction': pos.direction,
                'Entry': f'${pos.entry_price:.4f}',
                'Current': f'${current_price:.4f}',
                'SL': f'${pos.sl_price:.4f} ({sl_distance:.1f}%)',
                'TP': f'${pos.tp_price:.4f} ({tp_distance:.1f}%)',
                'Amount': f'{pos.amount:.2f}',
                'Leverage': f'{pos.leverage}x',
                'PnL': f'${pnl_usd:.2f}' if pnl_usd >= 0 else f'-${abs(pnl_usd):.2f}',
                'PnL %': f'{pnl_percent_leveraged:.2f}%',
                'Opened': open_time
            })
        
        return position_data, total_unrealized_pnl
    
    finally:
        db_session.remove()


def get_trade_history_summary():
    """Trade history özetini getir"""
    db = db_session()
    try:
        all_trades = db.query(TradeHistory).all()
        
        if not all_trades:
            return None
        
        total_pnl = 0
        win_count = 0
        loss_count = 0
        total_win_pnl = 0
        total_loss_pnl = 0
        
        for trade in all_trades:
            total_pnl += trade.pnl_usd
            
            if trade.pnl_usd > 0:
                win_count += 1
                total_win_pnl += trade.pnl_usd
            else:
                loss_count += 1
                total_loss_pnl += abs(trade.pnl_usd)
        
        total_trades = win_count + loss_count
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        avg_win = total_win_pnl / win_count if win_count > 0 else 0
        avg_loss = total_loss_pnl / loss_count if loss_count > 0 else 0
        
        return {
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'win_count': win_count,
            'loss_count': loss_count,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else float('inf')
        }
    
    finally:
        db_session.remove()


def get_recent_trades(limit=10):
    """Son N trade'i göster"""
    db = db_session()
    try:
        trades = db.query(TradeHistory).order_by(TradeHistory.close_time.desc()).limit(limit).all()
        
        if not trades:
            return None
        
        trade_data = []
        
        for trade in trades:
            # Timestamp düzeltmesi
            open_timestamp = trade.open_time / 1000 if trade.open_time > 1000000000000 else trade.open_time
            close_timestamp = trade.close_time / 1000 if trade.close_time > 1000000000000 else trade.close_time
            
            open_time = datetime.fromtimestamp(open_timestamp).strftime('%Y-%m-%d %H:%M')
            close_time = datetime.fromtimestamp(close_timestamp).strftime('%Y-%m-%d %H:%M')
            
            status = '✅' if trade.pnl_usd > 0 else '❌'
            
            trade_data.append({
                'Status': status,
                'Symbol': trade.symbol,
                'Dir': trade.direction,
                'Entry': f'${trade.entry_price:.4f}',
                'Exit': f'${trade.close_price:.4f}',
                'PnL': f'${trade.pnl_usd:.2f}',
                'PnL %': f'{trade.pnl_percent:.2f}%',
                'Reason': trade.close_reason,
                'Opened': open_time,
                'Closed': close_time
            })
        
        return trade_data
    
    finally:
        db_session.remove()


def main():
    """Ana monitoring fonksiyonu"""
    print("\n" + "="*100)
    print("📊 CHIMERABOT v10.7 - POSITION MONITOR")
    print("="*100)
    
    # Açık Pozisyonlar
    print("\n🔴 AÇIK POZİSYONLAR (Real-time PnL)")
    print("-"*100)
    
    position_data, unrealized_pnl = get_open_positions_with_pnl()
    
    if position_data:
        print(tabulate(position_data, headers='keys', tablefmt='grid'))
        print(f"\n💵 Gerçekleşmemiş Toplam PnL: ${unrealized_pnl:.2f}")
    else:
        print("❌ Hiç açık pozisyon yok")
    
    # Trade Summary
    print("\n" + "="*100)
    print("📈 TRADE İSTATİSTİKLERİ")
    print("-"*100)
    
    summary = get_trade_history_summary()
    
    if summary:
        print(f"📊 Toplam Trade: {summary['total_trades']}")
        print(f"✅ Kazanan: {summary['win_count']} ({summary['win_rate']:.1f}%)")
        print(f"❌ Kaybeden: {summary['loss_count']}")
        print(f"💰 Toplam Gerçekleşen PnL: ${summary['total_pnl']:.2f}")
        print(f"📈 Ortalama Kazanç: ${summary['avg_win']:.2f}")
        print(f"📉 Ortalama Kayıp: ${summary['avg_loss']:.2f}")
        print(f"⚖️  Profit Factor: {summary['profit_factor']:.2f}")
    else:
        print("❌ Hiç trade kaydı yok")
    
    # Son Trade'ler
    print("\n" + "="*100)
    print("📜 SON 10 TRADE")
    print("-"*100)
    
    recent_trades = get_recent_trades(10)
    
    if recent_trades:
        print(tabulate(recent_trades, headers='keys', tablefmt='grid'))
    else:
        print("❌ Hiç trade kaydı yok")
    
    print("\n" + "="*100)
    print(f"🕒 Son Güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Monitor kapatıldı")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
