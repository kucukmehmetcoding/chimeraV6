#!/usr/bin/env python3
"""
📊 BINANCE TRADE HISTORY SYNC
==============================

Binance'den geçmiş trade verilerini çekip TradeHistory'ye kaydeder.
Dün geceden bugüne kadar olan tüm kapalı pozisyonları database'e aktarır.

Kullanım:
    python sync_historical_trades.py

Author: ChimeraBot Team
"""

import os
import sys
from datetime import datetime, timedelta

# Proje yolunu ekle
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_fetcher.binance_fetcher import binance_client
from src.database.models import TradeHistory, db_session
from sqlalchemy import func
import logging

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_binance_income_history(days_back=2):
    """
    Binance'den gelir/gider geçmişini çek (realized PnL).
    """
    try:
        # Son X gün
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        
        # Income history (REALIZED_PNL tipinde olanlar)
        income_data = binance_client.futures_income_history(
            startTime=start_time,
            limit=1000
        )
        
        # Sadece realized PnL'leri filtrele (hem kar hem zarar)
        pnl_records = [
            rec for rec in income_data 
            if rec.get('incomeType') == 'REALIZED_PNL'
        ]
        
        # Kar/zarar dağılımını logla
        profitable = sum(1 for r in pnl_records if float(r.get('income', 0)) > 0)
        losing = sum(1 for r in pnl_records if float(r.get('income', 0)) < 0)
        zero = sum(1 for r in pnl_records if float(r.get('income', 0)) == 0)
        
        logger.info(f"✅ Binance'den {len(pnl_records)} adet realized PnL kaydı çekildi")
        logger.info(f"   💚 Karlı: {profitable} | 🔴 Zararlı: {losing} | ⚪ Sıfır: {zero}")
        return pnl_records
    
    except Exception as e:
        logger.error(f"❌ Binance income history hatası: {e}")
        return []


def get_binance_position_history(symbol, days_back=2):
    """
    Belirli bir symbol için trade detaylarını al.
    """
    try:
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        
        trades = binance_client.futures_account_trades(
            symbol=symbol,
            startTime=start_time,
            limit=1000
        )
        
        return trades
    
    except Exception as e:
        logger.warning(f"⚠️  {symbol} trade history hatası: {e}")
        return []


