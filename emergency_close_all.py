#!/usr/bin/env python3
"""
ACİL POZİSYON KAPATMA
Binance Futures'daki tüm açık pozisyonları kapatır
"""

import os
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
TESTNET = os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'

if TESTNET:
    print("⚠️ TESTNET modu - gerçek işlemler yapılmayacak")
else:
    print("🔥 GERÇEK HESAP - Tüm pozisyonlar kapatılacak!")
    confirm = input("Devam etmek için 'EVET' yazın: ")
    if confirm != 'EVET':
        print("İptal edildi")
        exit()

client = Client(API_KEY, SECRET_KEY, testnet=TESTNET)

# Açık pozisyonları al
positions = client.futures_position_information()

print(f"\n📊 Toplam {len(positions)} pozisyon kontrol ediliyor...\n")

closed_count = 0

for pos in positions:
    symbol = pos['symbol']
    position_amt = float(pos['positionAmt'])
    
    if position_amt != 0:  # Açık pozisyon
        side = 'SELL' if position_amt > 0 else 'BUY'  # LONG ise SELL, SHORT ise BUY
        quantity = abs(position_amt)
        
        print(f"🔴 AÇIK POZİSYON: {symbol}")
        print(f"   Miktar: {position_amt}")
        print(f"   Kapatma işlemi: {side} {quantity}")
        
        try:
            # Market emri ile kapat
            order = client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            
            print(f"   ✅ KAPATILDI - OrderID: {order['orderId']}\n")
            closed_count += 1
            
        except Exception as e:
            print(f"   ❌ HATA: {e}\n")

print(f"\n{'='*50}")
print(f"✅ {closed_count} pozisyon kapatıldı")
print(f"{'='*50}\n")
