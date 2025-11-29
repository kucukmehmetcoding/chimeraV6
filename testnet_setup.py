#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance Testnet Setup
Testnet hesabı kurulumu ve doğrulama
"""

import os
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)


def setup_testnet(api_key: str = None, api_secret: str = None) -> Client:
    """
    Binance Testnet hesabı kurulumu
    
    Args:
        api_key: Testnet API key (None ise .env'den alır)
        api_secret: Testnet API secret (None ise .env'den alır)
    
    Returns:
        Binance Client nesnesi
    
    Testnet hesabı oluşturma:
    1. https://testnet.binancefuture.com adresine git
    2. Email ile kayıt ol
    3. API Management -> Create API Key
    4. Read/Write yetkisi ver
    5. API Key ve Secret'i kopyala
    """
    
    # API credentials
    if not api_key:
        api_key = os.getenv('BINANCE_TESTNET_API_KEY', '')
    if not api_secret:
        api_secret = os.getenv('BINANCE_TESTNET_SECRET_KEY', '')
    
    if not api_key or not api_secret:
        print("\n" + "="*64)
        print("❌ TESTNET API KEY BULUNAMADI")
        print("="*64)
        print("\n🔧 Testnet hesabı oluşturma adımları:")
        print("1. https://testnet.binancefuture.com adresine git")
        print("2. Email ile ücretsiz kayıt ol")
        print("3. API Management -> Create API Key")
        print("4. Read + Write yetkisi ver")
        print("5. API Key ve Secret'i kopyala")
        print("\n6. .env dosyasına ekle:")
        print("   BINANCE_TESTNET_API_KEY=your_testnet_key")
        print("   BINANCE_TESTNET_SECRET_KEY=your_testnet_secret")
        print("="*64 + "\n")
        raise ValueError("Testnet API credentials bulunamadı")
    
    # Client oluştur (TESTNET MODE)
    try:
        client = Client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=True  # CRITICAL - Testnet modu
        )
        
        # Bağlantı testi
        client.ping()
        
        # Futures hesap bilgisi
        account_info = client.futures_account()
        balance = float(account_info['totalWalletBalance'])
        available = float(account_info['availableBalance'])
        
        print("\n" + "╔" + "═"*62 + "╗")
        print("║" + " "*15 + "✅ TESTNET BAĞLANTISI BAŞARILI" + " "*16 + "║")
        print("╚" + "═"*62 + "╝\n")
        
        print(f"💰 Total Balance:     {balance:.2f} USDT")
        print(f"💵 Available Balance: {available:.2f} USDT")
        print(f"🔑 API Key:           {api_key[:10]}...")
        print(f"🌐 Testnet URL:       https://testnet.binancefuture.com")
        
        # Açık pozisyonları kontrol et
        positions = client.futures_position_information()
        open_positions = [p for p in positions if float(p['positionAmt']) != 0]
        
        if open_positions:
            print(f"\n⚠️  Açık Pozisyonlar: {len(open_positions)}")
            for pos in open_positions:
                print(f"   - {pos['symbol']}: {pos['positionAmt']} @ {pos['entryPrice']}")
        else:
            print("\n✅ Açık pozisyon yok")
        
        print("\n" + "="*64 + "\n")
        
        return client
        
    except BinanceAPIException as e:
        print(f"\n❌ Binance API Hatası: {e.message}")
        print(f"   Error Code: {e.code}")
        print(f"   Status Code: {e.status_code}\n")
        
        if e.code == -2015:
            print("💡 API key yanlış veya geçersiz")
        elif e.code == -1022:
            print("💡 API signature hatası - secret key yanlış")
        
        raise
        
    except Exception as e:
        print(f"\n❌ Testnet bağlantı hatası: {e}\n")
        logger.error(f"Testnet setup error: {e}", exc_info=True)
        raise


def check_testnet_balance(client: Client) -> dict:
    """Testnet bakiyesini kontrol et"""
    try:
        account = client.futures_account()
        
        return {
            'total_balance': float(account['totalWalletBalance']),
            'available_balance': float(account['availableBalance']),
            'total_unrealized_pnl': float(account['totalUnrealizedProfit']),
            'total_margin_balance': float(account['totalMarginBalance'])
        }
        
    except Exception as e:
        logger.error(f"Balance check error: {e}")
        return None


def get_testnet_positions(client: Client) -> list:
    """Açık pozisyonları getir"""
    try:
        positions = client.futures_position_information()
        
        # Sadece açık pozisyonları filtrele
        open_positions = []
        for pos in positions:
            if float(pos['positionAmt']) != 0:
                open_positions.append({
                    'symbol': pos['symbol'],
                    'position_amt': float(pos['positionAmt']),
                    'entry_price': float(pos['entryPrice']),
                    'unrealized_pnl': float(pos['unRealizedProfit']),
                    'leverage': int(pos['leverage']),
                    'liquidation_price': float(pos['liquidationPrice'])
                })
        
        return open_positions
        
    except Exception as e:
        logger.error(f"Get positions error: {e}")
        return []


def close_all_testnet_positions(client: Client):
    """Tüm açık pozisyonları kapat (EMERGENCY)"""
    try:
        positions = get_testnet_positions(client)
        
        if not positions:
            print("✅ Kapatılacak pozisyon yok")
            return
        
        print(f"\n⚠️  {len(positions)} pozisyon kapatılıyor...")
        
        for pos in positions:
            symbol = pos['symbol']
            position_amt = pos['position_amt']
            
            # Kapatma yönü (long ise sat, short ise al)
            side = 'SELL' if position_amt > 0 else 'BUY'
            quantity = abs(position_amt)
            
            print(f"   Closing {symbol}: {side} {quantity}")
            
            try:
                # Market order ile kapat
                order = client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='MARKET',
                    quantity=quantity,
                    reduceOnly=True  # Sadece pozisyon kapatma
                )
                
                print(f"   ✅ {symbol} closed - Order ID: {order['orderId']}")
                
            except Exception as e:
                print(f"   ❌ {symbol} kapatma hatası: {e}")
        
        print("\n✅ Tüm pozisyonlar kapatıldı\n")
        
    except Exception as e:
        logger.error(f"Close all positions error: {e}")
        raise


# .env Template
TESTNET_ENV_TEMPLATE = """
# =============================================================================
# BINANCE TESTNET CONFIGURATION
# =============================================================================
# Testnet hesabı: https://testnet.binancefuture.com

# Testnet API Keys (FAKE MONEY - Gerçek para riski YOK)
BINANCE_TESTNET_API_KEY=your_testnet_api_key_here
BINANCE_TESTNET_SECRET_KEY=your_testnet_secret_key_here

# Testnet modunu aktifleştir
BINANCE_TESTNET=True

# =============================================================================
# LIVE TRADING CONFIGURATION (REAL MONEY - DİKKAT!)
# =============================================================================
# Live trading için gerçek API keys
# BINANCE_API_KEY=your_real_api_key_here
# BINANCE_SECRET_KEY=your_real_secret_key_here

# Live mode (False = Testnet, True = Real trading)
# BINANCE_TESTNET=False
"""


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "╔" + "═"*62 + "╗")
    print("║" + " "*15 + "BINANCE TESTNET SETUP" + " "*26 + "║")
    print("╚" + "═"*62 + "╝\n")
    
    # .env kontrolü
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        print("⚠️  .env dosyası bulunamadı")
        print("\nŞablon .env dosyası oluşturuluyor...")
        
        with open(env_path, 'w') as f:
            f.write(TESTNET_ENV_TEMPLATE)
        
        print(f"✅ .env dosyası oluşturuldu: {env_path}")
        print("\n📝 Lütfen .env dosyasını düzenleyin ve testnet API keys ekleyin")
        print("   1. https://testnet.binancefuture.com -> API Management")
        print("   2. Create API Key")
        print("   3. Copy key and secret")
        print("   4. Paste into .env file\n")
    
    # Testnet'e bağlan
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        
        client = setup_testnet()
        
        # Balance kontrol
        balance = check_testnet_balance(client)
        if balance:
            print(f"💰 Balance Details:")
            print(f"   Total:           ${balance['total_balance']:.2f}")
            print(f"   Available:       ${balance['available_balance']:.2f}")
            print(f"   Unrealized PnL:  ${balance['total_unrealized_pnl']:+.2f}")
            print(f"   Margin Balance:  ${balance['total_margin_balance']:.2f}\n")
        
        # Pozisyonlar
        positions = get_testnet_positions(client)
        if positions:
            print(f"📊 Open Positions ({len(positions)}):")
            for pos in positions:
                pnl_symbol = "🟢" if pos['unrealized_pnl'] > 0 else "🔴"
                print(f"   {pnl_symbol} {pos['symbol']}: {pos['position_amt']:+.4f} @ ${pos['entry_price']:.2f} | "
                      f"PnL: ${pos['unrealized_pnl']:+.2f}")
            print()
        
        print("="*64)
        print("✅ Testnet hazır - Live trading test edebilirsiniz!")
        print("="*64 + "\n")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}\n")
