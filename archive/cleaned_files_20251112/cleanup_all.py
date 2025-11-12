#!/usr/bin/env python3
"""
Full System Cleanup Script
- Alpha Cache (DB)
- Open Positions (DB)
- Trade History (DB)
- Binance Testnet Positions
- Log files
"""

import sys
import os
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from src.database.models import db_session, OpenPosition, TradeHistory, AlphaCache
from src.data_fetcher.binance_fetcher import binance_client
from src import config

print("\n" + "="*80)
print("🧹 FULL SYSTEM CLEANUP")
print("="*80)

# 1. Database Cleanup
print("\n📊 DATABASE CLEANUP:")
print("─"*80)

db = db_session()
try:
    # Alpha Cache
    alpha_count = db.query(AlphaCache).count()
    if alpha_count > 0:
        db.query(AlphaCache).delete()
        print(f"   ✅ AlphaCache temizlendi: {alpha_count} kayıt silindi")
    else:
        print(f"   ℹ️  AlphaCache zaten boş")
    
    # Open Positions
    open_count = db.query(OpenPosition).count()
    if open_count > 0:
        positions = db.query(OpenPosition).all()
        for pos in positions:
            print(f"      - {pos.symbol} {pos.direction} @ ${pos.entry_price:.2f}")
        db.query(OpenPosition).delete()
        print(f"   ✅ OpenPosition temizlendi: {open_count} kayıt silindi")
    else:
        print(f"   ℹ️  OpenPosition zaten boş")
    
    # Trade History
    history_count = db.query(TradeHistory).count()
    if history_count > 0:
        db.query(TradeHistory).delete()
        print(f"   ✅ TradeHistory temizlendi: {history_count} kayıt silindi")
    else:
        print(f"   ℹ️  TradeHistory zaten boş")
    
    db.commit()
    print(f"\n   ✅ Database commit başarılı")
    
except Exception as e:
    db.rollback()
    print(f"\n   ❌ Database hatası: {e}")
finally:
    db_session.remove()

# 2. Binance Testnet Cleanup
print("\n🔴 BINANCE TESTNET CLEANUP:")
print("─"*80)

if config.BINANCE_TESTNET:
    try:
        # Tüm açık pozisyonları al
        positions = binance_client.futures_position_information()
        
        closed_count = 0
        for pos in positions:
            position_amt = float(pos['positionAmt'])
            if position_amt != 0:  # Açık pozisyon varsa
                symbol = pos['symbol']
                side = 'SELL' if position_amt > 0 else 'BUY'
                qty = abs(position_amt)
                
                print(f"   🔴 {symbol} kapatılıyor... ({side} {qty})")
                
                try:
                    # Market emri ile kapat
                    order = binance_client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='MARKET',
                        quantity=qty,
                        reduceOnly=True
                    )
                    print(f"      ✅ Kapatıldı! Order ID: {order['orderId']}")
                    closed_count += 1
                except Exception as order_error:
                    print(f"      ❌ Kapatma hatası: {order_error}")
        
        if closed_count > 0:
            print(f"\n   ✅ Toplam {closed_count} pozisyon kapatıldı")
        else:
            print(f"   ℹ️  Binance'de açık pozisyon yok")
        
        # Güncel bakiye
        account = binance_client.futures_account()
        balance = float(account['totalWalletBalance'])
        print(f"\n   💰 Testnet Balance: ${balance:,.2f} USDT")
        
    except Exception as e:
        print(f"   ❌ Binance hatası: {e}")
else:
    print(f"   ⚠️  TESTNET modu kapalı, Binance cleanup atlanıyor")

# 3. Log Cleanup (Optional)
print("\n📝 LOG FILES:")
print("─"*80)

log_file = "logs/chimerabot.log"
if os.path.exists(log_file):
    file_size = os.path.getsize(log_file)
    print(f"   📄 {log_file}: {file_size:,} bytes")
    
    choice = input("   🗑️  Log dosyasını temizle? (y/N): ").strip().lower()
    if choice == 'y':
        with open(log_file, 'w') as f:
            f.write("")
        print(f"   ✅ Log dosyası temizlendi")
    else:
        print(f"   ℹ️  Log dosyası korundu")
else:
    print(f"   ℹ️  Log dosyası bulunamadı")

# 4. Backtest Cache
print("\n💾 BACKTEST CACHE:")
print("─"*80)

cache_dir = "data/backtest_cache"
if os.path.exists(cache_dir):
    cache_files = os.listdir(cache_dir)
    if cache_files:
        print(f"   📁 {len(cache_files)} cache dosyası bulundu")
        
        choice = input("   🗑️  Backtest cache'i temizle? (y/N): ").strip().lower()
        if choice == 'y':
            for file in cache_files:
                file_path = os.path.join(cache_dir, file)
                os.remove(file_path)
            print(f"   ✅ {len(cache_files)} cache dosyası silindi")
        else:
            print(f"   ℹ️  Cache dosyaları korundu")
    else:
        print(f"   ℹ️  Cache dizini zaten boş")
else:
    print(f"   ℹ️  Cache dizini bulunamadı")

# Final Summary
print("\n" + "="*80)
print("✅ CLEANUP TAMAMLANDI")
print("="*80)

print(f"""
📊 Temizlenen Veriler:
   - Database: AlphaCache, OpenPosition, TradeHistory
   - Binance Testnet: Tüm açık pozisyonlar kapatıldı
   - Log: {'Temizlendi' if choice == 'y' else 'Korundu'}
   - Backtest Cache: {'Temizlendi' if choice == 'y' else 'Korundu'}

🚀 Sistem temiz durumda, bot başlatmaya hazır!
""")

print("="*80 + "\n")
