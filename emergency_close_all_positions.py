#!/usr/bin/env python3
"""
🚨 ACİL: TÜM AÇIK POZİSYONLARI KAPAT
Testnet'teki tüm açık pozisyonları market order ile kapatır.
"""

import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_fetcher.binance_fetcher import binance_client
import time

print("="*80)
print("🚨 TÜM AÇIK POZİSYONLARI KAPATMA")
print("="*80)

try:
    # 1. Açık pozisyonları al
    print("\n1️⃣  Açık pozisyonlar kontrol ediliyor...")
    positions = binance_client.futures_position_information()
    
    open_positions = []
    for pos in positions:
        position_amt = float(pos.get('positionAmt', 0))
        if position_amt != 0:
            open_positions.append({
                'symbol': pos['symbol'],
                'side': 'LONG' if position_amt > 0 else 'SHORT',
                'amount': abs(position_amt),
                'unrealized_pnl': float(pos.get('unRealizedProfit', 0))
            })
    
    if not open_positions:
        print("   ✅ Zaten hiç açık pozisyon yok!")
        sys.exit(0)
    
    print(f"\n   📊 {len(open_positions)} açık pozisyon bulundu:")
    total_pnl = 0
    for pos in open_positions:
        emoji = "🟢" if pos['unrealized_pnl'] >= 0 else "🔴"
        print(f"   {emoji} {pos['symbol']:15} {pos['side']:5} - "
              f"Amount: {pos['amount']:.4f} - PnL: ${pos['unrealized_pnl']:+.2f}")
        total_pnl += pos['unrealized_pnl']
    
    print(f"\n   💰 Toplam Unrealized PnL: ${total_pnl:+.2f}")
    
    # 2. Onay al
    print("\n" + "="*80)
    print("⚠️  UYARI: Tüm pozisyonlar MARKET order ile kapatılacak!")
    print("="*80)
    response = input("\nDevam etmek istiyor musunuz? (yes/no): ")
    
    if response.lower() != 'yes':
        print("\n❌ İşlem iptal edildi.")
        sys.exit(0)
    
    # 3. Pozisyonları kapat
    print("\n2️⃣  Pozisyonlar kapatılıyor...\n")
    
    closed_count = 0
    errors = []
    
    for pos in open_positions:
        symbol = pos['symbol']
        side = pos['side']
        amount = pos['amount']
        
        try:
            # Karşıt emir ver (LONG ise SELL, SHORT ise BUY)
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            
            print(f"   Kapatılıyor: {symbol} ({side}) - {amount:.4f} adet...")
            
            order = binance_client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='MARKET',
                quantity=amount,
                reduceOnly=True  # Sadece mevcut pozisyonu kapat
            )
            
            print(f"   ✅ Kapatıldı: {symbol} - Order ID: {order['orderId']}")
            closed_count += 1
            time.sleep(0.5)  # Rate limit
            
        except Exception as e:
            error_msg = f"❌ {symbol} kapatılamadı: {e}"
            print(f"   {error_msg}")
            errors.append(error_msg)
    
    # 4. Özet
    print("\n" + "="*80)
    print("📊 SONUÇ")
    print("="*80)
    print(f"✅ Başarıyla kapatılan: {closed_count}")
    print(f"❌ Hata oluşan: {len(errors)}")
    
    if errors:
        print("\n⚠️  Hatalar:")
        for err in errors:
            print(f"   {err}")
    
    # 5. Son kontrol
    print("\n3️⃣  Son kontrol...")
    time.sleep(2)
    
    positions_after = binance_client.futures_position_information()
    remaining = sum(1 for p in positions_after if float(p.get('positionAmt', 0)) != 0)
    
    if remaining == 0:
        print("   ✅ Tüm pozisyonlar başarıyla kapatıldı!")
    else:
        print(f"   ⚠️  Hala {remaining} açık pozisyon var!")

except Exception as e:
    print(f"\n❌ Kritik hata: {e}")
    import traceback
    traceback.print_exc()
