#!/usr/bin/env python3
"""KMNOUSDT için eksik SL emrini yerleştir"""

import sys
sys.path.insert(0, '/Users/macbook/Desktop/ChimeraBot')

from src.trade_manager.executor import BinanceFuturesExecutor
from src.config import BINANCE_API_KEY, BINANCE_SECRET_KEY

executor = BinanceFuturesExecutor(api_key=BINANCE_API_KEY, api_secret=BINANCE_SECRET_KEY)

print("=" * 80)
print("KMNOUSDT EKSİK SL EMRİ KONTROLÜ VE DÜZELTME")
print("=" * 80)

# Pozisyon bilgisini al
all_positions = executor.get_open_positions_from_binance()
pos_info = None

for pos in all_positions:
    if pos['symbol'] == 'KMNOUSDT' and float(pos['positionAmt']) != 0:
        pos_info = pos
        break

if pos_info:
    amount = float(pos_info['positionAmt'])
    entry = float(pos_info['entryPrice'])
    
    print(f"\n📊 KMNOUSDT Pozisyon:")
    print(f"  Miktar: {amount}")
    print(f"  Giriş: {entry}")
    print(f"  Yön: {'LONG' if amount > 0 else 'SHORT'}")
    
    # Açık emirler
    orders = executor.get_open_orders('KMNOUSDT')
    print(f"\n📝 Açık Emirler ({len(orders)} adet):")
    
    has_sl = False
    has_tp = False
    
    for order in orders:
        order_type = order['type']
        stop_price = float(order.get('stopPrice', 0))
        qty = float(order['origQty'])
        
        print(f"  - {order_type} @ {stop_price} (Miktar: {qty})")
        
        if 'STOP_MARKET' in order_type or 'STOP_LOSS' in order_type:
            has_sl = True
        if 'TAKE_PROFIT' in order_type:
            has_tp = True
    
    print(f"\n🔍 Emir Durumu:")
    print(f"  SL Var mı? {has_sl}")
    print(f"  TP Var mı? {has_tp}")
    
    if not has_sl:
        print(f"\n❌ UYARI: SL emri YOK!")
        print(f"  Bu pozisyon korumasız - manuel olarak SL koymalısın!")
        print(f"\n💡 Önerilen SL: {entry * 0.95:.5f} (Entry'den %5 aşağı)")
        print(f"  Binance'de manuel olarak STOP_MARKET emri koy.")
    
    if not has_tp:
        print(f"\n⚠️ UYARI: TP emri eksik!")

else:
    print("❌ KMNOUSDT pozisyonu bulunamadı!")

print("\n" + "=" * 80)