def sync_trades_to_database():
    """
    Binance'den trade verilerini çek ve TradeHistory'ye kaydet.
    """
    logger.info("\n" + "="*80)
    logger.info("📊 BINANCE TRADE HISTORY SYNC BAŞLATILDI")
    logger.info("="*80)
    logger.info(f"🕐 Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. Income history'den PnL'leri al
    logger.info("1️⃣  Binance Income History çekiliyor...")
    pnl_records = get_binance_income_history(days_back=2)
    
    if not pnl_records:
        logger.warning("⚠️  Hiç realized PnL kaydı bulunamadı")
        return
    
    # 2. Symbol bazında grupla
    symbol_pnls = {}
    for rec in pnl_records:
        symbol = rec['symbol']
        income = float(rec['income'])
        timestamp = int(rec['time'])
        
        if symbol not in symbol_pnls:
            symbol_pnls[symbol] = []
        
        symbol_pnls[symbol].append({
            'income': income,
            'time': datetime.fromtimestamp(timestamp / 1000),
            'asset': rec.get('asset', 'USDT'),
            'tranId': rec.get('tranId', 0)
        })
    
    logger.info(f"📊 {len(symbol_pnls)} farklı symbol tespit edildi\n")
    
    # 3. Her symbol için TradeHistory oluştur
    db = db_session()
    total_saved = 0
    total_pnl = 0.0
    
    try:
        for symbol, pnl_list in symbol_pnls.items():
            logger.info(f"\n📍 {symbol}:")
            logger.info(f"   Trade sayısı: {len(pnl_list)}")
            
            # Symbol'ün trade detaylarını al
            trades = get_binance_position_history(symbol, days_back=2)
            
            for pnl_record in pnl_list:
                pnl_usd = pnl_record['income']
                closed_time = pnl_record['time']
                
                # Bu PnL için entry/exit fiyatlarını bul
                entry_price = None
                exit_price = None
                position_size = None
                direction = None
                
                # Trade history'den fiyat bilgisi çek
                if trades:
                    # Son trade'leri kontrol et
                    for trade in reversed(trades):
                        trade_time = datetime.fromtimestamp(int(trade['time']) / 1000)
                        if abs((trade_time - closed_time).total_seconds()) < 60:  # 1 dakika içinde
                            if not entry_price:
                                entry_price = float(trade['price'])
                            exit_price = float(trade['price'])
                            position_size = abs(float(trade['qty']))
                            direction = 'LONG' if trade['side'] == 'BUY' else 'SHORT'
                
                # Entry/exit fiyat bulunamazsa tahmin et
                if not entry_price or not exit_price:
                    # Varsayılan değerler
                    entry_price = 0.0
                    exit_price = 0.0
                    position_size = 1.0
                    direction = 'LONG' if pnl_usd > 0 else 'SHORT'
                
                # PnL yüzdesi hesapla (10x leverage, $10 margin varsayımı)
                margin = 10.0
                leverage = 10
                pnl_percent = (pnl_usd / (margin * leverage)) * 100 if margin and leverage else 0
                
                # Database'de var mı kontrol et (close_time Unix timestamp)
                close_timestamp = int(closed_time.timestamp())
                existing = db.query(TradeHistory).filter(
                    TradeHistory.symbol == symbol,
                    TradeHistory.close_time == close_timestamp
                ).first()
                
                if existing:
                    logger.info(f"   ⏭️  Zaten kayıtlı: {closed_time.strftime('%H:%M:%S')} - ${pnl_usd:+.2f}")
                    continue
                
                # Yeni kayıt oluştur
                trade_record = TradeHistory(
                    symbol=symbol,
                    strategy='range_trading',
                    direction=direction,
                    quality_grade='N/A',
                    entry_price=entry_price,
                    close_price=exit_price,
                    sl_price=0.0,
                    tp_price=0.0,
                    leverage=leverage,
                    position_size_units=position_size,
                    pnl_usd=pnl_usd,
                    pnl_percent=pnl_percent,
                    open_time=int((closed_time - timedelta(minutes=5)).timestamp()),  # Tahmin - Unix timestamp
                    close_time=int(closed_time.timestamp()),  # Unix timestamp
                    close_reason='Binance_Historical_Sync'
                )
                
                db.add(trade_record)
                total_saved += 1
                total_pnl += pnl_usd
                
                emoji = "✅" if pnl_usd >= 0 else "❌"
                logger.info(f"   {emoji} {closed_time.strftime('%Y-%m-%d %H:%M:%S')} - "
                          f"${pnl_usd:+.2f} ({pnl_percent:+.2f}%) - {direction}")
        
        # Toplu commit
        db.commit()
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ SYNC TAMAMLANDI")
        logger.info(f"{'='*80}")
        logger.info(f"📊 Toplam kaydedilen: {total_saved} trade")
        logger.info(f"💰 Toplam PnL: ${total_pnl:+.2f}")
        
        # Kar/zarar dağılımı
        profitable = sum(1 for _, pnls in symbol_pnls.items() for p in pnls if p['income'] > 0)
        losing = sum(1 for _, pnls in symbol_pnls.items() for p in pnls if p['income'] < 0)
        
        logger.info(f"✅ Karlı trade: {profitable}")
        logger.info(f"❌ Zararlı trade: {losing}")
        
        if profitable + losing > 0:
            win_rate = (profitable / (profitable + losing)) * 100
            logger.info(f"📊 Kazanma oranı: {win_rate:.1f}%")
    
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Database kayıt hatası: {e}", exc_info=True)
    
    finally:
        db_session.remove()


def show_current_database_stats():
    """
    Mevcut TradeHistory istatistiklerini göster.
    """
    db = db_session()
    
    try:
        total_trades = db.query(TradeHistory).count()
        total_pnl = db.query(func.sum(TradeHistory.pnl_usd)).scalar() or 0.0
        
        logger.info("\n" + "="*80)
        logger.info("📊 MEVCUT DATABASE İSTATİSTİKLERİ")
        logger.info("="*80)
        logger.info(f"📈 Toplam trade: {total_trades}")
        logger.info(f"💰 Toplam PnL: ${total_pnl:+.2f}")
        
        # Son 10 trade
        if total_trades > 0:
            recent_trades = db.query(TradeHistory).order_by(
                TradeHistory.close_time.desc()
            ).limit(10).all()
            
            logger.info(f"\n📋 Son 10 Trade:")
            for trade in recent_trades:
                emoji = "✅" if trade.pnl_usd >= 0 else "❌"
                close_dt = datetime.fromtimestamp(trade.close_time) if trade.close_time else datetime.now()
                logger.info(f"   {emoji} {trade.symbol} - {close_dt.strftime('%Y-%m-%d %H:%M:%S')} - "
                          f"${trade.pnl_usd:+.2f} ({trade.pnl_percent:+.2f}%)")
    
    finally:
        db_session.remove()


if __name__ == "__main__":
    try:
        # Önce mevcut durumu göster
        show_current_database_stats()
        
        # Sync işlemi
        sync_trades_to_database()
        
        # Sonra yeni durumu göster
        show_current_database_stats()
    
    except KeyboardInterrupt:
        logger.info("\n⛔ İşlem iptal edildi")
    
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}", exc_info=True)
