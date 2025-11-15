#!/usr/bin/env python3
"""
🎯 RANGE TRADING BOT - Position Monitor
========================================

Range trading bot ile açılan pozisyonları canlı takip eder.
Binance otomatik SL/TP ile açılan pozisyonların kapanış durumunu izler.

Özellikler:
- Binance'den açık pozisyonları real-time kontrol
- Kapanan pozisyonları tespit et
- PnL hesapla ve Telegram bildirim gönder
- Database'i güncelle

Kullanım:
    python range_position_monitor.py

Author: ChimeraBot Team - Range Trading Module
Version: 1.0.0
"""

import os
import sys
import time
import logging
from datetime import datetime
from threading import Event

# Proje yolunu ekle
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_fetcher.binance_fetcher import binance_client
from src.database.models import OpenPosition, TradeHistory, db_session
from src.notifications import telegram as telegram_notifier

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('logs/range_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global
stop_event = Event()
CHECK_INTERVAL = 5  # 5 saniye - anlık takip için


def get_binance_open_positions() -> dict:
    """
    Binance'den açık pozisyonları al.
    Returns: {symbol: position_info}
    """
    try:
        positions = binance_client.futures_position_information()
        
        open_positions = {}
        for pos in positions:
            position_amt = float(pos.get('positionAmt', 0))
            if position_amt != 0:  # Açık pozisyon var
                symbol = pos['symbol']
                open_positions[symbol] = {
                    'side': 'LONG' if position_amt > 0 else 'SHORT',
                    'amount': abs(position_amt),
                    'entry_price': float(pos.get('entryPrice', 0)),
                    'unrealized_pnl': float(pos.get('unRealizedProfit', 0)),
                    'leverage': int(pos.get('leverage', 1))
                }
        
        return open_positions
    
    except Exception as e:
        logger.error(f"❌ Binance pozisyon bilgisi alınamadı: {e}")
        return {}


def get_database_open_positions() -> dict:
    """
    Database'den range trading pozisyonlarını al.
    Returns: {symbol: position_record}
    """
    db = db_session()
    try:
        positions = db.query(OpenPosition).filter(
            OpenPosition.strategy == 'range_trading'
        ).all()
        
        db_positions = {}
        for pos in positions:
            db_positions[pos.symbol] = pos
        
        return db_positions
    
    finally:
        db_session.remove()


def get_trade_pnl(symbol: str) -> float:
    """
    Binance trade history'den realized PnL al.
    """
    try:
        trades = binance_client.futures_account_trades(
            symbol=symbol,
            limit=10
        )
        
        if not trades:
            return 0.0
        
        # Son trade'lerin realized PnL'lerini topla
        total_pnl = sum(float(t.get('realizedPnl', 0)) for t in trades[-5:])
        return total_pnl
    
    except Exception as e:
        logger.warning(f"⚠️ {symbol} PnL alınamadı: {e}")
        return 0.0


def send_position_closed_notification(pos, realized_pnl: float):
    """
    Pozisyon kapandı Telegram bildirimi gönder.
    """
    try:
        emoji = "✅" if realized_pnl >= 0 else "❌"
        pnl_percent = 0
        
        if pos.margin and pos.leverage:
            pnl_percent = (realized_pnl / (pos.margin * pos.leverage)) * 100
        
        message = (
            f"{emoji} *RANGE POZİSYON KAPANDI*\n\n"
            f"*Symbol:* `{pos.symbol}`\n"
            f"*Direction:* {pos.direction}\n"
            f"*Strateji:* Range Trading\n\n"
            f"*Giriş Detayları:*\n"
            f"  📍 Entry: ${pos.entry_price:.6f}\n"
            f"  🎯 TP: ${pos.tp_price:.6f}\n"
            f"  🛡️ SL: ${pos.sl_price:.6f}\n\n"
            f"*Range Seviyeleri:*\n"
            f"  🔵 Destek: ${pos.support_level:.6f}\n"
            f"  🔴 Direnç: ${pos.resistance_level:.6f}\n"
            f"  📊 Genişlik: {pos.range_width:.2%}\n\n"
            f"*Sonuç:*\n"
            f"  💰 PnL: ${realized_pnl:+.2f}\n"
            f"  📊 Return: {pnl_percent:+.2f}%\n"
            f"  ⚡ Kaldıraç: {pos.leverage}x\n"
            f"  💵 Margin: ${pos.margin}\n\n"
            f"*Açılış:* {pos.open_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"*Kapanış:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"_Binance Otomatik SL/TP ile kapatıldı_"
        )
        
        telegram_notifier.send_message(message)
        logger.info(f"✅ Telegram bildirimi gönderildi: {pos.symbol}")
    
    except Exception as e:
        logger.error(f"❌ Telegram bildirim hatası: {e}")


def monitor_positions():
    """
    Ana monitoring loop - Binance vs Database pozisyon karşılaştırması.
    """
    logger.info("\n" + "="*80)
    logger.info("🎯 RANGE TRADING POSITION MONITOR BAŞLATILDI")
    logger.info("="*80)
    logger.info(f"⏱️  Kontrol Aralığı: {CHECK_INTERVAL} saniye")
    logger.info(f"🎯 Binance Otomatik SL/TP - Pozisyon Kapanış Takibi")
    logger.info("="*80 + "\n")
    
    check_count = 0
    total_closed_positions = 0  # Toplam kapanan pozisyon sayısı
    total_pnl = 0.0  # Toplam kar/zarar (komisyon dahil)
    
    while not stop_event.is_set():
        try:
            check_count += 1
            
            # 1. Database'den range pozisyonlarını al
            db_positions = get_database_open_positions()
            
            if not db_positions:
                if check_count % 20 == 1:  # Her 5 dakikada bir
                    logger.info("ℹ️  Açık range pozisyonu yok")
                stop_event.wait(CHECK_INTERVAL)
                continue
            
            # 2. Binance'den açık pozisyonları al
            binance_positions = get_binance_open_positions()
            
            # 3. Database'de var ama Binance'de yok = Kapanmış
            db_symbols = set(db_positions.keys())
            binance_symbols = set(binance_positions.keys())
            
            closed_symbols = db_symbols - binance_symbols
            
            if closed_symbols:
                logger.info(f"\n{'='*80}")
                logger.info(f"🎯 KAPANAN POZİSYONLAR TESPİT EDİLDİ: {len(closed_symbols)}")
                logger.info(f"{'='*80}")
            
            # 4. Kapanan pozisyonları işle
            for symbol in closed_symbols:
                pos = db_positions[symbol]
                
                logger.info(f"\n📊 {symbol} pozisyonu kapandı:")
                logger.info(f"   Direction: {pos.direction}")
                logger.info(f"   Entry: ${pos.entry_price:.6f}")
                logger.info(f"   TP: ${pos.tp_price:.6f}")
                logger.info(f"   SL: ${pos.sl_price:.6f}")
                
                # PnL hesapla (Binance trade history'den - komisyon dahil)
                realized_pnl = get_trade_pnl(symbol)
                logger.info(f"   💰 Realized PnL: ${realized_pnl:+.2f} (komisyon dahil)")
                
                # Toplam sayaçları güncelle
                total_closed_positions += 1
                total_pnl += realized_pnl
                
                # PnL yüzdesini hesapla
                pnl_percent = 0
                if pos.margin and pos.leverage:
                    pnl_percent = (realized_pnl / (pos.margin * pos.leverage)) * 100
                
                # Telegram bildirim
                send_position_closed_notification(pos, realized_pnl)
                
                # TradeHistory'ye kaydet
                db = db_session()
                try:
                    # Kapaş fiyatını tahmin et (PnL'den ters hesapla)
                    if pos.direction == 'LONG':
                        # realized_pnl = (close_price - entry_price) * position_size
                        close_price = pos.entry_price + (realized_pnl / pos.position_size) if pos.position_size else pos.entry_price
                    else:  # SHORT
                        # realized_pnl = (entry_price - close_price) * position_size
                        close_price = pos.entry_price - (realized_pnl / pos.position_size) if pos.position_size else pos.entry_price
                    
                    # TradeHistory kaydı oluştur
                    trade_record = TradeHistory(
                        symbol=pos.symbol,
                        strategy=pos.strategy,
                        direction=pos.direction,
                        quality_grade='N/A',  # Range trading için quality yok
                        entry_price=pos.entry_price,
                        close_price=close_price,  # exit_price değil close_price
                        sl_price=pos.sl_price,
                        tp_price=pos.tp_price,
                        leverage=pos.leverage,
                        position_size_units=pos.position_size,
                        pnl_usd=realized_pnl,
                        pnl_percent=pnl_percent,
                        open_time=pos.open_time,  # Zaten Unix timestamp
                        close_time=int(datetime.now().timestamp()),  # Unix timestamp
                        close_reason='Binance_Auto_SL_TP'  # exit_reason değil close_reason
                    )
                    
                    db.add(trade_record)
                    db.commit()
                    logger.info(f"   ✅ TradeHistory'ye kaydedildi: {symbol}")
                    
                    # Şimdi OpenPosition'dan sil
                    db.delete(pos)
                    db.commit()
                    logger.info(f"   ✅ OpenPosition'dan silindi: {symbol}")
                    
                except Exception as db_error:
                    db.rollback()
                    logger.error(f"   ❌ Database işlemi hatası: {db_error}")
                finally:
                    db_session.remove()
            
            # Kapanış özeti göster
            if closed_symbols:
                logger.info(f"\n{'='*80}")
                logger.info(f"📈 TOPLAM KAPANAN POZİSYONLAR: {total_closed_positions}")
                logger.info(f"💰 TOPLAM KAR/ZARAR: ${total_pnl:+.2f} (Binance komisyonları dahil)")
                
                # Ortalama kar/zarar
                if total_closed_positions > 0:
                    avg_pnl = total_pnl / total_closed_positions
                    logger.info(f"📊 ORTALAMA PnL: ${avg_pnl:+.2f}")
                
                # Kar/zarar dağılımı
                win_count = sum(1 for s in closed_symbols if get_trade_pnl(s) > 0)
                loss_count = total_closed_positions - win_count
                if total_closed_positions > 0:
                    win_rate = (win_count / total_closed_positions) * 100
                    logger.info(f"✅ Kazanan: {win_count} | ❌ Kaybeden: {loss_count} | 📊 Win Rate: {win_rate:.1f}%")
                
                logger.info(f"{'='*80}\n")
            
            # 5. Açık pozisyon özeti
            if check_count % 4 == 1:  # Her 20 saniyede bir (5sn * 4)
                remaining_positions = len(db_positions) - len(closed_symbols)
                if remaining_positions > 0:
                    logger.info(f"\n📊 Aktif Pozisyonlar: {remaining_positions}")
                    
                    for symbol, pos in db_positions.items():
                        if symbol not in closed_symbols:
                            binance_pos = binance_positions.get(symbol, {})
                            unrealized_pnl = binance_pos.get('unrealized_pnl', 0)
                            
                            # Icon seçimi: Yeşil (kar), Kırmızı (zarar)
                            pnl_icon = "🟢" if unrealized_pnl >= 0 else "🔴"
                            
                            logger.info(f"   {pnl_icon} {symbol} ({pos.direction}): "
                                      f"Entry ${pos.entry_price:.4f} | "
                                      f"Unrealized PnL: ${unrealized_pnl:+.2f}")
            
            # Bekleme
            stop_event.wait(CHECK_INTERVAL)
        
        except KeyboardInterrupt:
            logger.info("\n⛔ Kullanıcı tarafından durduruldu")
            break
        
        except Exception as e:
            logger.error(f"❌ Monitor hatası: {e}", exc_info=True)
            stop_event.wait(60)


if __name__ == "__main__":
    try:
        monitor_positions()
    
    except KeyboardInterrupt:
        logger.info("\n⛔ Program sonlandırıldı")
    
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}", exc_info=True)
