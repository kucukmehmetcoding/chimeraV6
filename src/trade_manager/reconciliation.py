"""
Startup reconciliation: sync DB positions with Binance real state
"""
import logging
import time
from typing import List, Dict

logger = logging.getLogger(__name__)

try:
    from src.database.models import get_db_session, OpenPosition, TradeHistory
    from src.trade_manager.executor import get_executor
    from src.notifications import telegram as telegram_notifier
except ImportError as e:
    logger.error(f"Reconciliation import hatası: {e}")
    get_db_session = None


def reconcile_positions_on_startup(config) -> Dict[str, int]:
    """
    Bot başlangıcında DB'deki pozisyonları Binance'teki gerçek durum ile karşılaştırır.
    Binance'te kapalı olan pozisyonları DB'den de temizler.
    
    Returns:
        {
            'db_count': int,
            'binance_count': int,
            'orphaned_count': int,
            'closed_symbols': List[str]
        }
    """
    if not get_db_session:
        logger.error("DB session yok, reconciliation atlanıyor")
        return {'db_count': 0, 'binance_count': 0, 'orphaned_count': 0, 'closed_symbols': []}
    
    executor = get_executor()
    if not executor:
        logger.warning("⚠️ Executor yok, reconciliation atlanıyor (simülasyon modunda olabilir)")
        return {'db_count': 0, 'binance_count': 0, 'orphaned_count': 0, 'closed_symbols': []}
    
    try:
        # 1. DB'den açık pozisyonları al
        with get_db_session() as db:
            db_positions = db.query(OpenPosition).filter(
                OpenPosition.status.in_(['ACTIVE', 'PENDING', 'SIMULATED'])
            ).all()
            db_count = len(db_positions)
            db_symbols = {p.symbol: p for p in db_positions}
            logger.info(f"🔍 Reconciliation: DB'de {db_count} açık pozisyon bulundu")
        
        # 2. Binance'ten açık pozisyonları al
        try:
            # executor.client kullanıyoruz (binance_client değil)
            binance_positions = executor.client.futures_position_information()
            # Sadece gerçekten açık pozisyonları filtrele (positionAmt != 0)
            active_binance = {
                p['symbol']: float(p['positionAmt'])
                for p in binance_positions
                if float(p.get('positionAmt', 0)) != 0
            }
            binance_count = len(active_binance)
            logger.info(f"🔍 Reconciliation: Binance'te {binance_count} açık pozisyon bulundu")
        except Exception as e:
            logger.error(f"Binance pozisyonları alınamadı: {e}")
            return {'db_count': db_count, 'binance_count': 0, 'orphaned_count': 0, 'closed_symbols': []}
        
        # 3. Orphan pozisyonları tespit et (DB'de var ama Binance'te yok)
        orphaned = []
        for symbol, db_pos in db_symbols.items():
            if symbol not in active_binance:
                orphaned.append(db_pos)
        
        if not orphaned:
            logger.info("✅ Reconciliation: Tüm DB pozisyonları Binance ile senkron")
            return {
                'db_count': db_count,
                'binance_count': binance_count,
                'orphaned_count': 0,
                'closed_symbols': []
            }
        
        # 4. Orphan pozisyonları kapat ve TradeHistory'e taşı
        closed_symbols = []
        with get_db_session() as db:
            for orphan_pos in orphaned:
                try:
                    # Gerçek kapanış fiyatını almaya çalış (trade history'den)
                    close_price = _get_close_price_fallback(orphan_pos, executor)
                    
                    # PnL hesapla
                    if orphan_pos.direction.upper() == 'LONG':
                        pnl_usd = (close_price - orphan_pos.entry_price) * orphan_pos.position_size_units
                    else:
                        pnl_usd = (orphan_pos.entry_price - close_price) * orphan_pos.position_size_units
                    
                    pnl_percent = (pnl_usd / (orphan_pos.entry_price * orphan_pos.position_size_units)) * 100.0
                    
                    # TradeHistory'e kaydet
                    history_record = TradeHistory(
                        symbol=orphan_pos.symbol,
                        strategy=orphan_pos.strategy,
                        direction=orphan_pos.direction,
                        quality_grade=orphan_pos.quality_grade,
                        entry_price=orphan_pos.entry_price,
                        close_price=close_price,
                        sl_price=orphan_pos.sl_price,
                        tp_price=orphan_pos.tp_price,
                        position_size_units=orphan_pos.position_size_units,
                        final_risk_usd=orphan_pos.final_risk_usd,
                        leverage=orphan_pos.leverage or 2,
                        open_time=orphan_pos.open_time,
                        close_time=int(time.time()),
                        close_reason='MANUAL_CLOSE_DETECTED',
                        pnl_usd=float(pnl_usd),
                        pnl_percent=float(pnl_percent)
                    )
                    db.add(history_record)
                    
                    # DB'den sil
                    db.delete(orphan_pos)
                    closed_symbols.append(orphan_pos.symbol)
                    
                    logger.warning(f"🧹 {orphan_pos.symbol}: Manuel kapatma tespit edildi, DB'den temizlendi (PnL: ${pnl_usd:.2f})")
                    
                except Exception as e:
                    logger.error(f"Orphan pozisyon temizlenemedi ({orphan_pos.symbol}): {e}")
            
            db.commit()
        
        # 5. Telegram bildirimi
        if closed_symbols:
            try:
                msg = f"🧹 *Reconciliation Sonucu*\n\n"
                msg += f"DB'de {len(orphaned)} orphan pozisyon tespit edildi ve temizlendi:\n"
                msg += "\n".join([f"• {s}" for s in closed_symbols])
                msg += f"\n\n_Not: Bu pozisyonlar Binance'te manuel kapatılmış olabilir._"
                telegram_notifier.send_message(msg)
            except Exception:
                pass
        
        logger.info(f"✅ Reconciliation tamamlandı: {len(orphaned)} orphan pozisyon temizlendi")
        return {
            'db_count': db_count,
            'binance_count': binance_count,
            'orphaned_count': len(orphaned),
            'closed_symbols': closed_symbols
        }
        
    except Exception as e:
        logger.error(f"Reconciliation hatası: {e}", exc_info=True)
        return {'db_count': 0, 'binance_count': 0, 'orphaned_count': 0, 'closed_symbols': []}


def _get_close_price_fallback(pos: OpenPosition, executor) -> float:
    """
    Orphan pozisyon için kapanış fiyatını tahmin et.
    Önce trade history'den al, yoksa güncel market fiyatını kullan.
    """
    try:
        # Trade history'den gerçek close price'ı bul
        if executor.binance_client:
            trades = executor.binance_client.futures_account_trades(
                symbol=pos.symbol,
                limit=100
            )
            # Açılış zamanından sonraki ilk PnL realize eden trade
            for trade in reversed(trades):  # En yeniden başla
                if int(trade['time']) > pos.open_time * 1000 and float(trade.get('realizedPnl', 0)) != 0:
                    return float(trade['price'])
    except Exception as e:
        logger.debug(f"Trade history okunamadı ({pos.symbol}): {e}")
    
    # Fallback: güncel market fiyatı
    try:
        from src.data_fetcher.binance_fetcher import get_current_price
        current = get_current_price(pos.symbol)
        if current:
            return current
    except Exception:
        pass
    
    # Son fallback: TP veya SL ortalaması
    return (pos.tp_price + pos.sl_price) / 2.0
