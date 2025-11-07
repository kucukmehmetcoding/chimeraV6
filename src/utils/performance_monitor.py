#!/usr/bin/env python3
"""
📊 ORCHESTRATOR İÇİN PERFORMANS MONİTÖRÜ
========================================

Ana orchestrator'a entegre edilebilir modül.
Her scan sonrası otomatik özet gösterir.
"""

import sys
import os

# Path ayarları
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.database.models import db_session, OpenPosition, TradeHistory
from src.data_fetcher.binance_fetcher import get_current_price
import logging

logger = logging.getLogger(__name__)

def get_quick_performance_summary():
    """
    Hızlı performans özeti döndürür.
    Orchestrator'ın her scan sonunda çağırabileceği hafif bir fonksiyon.
    
    Returns:
        dict: Performans metrikleri
    """
    db = db_session()
    
    try:
        # Verileri yükle
        open_positions = db.query(OpenPosition).all()
        closed_trades = db.query(TradeHistory).all()
        
        # Açık pozisyonlar için unrealized PnL
        total_unrealized = 0.0
        total_risk = 0.0
        
        for pos in open_positions:
            try:
                current_price = get_current_price(pos.symbol)
                if current_price:
                    if pos.direction.upper() == 'LONG':
                        pnl = (current_price - pos.entry_price) * pos.position_size_units
                    else:
                        pnl = (pos.entry_price - current_price) * pos.position_size_units
                    
                    total_unrealized += pnl
                    total_risk += pos.final_risk_usd
            except Exception:
                continue
        
        # Kapanan pozisyonlar için realized PnL
        realized_pnl = 0.0
        winning_trades = 0
        losing_trades = 0
        
        for trade in closed_trades:
            if trade.pnl_usd:
                realized_pnl += trade.pnl_usd
                if trade.pnl_usd > 0:
                    winning_trades += 1
                elif trade.pnl_usd < 0:
                    losing_trades += 1
        
        total_completed = winning_trades + losing_trades
        win_rate = (winning_trades / total_completed * 100) if total_completed > 0 else 0
        
        return {
            'open_positions_count': len(open_positions),
            'closed_trades_count': len(closed_trades),
            'unrealized_pnl': total_unrealized,
            'realized_pnl': realized_pnl,
            'total_risk': total_risk,
            'win_rate': win_rate,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'has_data': total_completed > 0
        }
        
    except Exception as e:
        logger.error(f"Performans özeti hatası: {e}")
        return None
    
    finally:
        db_session.remove()


def print_performance_summary():
    """
    Performans özetini konsola yazdırır.
    Orchestrator'ın main_scan_cycle() sonunda çağırılabilir.
    """
    try:
        summary = get_quick_performance_summary()
        
        if summary is None:
            logger.warning("⚠️  Performans özeti alınamadı")
            return
        
        logger.info("=" * 80)
        logger.info("📊 PERFORMANS ÖZETİ")
        logger.info("=" * 80)
        logger.info(f"💼 Açık Pozisyonlar: {summary['open_positions_count']}")
        logger.info(f"💰 Unrealized PnL: ${summary['unrealized_pnl']:+.2f}")
        logger.info(f"📊 Risk: ${summary['total_risk']:.2f}")
        
        if summary['has_data']:
            logger.info(f"✅ Kapanan İşlemler: {summary['closed_trades_count']} "
                       f"(Win: {summary['winning_trades']}, Loss: {summary['losing_trades']})")
            logger.info(f"🎯 Win Rate: {summary['win_rate']:.1f}%")
            logger.info(f"💵 Realized PnL: ${summary['realized_pnl']:+.2f}")
        else:
            logger.info("⏳ Henüz kapanan pozisyon yok")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Performans özeti yazdırma hatası: {e}")


def send_performance_to_telegram():
    """
    Performans özetini Telegram'a gönderir.
    İsteğe bağlı - her scan sonrası veya belirli aralıklarla çağrılabilir.
    """
    try:
        from src.notifications.telegram import send_message
        
        summary = get_quick_performance_summary()
        if summary is None:
            return
        
        # Telegram mesajı oluştur
        msg = "📊 *Scan Tamamlandı \\- Durum Özeti*\n\n"
        msg += f"💼 Açık: {summary['open_positions_count']}\n"
        msg += f"💰 Unrealized: ${summary['unrealized_pnl']:+.2f}\n"
        
        if summary['has_data']:
            msg += f"🎯 Win Rate: {summary['win_rate']:.1f}%\n"
            msg += f"💵 Realized: ${summary['realized_pnl']:+.2f}"
        else:
            msg += "⏳ Henüz tamamlanmış işlem yok"
        
        send_message(msg)
        
    except Exception as e:
        logger.error(f"Telegram performans özeti hatası: {e}")


if __name__ == "__main__":
    # Test
    print("\n🧪 Test - Performans Özeti:\n")
    print_performance_summary()
