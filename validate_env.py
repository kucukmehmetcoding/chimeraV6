#!/usr/bin/env python3
"""
ENV Configuration Validator
Tests if range_main.py correctly reads environment variables
"""

import os
import sys
from dotenv import load_dotenv

# Load .env.range_bot
load_dotenv('.env.range_bot')

print("🔍 Environment Variable Validation\n")
print("=" * 60)

# Test all critical variables
test_vars = {
    'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY'),
    'BINANCE_SECRET_KEY': os.getenv('BINANCE_SECRET_KEY'),
    'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
    'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID'),
    'BINANCE_TESTNET': os.getenv('BINANCE_TESTNET', 'True'),
    'RANGE_LEVERAGE': int(os.getenv('RANGE_LEVERAGE', '7')),
    'RANGE_MARGIN_PER_TRADE': float(os.getenv('RANGE_MARGIN_PER_TRADE', '10.0')),
    'RANGE_MAX_OPEN_POSITIONS': int(os.getenv('RANGE_MAX_OPEN_POSITIONS', '3')),
    'RANGE_MIN_WIDTH': float(os.getenv('RANGE_MIN_WIDTH', '0.035')),
    'RANGE_MIN_SL_DISTANCE': float(os.getenv('RANGE_MIN_SL_DISTANCE', '0.008')),
    'RANGE_MIN_RR_RATIO': float(os.getenv('RANGE_MIN_RR_RATIO', '2.0')),
    'RANGE_MIN_QUALITY': os.getenv('RANGE_MIN_QUALITY', 'B'),
    'RANGE_USE_HTF_CONFIRMATION': os.getenv('RANGE_USE_HTF_CONFIRMATION', 'True'),
}

# Critical vars (must be set)
critical = ['BINANCE_API_KEY', 'BINANCE_SECRET_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
missing = []

print("\n📋 Critical Variables (Must be configured):")
print("-" * 60)
for key in critical:
    value = test_vars[key]
    if not value or value.startswith('your_'):
        print(f"❌ {key}: NOT SET (placeholder detected)")
        missing.append(key)
    else:
        masked = value[:8] + "..." if len(value) > 8 else "***"
        print(f"✅ {key}: {masked}")

print("\n\n📊 Trading Parameters:")
print("-" * 60)
print(f"Leverage: {test_vars['RANGE_LEVERAGE']}x")
print(f"Margin per Trade: ${test_vars['RANGE_MARGIN_PER_TRADE']}")
print(f"Max Open Positions: {test_vars['RANGE_MAX_OPEN_POSITIONS']}")
print(f"Min Range Width: {test_vars['RANGE_MIN_WIDTH']*100:.1f}%")
print(f"Min SL Distance: {test_vars['RANGE_MIN_SL_DISTANCE']*100:.2f}%")
print(f"Min RR Ratio: {test_vars['RANGE_MIN_RR_RATIO']}:1")
print(f"Min Quality Grade: {test_vars['RANGE_MIN_QUALITY']}")
print(f"HTF Confirmation: {test_vars['RANGE_USE_HTF_CONFIRMATION']}")
print(f"Testnet Mode: {test_vars['BINANCE_TESTNET']}")

print("\n\n🧪 Type Validation:")
print("-" * 60)
try:
    assert isinstance(test_vars['RANGE_LEVERAGE'], int), "LEVERAGE must be int"
    assert isinstance(test_vars['RANGE_MARGIN_PER_TRADE'], float), "MARGIN must be float"
    assert isinstance(test_vars['RANGE_MAX_OPEN_POSITIONS'], int), "MAX_POSITIONS must be int"
    assert isinstance(test_vars['RANGE_MIN_WIDTH'], float), "MIN_WIDTH must be float"
    assert isinstance(test_vars['RANGE_MIN_RR_RATIO'], float), "MIN_RR must be float"
    print("✅ All parameter types are correct")
except AssertionError as e:
    print(f"❌ Type error: {e}")
    sys.exit(1)

print("\n\n✨ Validation Results:")
print("=" * 60)

if missing:
    print(f"❌ FAILED: {len(missing)} critical variable(s) not configured:")
    for key in missing:
        print(f"   - {key}")
    print("\n📝 Action Required:")
    print("   1. Copy .env.range_bot to .env")
    print("   2. Fill in your actual API keys and tokens")
    print("   3. Run this validator again")
    sys.exit(1)
else:
    print("✅ SUCCESS: All variables configured correctly!")
    print("\n🚀 Ready for deployment:")
    print("   1. git push origin main")
    print("   2. Configure Coolify service")
    print("   3. Add environment variables in Coolify dashboard")
    print("   4. Deploy!")
    sys.exit(0)
