#!/usr/bin/env python3
"""
Live Position Monitor - Minimal version
Gerçek zamanlı pozisyon takibi için basit script
"""

import time
import sys
import os
from datetime import datetime

from src.database.models import db_session, OpenPosition, TradeHistory
from src.data_fetcher.binance_fetcher import get_current_price

def format_price(price):
    """Fiyat hassasiyetini otomatik belirle"""
    if price < 0.001:
        return f"${price:.8f}"  # Çok küçük: 8 desimal
    elif price < 0.01:
        return f"${price:.6f}"  # Küçük: 6 desimal
    elif price < 1.0:
        return f"${price:.4f}"  # Normal: 4 desimal
    else:
        return f"${price:.2f}"  # Büyük: 2 desimal

def clear_screen():
    """Ekranı gerçekten temizle - OS bazlı"""
    os.system('clear' if os.name == 'posix' else 'cls')

def monitor_loop(interval=5):
    """Sürekli monitoring döngüsü"""
    
    while True:
        clear_screen()
        
        # String buffer oluştur (tüm output tek seferde yazılacak)
        output = []
        output.append("="*80)
        output.append(f"📊 CHIMERABOT LIVE MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("="*80)
        
        db = db_session()
        try:
            # AÇIK POZİSYONLAR
            positions = db.query(OpenPosition).all()
            
            output.append(f"\n🔴 AÇIK POZİSYONLAR: {len(positions)}")
            output.append("-"*80)
            
            total_unrealized = 0
            
            if positions:
                for idx, pos in enumerate(positions, 1):
                    current_price = get_current_price(pos.symbol)
                    
                    if current_price:
                        # PnL hesapla
                        if pos.direction == 'LONG':
                            pnl_pct = ((current_price - pos.entry_price) / pos.entry_price) * 100
                            pnl_usd = (current_price - pos.entry_price) * pos.amount * pos.leverage
                        else:
                            pnl_pct = ((pos.entry_price - current_price) / pos.entry_price) * 100
                            pnl_usd = (pos.entry_price - current_price) * pos.amount * pos.leverage
                        
                        total_unrealized += pnl_usd
                        
                        pnl_color = "🟢" if pnl_usd >= 0 else "🔴"
                        
                        output.append(f"\n{idx}. {pos.symbol} - {pos.direction} {pos.leverage}x")
                        output.append(f"   Entry: {format_price(pos.entry_price)} → Current: {format_price(current_price)}")
                        output.append(f"   {pnl_color} PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%)")
                        output.append(f"   SL: {format_price(pos.sl_price)} | TP: {format_price(pos.tp_price)}")
                
                output.append(f"\n💵 Toplam Gerçekleşmemiş PnL: ${total_unrealized:.2f}")
            else:
                output.append("❌ Açık pozisyon yok")
            
            # TRADE İSTATİSTİKLERİ
            all_trades = db.query(TradeHistory).all()
            
            if all_trades:
                total_pnl = sum(t.pnl_usd for t in all_trades)
                wins = len([t for t in all_trades if t.pnl_usd > 0])
                losses = len([t for t in all_trades if t.pnl_usd <= 0])
                total = wins + losses
                win_rate = (wins / total * 100) if total > 0 else 0
                
                output.append(f"\n📈 GENEL İSTATİSTİKLER")
                output.append("-"*80)
                output.append(f"💰 Gerçekleşen Toplam PnL: ${total_pnl:.2f}")
                output.append(f"📊 Toplam Trade: {total} (✅ {wins} | ❌ {losses})")
                output.append(f"🎯 Win Rate: {win_rate:.1f}%")
                
                # NET TOPLAM
                net_total = total_pnl + total_unrealized
                output.append(f"\n💎 NET TOPLAM PnL: ${net_total:.2f}")
            
        finally:
            db_session.remove()
        
        output.append("\n" + "="*80)
        output.append(f"⏱️  Sonraki güncelleme {interval} saniye sonra... (Ctrl+C ile çıkış)")
        output.append("="*80)
        
        # Tek seferde tüm output'u yaz
        print("\n".join(output), flush=True)
        
        time.sleep(interval)


if __name__ == "__main__":
    try:
        print("🚀 Live Monitor başlatılıyor...")
        print("📊 Pozisyonlarınız her 5 saniyede bir güncellenecek")
        print("\n⌨️  Çıkmak için Ctrl+C'ye basın\n")
        time.sleep(2)
        monitor_loop(interval=5)
    except KeyboardInterrupt:
        print("\n\n👋 Monitor durduruldu")
        sys.exit(0)
