#!/usr/bin/env python3
# test_telegram.py - Telegram bildirimlerini test et

import sys
import os

# Proje kök dizinini sys.path'e ekle
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src import config
from src.notifications import telegram

def main():
    print("=" * 60)
    print("TELEGRAM BİLDİRİM TESTİ")
    print("=" * 60)
    
    # Bot'u başlat
    print("\n1️⃣ Telegram botu başlatılıyor...")
    success = telegram.initialize_bot(config)
    
    if not success:
        print("❌ Bot başlatılamadı! .env dosyanızı kontrol edin.")
        return
    
    print("✅ Bot başarıyla başlatıldı!\n")
    
    # Basit test mesajı
    print("2️⃣ Test mesajı gönderiliyor...")
    test_message = telegram.escape_markdown_v2("🤖 ChimeraBot test mesajı!\n\nTelegram bildirimleri çalışıyor ✅")
    telegram.send_message(test_message)
    print("✅ Test mesajı gönderildi!\n")
    
    # Sinyal mesajı testi
    print("3️⃣ Örnek sinyal mesajı gönderiliyor...")
    test_signal = {
        'symbol': 'BTC/USDT',
        'direction': 'LONG',
        'strategy': 'PULLBACK',
        'entry_price': 75432.50,
        'sl_price': 74500.00,
        'tp_price': 77500.00,
        'rr_ratio': 2.2,
        'quality_grade': 'A',
        'final_risk_usd': 50.0
    }
    telegram.send_new_signal_alert([test_signal])
    print("✅ Sinyal mesajı gönderildi!\n")
    
    # Pozisyon kapanış mesajı testi
    print("4️⃣ Örnek pozisyon kapanış mesajı gönderiliyor...")
    test_close = {
        'symbol': 'ETH/USDT',
        'direction': 'SHORT',
        'close_reason': 'TAKE_PROFIT',
        'entry_price': 4200.00,
        'close_price': 4050.00,
        'pnl_percent': 3.57
    }
    telegram.send_position_closed_alert(test_close)
    print("✅ Kapanış mesajı gönderildi!\n")
    
    print("=" * 60)
    print("✅ TÜM TESTLER TAMAMLANDI!")
    print("Telegram'ı kontrol edin, 3 mesaj almış olmalısınız.")
    print("=" * 60)

if __name__ == '__main__':
    main()
