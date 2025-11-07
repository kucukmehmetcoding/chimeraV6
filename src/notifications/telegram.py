# src/notifications/telegram.py

import logging
import sys
import os
import requests  # GÜNCELLENDİ: Senkron HTTP istekleri için


# GÜNCELLENDİ: python-telegram-bot yerine direkt HTTP API kullanacağız
# Opsiyonel import - hata kontrolleri için kullanılabilir
try:
    from telegram.error import TelegramError
except ImportError:
    # Telegram error sınıfı yoksa kendi exception'ımızı oluştur
    class TelegramError(Exception):
        pass


# --- Proje Kök Dizinini Ayarla ---
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.append(src_path)

# --- Loglamayı Ayarla ---
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')

# --- Global Değişkenler ---
telegram_bot_token: str | None = None
telegram_chat_id: str | None = None

# --- Bot Başlatma ---
def initialize_bot(config_module: object) -> bool:
    """
    Telegram bot bilgilerini yapılandırır.

    Args:
        config_module (object): src.config modülü.

    Returns:
        bool: Başlatma başarılı ise True, değilse False.
    """
    global telegram_bot_token
    global telegram_chat_id

    token = getattr(config_module, 'TELEGRAM_BOT_TOKEN', None)
    chat_id_from_config = getattr(config_module, 'TELEGRAM_CHAT_ID', None)

    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER":
        logger.warning("⚠️ Telegram Bot Token eksik veya yer tutucu değer içeriyor (config.py). Bildirimler çalışmayacak.")
        return False
    
    # Chat ID'yi integer'a çevirmeyi dene
    try:
        chat_id_int = int(chat_id_from_config)
    except (ValueError, TypeError):
         logger.warning(f"⚠️ Telegram Chat ID geçersiz veya yer tutucu değer içeriyor: '{chat_id_from_config}' (config.py). Bildirimler gönderilemeyecek.")
         return False

    try:
        logger.info("⏳ Telegram botu yapılandırılıyor...")
        telegram_bot_token = token
        telegram_chat_id = str(chat_id_int)

        logger.info(f"✅ Telegram botu başarıyla yapılandırıldı. Chat ID: {telegram_chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Telegram botu yapılandırılırken beklenmedik hata oluştu: {e}", exc_info=True)
        telegram_bot_token = None
        telegram_chat_id = None
        return False

