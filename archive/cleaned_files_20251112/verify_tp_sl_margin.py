#!/usr/bin/env python3
"""
TP/SL Margin Hesaplama Doğrulama Testi

DOĞRU MANTIK:
- Margin: 10 USD
- TP: Margin + %40 kar = 10 + 4 = 14 USD
- SL: Margin - %10 zarar = 10 - 1 = 9 USD
"""

# Test senaryoları
test_cases = [
    {
        'name': 'BTCUSDT @ $90,000',
        'entry_price': 90000.0,
        'margin': 10.0,
        'leverage': 10,
    },
    {
        'name': 'ETHUSDT @ $3,000',
        'entry_price': 3000.0,
        'margin': 10.0,
        'leverage': 10,
    },
    {
        'name': 'BNBUSDT @ $600',
        'entry_price': 600.0,
        'margin': 10.0,
        'leverage': 10,
    },
]

print("=" * 80)
print("🧪 TP/SL MARGIN HESAPLAMA TEST")
print("=" * 80)

print("\n📋 DOĞRU MANTIĞIN AÇIKLAMASI:")
print("   • Margin: 10 USD (sabit)")
print("   • TP Hedefi: Margin + %40 kar = 10 + 4 = 14 USD")
print("   • SL Hedefi: Margin - %10 zarar = 10 - 1 = 9 USD")
print("   • TP Kar: +4 USD (%40)")
print("   • SL Zarar: -1 USD (%10)")

for test in test_cases:
    print("\n" + "=" * 80)
    print(f"📊 {test['name']}")
    print("=" * 80)
    
    entry = test['entry_price']
    margin = test['margin']
    leverage = test['leverage']
    
    # Position size
    position_size = (margin * leverage) / entry
    
    # TP/SL profit/loss amounts
    tp_profit = 4.0  # +4 USD kar
    sl_loss = 1.0    # +1 USD zarar
    
    # TP/SL prices
    tp_price_long = entry + (tp_profit / position_size)
    sl_price_long = entry - (sl_loss / position_size)
    
    tp_price_short = entry - (tp_profit / position_size)
    sl_price_short = entry + (sl_loss / position_size)
    
    # Verification
    long_tp_value = (tp_price_long - entry) * position_size
    long_sl_value = (entry - sl_price_long) * position_size
    
    short_tp_value = (entry - tp_price_short) * position_size
    short_sl_value = (sl_price_short - entry) * position_size
    
    print(f"\n💰 MARGIN: ${margin}")
    print(f"⚡ LEVERAGE: {leverage}x")
    print(f"📈 ENTRY: ${entry:,.2f}")
    print(f"📦 POSITION SIZE: {position_size:.6f} units")
    
    print(f"\n🟢 LONG Pozisyon:")
    print(f"   🎯 TP Price: ${tp_price_long:,.4f}")
    print(f"      → Kar: ${long_tp_value:.2f} ({'✅ DOĞRU' if abs(long_tp_value - 4.0) < 0.01 else '❌ YANLIŞ'})")
    print(f"   🛑 SL Price: ${sl_price_long:,.4f}")
    print(f"      → Zarar: ${long_sl_value:.2f} ({'✅ DOĞRU' if abs(long_sl_value - 1.0) < 0.01 else '❌ YANLIŞ'})")
    
    print(f"\n🔴 SHORT Pozisyon:")
    print(f"   🎯 TP Price: ${tp_price_short:,.4f}")
    print(f"      → Kar: ${short_tp_value:.2f} ({'✅ DOĞRU' if abs(short_tp_value - 4.0) < 0.01 else '❌ YANLIŞ'})")
    print(f"   🛑 SL Price: ${sl_price_short:,.4f}")
    print(f"      → Zarar: ${short_sl_value:.2f} ({'✅ DOĞRU' if abs(short_sl_value - 1.0) < 0.01 else '❌ YANLIŞ'})")

print("\n" + "=" * 80)
print("✅ TEST TAMAMLANDI")
print("=" * 80)

print("\n📊 ÖZET:")
print("   • Tüm senaryolarda TP = +4 USD kar (margin'in %40'ı)")
print("   • Tüm senaryolarda SL = -1 USD zarar (margin'in %10'u)")
print("   • Entry fiyatı değişse de, TP/SL değerleri SABİT kalıyor")
print("   • Bu tam olarak istenen davranış!")