# --- Mesaj Gönderme ---
def send_message(message_text: str):
    """
    Genel bir metin mesajını Telegram API'ye senkron HTTP isteği ile gönderir.
    """
    if not telegram_bot_token or not telegram_chat_id:
        if not telegram_bot_token:
            logger.warning("Telegram bot token bilinmediği için mesaj gönderilemedi.")
        else:
            logger.warning("Telegram Chat ID bilinmediği için mesaj gönderilemedi.")
        return
    
    try:
        url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        payload = {
            'chat_id': telegram_chat_id,
            'text': message_text,
            'parse_mode': 'MarkdownV2'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.debug(f"Telegram mesajı başarıyla gönderildi: {message_text[:50]}...")
        else:
            error_data = response.json()
            error_msg = error_data.get('description', 'Bilinmeyen hata')
            logger.error(f"❌ Telegram mesajı gönderilemedi! HTTP {response.status_code}: {error_msg}")
            
            if "chat not found" in error_msg.lower():
                logger.error(f"   HATA: Belirtilen Chat ID ({telegram_chat_id}) bulunamadı veya botun bu chat'e yazma izni yok.")
            elif "bot was blocked" in error_msg.lower():
                logger.error(f"   HATA: Bot kullanıcı ({telegram_chat_id}) tarafından engellenmiş.")
            elif "can't parse entities" in error_msg.lower():
                logger.error(f"   HATA: Mesaj formatı hatalı (MarkdownV2 escape sorunu olabilir)")
                
    except requests.exceptions.Timeout:
        logger.error("❌ Telegram API isteği zaman aşımına uğradı (10 saniye)")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Telegram mesajı gönderilirken HTTP hatası: {e}")
    except Exception as e:
        logger.error(f"❌ Telegram mesajı gönderilirken beklenmedik hata: {e}", exc_info=True)


# --- Mesaj Formatlama (MarkdownV2 için Düzeltmeler) ---
def escape_markdown_v2(text: str) -> str:
    """MarkdownV2 için özel karakterleri escape eder."""
    # Kaçırılması gereken karakterler listesi (Telegram API dokümantasyonuna göre)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    # Her bir özel karakterin önüne \ ekle
    return ''.join(f'\\{char}' if char in escape_chars else char for char in str(text))

def format_signal_message(signal_data: dict) -> str:
    """Sinyal verisini Telegram mesajı için MarkdownV2 formatında hazırlar."""
    symbol = escape_markdown_v2(signal_data.get('symbol', 'N/A'))
    direction = escape_markdown_v2(signal_data.get('direction', 'N/A'))
    strategy = escape_markdown_v2(signal_data.get('strategy', 'N/A'))
    entry = signal_data.get('entry_price', 0.0)
    sl = signal_data.get('sl_price', 0.0)
    tp = signal_data.get('tp_price', 0.0)
    rr = signal_data.get('rr_ratio', 0.0)
    quality = escape_markdown_v2(signal_data.get('quality_grade', 'N/A'))
    
    # Yeni alanlar
    leverage = signal_data.get('leverage', 3)  # Default 3x
    position_size_usd = signal_data.get('position_size_usd', 0.0)  # Notional value (kaldıraçsız)
    position_size_units = signal_data.get('position_size_units', 0.0)
    
    # Gerçek margin (kullanılan sermaye)
    actual_margin_usd = position_size_usd / leverage
    
    # Tahmini kar/zarar hesaplamaları
    if direction == 'LONG':
        potential_profit_usd = (tp - entry) * position_size_units
        potential_loss_usd = (entry - sl) * position_size_units
        # Yüzde hesabı: MARGİN bazında (kullanılan sermayeye göre)
        profit_percent = (potential_profit_usd / actual_margin_usd) * 100 if actual_margin_usd > 0 else 0
        loss_percent = (potential_loss_usd / actual_margin_usd) * 100 if actual_margin_usd > 0 else 0
    else:  # SHORT
        potential_profit_usd = (entry - tp) * position_size_units
        potential_loss_usd = (sl - entry) * position_size_units
        # Yüzde hesabı: MARGİN bazında
        profit_percent = (potential_profit_usd / actual_margin_usd) * 100 if actual_margin_usd > 0 else 0
        loss_percent = (potential_loss_usd / actual_margin_usd) * 100 if actual_margin_usd > 0 else 0
    
    # Fiyatları escape etmeden önce string'e çevirip formatlayalım
    entry_str = escape_markdown_v2(f"{entry:.4f}")
    sl_str = escape_markdown_v2(f"{sl:.4f}")
    tp_str = escape_markdown_v2(f"{tp:.4f}")
    rr_str = escape_markdown_v2(f"{rr:.2f}")
    leverage_str = escape_markdown_v2(f"{leverage}x")
    position_usd_str = escape_markdown_v2(f"{position_size_usd:.2f}")
    margin_usd_str = escape_markdown_v2(f"{actual_margin_usd:.2f}")
    profit_usd_str = escape_markdown_v2(f"{potential_profit_usd:.2f}")
    loss_usd_str = escape_markdown_v2(f"{potential_loss_usd:.2f}")
    profit_pct_str = escape_markdown_v2(f"{profit_percent:.2f}%")
    loss_pct_str = escape_markdown_v2(f"{loss_percent:.2f}%")

    message = f"*🚀 Yeni Pozisyon Açıldı: {symbol}*\n\n"
    message += f"*{escape_markdown_v2('━')}━━━━━━━━━━━━━━━━━━*\n"
    message += f"*📊 İşlem Detayları:*\n"
    message += f"  • *Yön:* {direction}\n"
    message += f"  • *Strateji:* {strategy}\n"
    message += f"  • *Kaldıraç:* {leverage_str}\n"
    message += f"  • *Kalite:* {quality}\n\n"
    
    message += f"*💰 Fiyat Seviyeleri:*\n"
    message += f"  • *Giriş:* {entry_str}\n"
    message += f"  • *Stop Loss:* {sl_str}\n"
    message += f"  • *Take Profit:* {tp_str}\n"
    message += f"  • *Risk/Ödül:* {rr_str}\n\n"
    
    message += f"*💵 Pozisyon Büyüklüğü:*\n"
    message += f"  • *Notional Değer:* \\${position_usd_str}\n"
    message += f"  • *Kullanılan Margin:* \\${margin_usd_str}\n\n"
    
    message += f"*📈 Tahmini Sonuçlar:*\n"
    message += f"  • *Hedef Kar:* \\${profit_usd_str} \({profit_pct_str}\)\n"
    message += f"  • *Maksimum Zarar:* \\${loss_usd_str} \({loss_pct_str}\)\n"
    message += f"*{escape_markdown_v2('━')}━━━━━━━━━━━━━━━━━━*\n"
    
    return message


def send_new_signal_alert(signals: list):
    """Bulunan yeni sinyaller için bildirim gönderir."""
    if not signals:
        return

    if len(signals) == 1:
        message = format_signal_message(signals[0])
        send_message(message)
    else:
        # Birden fazla sinyal varsa özet mesajı gönder
        summary = f"*{escape_markdown_v2(len(signals))} adet yeni sinyal bulundu:*\n\n"
        for signal in signals:
            symbol = escape_markdown_v2(signal.get('symbol', 'N/A'))
            direction = escape_markdown_v2(signal.get('direction', 'N/A'))
            rr = signal.get('rr_ratio', 0.0)
            rr_str = escape_markdown_v2(f"{rr:.2f}")
            summary += f"- {symbol} \({direction}\) R:R={rr_str}\n" # Parantezleri escape et
        send_message(summary)
        # İpucu: İsterseniz burada her sinyal için ayrı ayrı format_signal_message çağrısı da yapabilirsiniz.
        # for signal in signals:
        #    time.sleep(1) # Rate limit yememek için küçük bir bekleme
        #    send_message(format_signal_message(signal))


def format_close_message(position_data: dict) -> str:
    """Kapanan pozisyon verisini Telegram mesajı için MarkdownV2 formatında hazırlar."""
    symbol = escape_markdown_v2(position_data.get('symbol', 'N/A'))
    direction = escape_markdown_v2(position_data.get('direction', 'N/A'))
    close_reason_raw = position_data.get('close_reason', 'N/A')
    # Tire karakterini escape etmeden önce değiştir
    close_reason_text = close_reason_raw.replace('_', ' ').title()
    close_reason = escape_markdown_v2(close_reason_text)
    
    entry = position_data.get('entry_price', 0.0)
    close_price = position_data.get('close_price', 0.0)
    leverage = position_data.get('leverage', 3)
    position_size_units = position_data.get('position_size_units', 0.0)
    position_size_usd = position_data.get('position_size_usd', 0.0)
    
    # Gerçek margin
    actual_margin_usd = position_size_usd / leverage
    
    # PnL hesaplamaları
    if direction == 'LONG':
        pnl_usd = (close_price - entry) * position_size_units
    else:  # SHORT
        pnl_usd = (entry - close_price) * position_size_units
    
    # Yüzde hesabı: MARGİN bazında
    pnl_percent = (pnl_usd / actual_margin_usd) * 100 if actual_margin_usd > 0 else 0
    
    # Escape işlemleri
    entry_str = escape_markdown_v2(f"{entry:.4f}")
    close_price_str = escape_markdown_v2(f"{close_price:.4f}")
    leverage_str = escape_markdown_v2(f"{leverage}x")
    position_usd_str = escape_markdown_v2(f"{position_size_usd:.2f}")
    margin_usd_str = escape_markdown_v2(f"{actual_margin_usd:.2f}")
    pnl_usd_str = escape_markdown_v2(f"{abs(pnl_usd):.2f}")
    pnl_pct_str = escape_markdown_v2(f"{abs(pnl_percent):.2f}%")
    
    # Emoji ve başlık
    if pnl_usd >= 0:
        emoji = "✅"
        pnl_prefix = "+"
        result_text = "KAR 🎉"
    else:
        emoji = "❌"
        pnl_prefix = "-"
        result_text = "ZARAR 😞"

    message = f"*{emoji} Pozisyon Kapatıldı: {symbol}*\n\n"
    message += f"*{escape_markdown_v2('━')}━━━━━━━━━━━━━━━━━━*\n"
    message += f"*📊 İşlem Detayları:*\n"
    message += f"  • *Yön:* {direction}\n"
    message += f"  • *Kaldıraç:* {leverage_str}\n"
    message += f"  • *Kapanış Nedeni:* {close_reason}\n\n"
    
    message += f"*💰 Fiyat Bilgileri:*\n"
    message += f"  • *Giriş:* {entry_str}\n"
    message += f"  • *Kapanış:* {close_price_str}\n"
    message += f"  • *Notional:* \\${position_usd_str}\n"
    message += f"  • *Margin:* \\${margin_usd_str}\n\n"
    
    message += f"*💵 SONUÇ: {escape_markdown_v2(result_text)}*\n"
    message += f"  • *PnL:* {escape_markdown_v2(pnl_prefix)}\\${pnl_usd_str} \({escape_markdown_v2(pnl_prefix)}{pnl_pct_str}\)\n"
    message += f"*{escape_markdown_v2('━')}━━━━━━━━━━━━━━━━━━*\n"
    
    return message

def send_position_closed_alert(closed_position: dict):
    """Kapanan bir pozisyon için bildirim gönderir."""
    message = format_close_message(closed_position)
    send_message(message)

# --- Ana Çalıştırma Bloğu (Test için) ---
if __name__ == '__main__':
    logger.info("Telegram modülü test modunda çalıştırılıyor...")

    class MockConfig:
        TELEGRAM_BOT_TOKEN = "YOUR_ACTUAL_TELEGRAM_BOT_TOKEN" # GERÇEK TOKEN İLE DEĞİŞTİRİN
        TELEGRAM_CHAT_ID = "YOUR_ACTUAL_TELEGRAM_CHAT_ID"     # GERÇEK CHAT ID İLE DEĞİŞTİRİN

    mock_config = MockConfig()

    if initialize_bot(mock_config):
        logger.info("Test: Bot başlatıldı.")

        # MarkdownV2 Test Mesajı
        test_text = escape_markdown_v2("Merhaba! Bu bir *test* mesajıdır. Özel karakterler: . + - = ( ) { }")
        send_message(test_text)

        test_signal = {
            'symbol': 'BTC/USDT', 'direction': 'LONG', 'strategy': 'PULLBACK_TEST',
            'entry_price': 60123.45, 'sl_price': 59123.45, 'tp_price': 62123.45,
            'rr_ratio': 2.05, 'quality_grade': 'B+'
        }
        send_new_signal_alert([test_signal])

        test_closed_position = {
            'symbol': 'ETH-USDT', 'direction': 'SHORT', 'close_reason': 'STOP_LOSS',
            'entry_price': 4000.12, 'close_price': 4050.34
        }
        send_position_closed_alert(test_closed_position)

    else:
        logger.error("Test: Bot başlatılamadı. Token/Chat ID kontrol edin (MockConfig içinde).")