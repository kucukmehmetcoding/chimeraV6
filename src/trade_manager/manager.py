# src/trade_manager/manager.py

import logging
import time
from datetime import datetime  # 🆕 FIX: datetime import ekle
from threading import Lock, Event
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Tuple
from binance.exceptions import BinanceAPIException

# Importlar
try:
    from src.database.models import db_session, OpenPosition, TradeHistory, get_db_session  # YENİ import
    from src.data_fetcher.realtime_manager import RealTimeDataManager
    from src.notifications import telegram as telegram_notifier
    from src.notifications.telegram import send_position_closed_alert  # 🆕 FIX: Eksik import
    from src import config
    # GÜNCELLENDİ: Binance fetcher'a fallback için ihtiyacımız var
    from src.data_fetcher import binance_fetcher
    from src.data_fetcher.binance_fetcher import get_current_price  # 🆕 FIX: Eksik import
    # v5.0 AUTO-PILOT: Executor import
    from src.trade_manager.executor import get_executor
except ImportError as e:
    print(f"KRİTİK HATA (Trade Manager): Gerekli modüller import edilemedi: {e}")
    raise

logger = logging.getLogger(__name__)

# 🆕 FIX: Config'den ENABLE_REAL_TRADING al
ENABLE_REAL_TRADING = getattr(config, 'ENABLE_REAL_TRADING', False)


# --- PnL Hesaplama (Değişiklik Yok) ---
def _calculate_pnl(entry_price: float, close_price: float, direction: str, position_size_units: float) -> Optional[Dict[str, Decimal]]:
    # ... (Kod aynı) ...
    try:
        entry = Decimal(str(entry_price)); close = Decimal(str(close_price)); size = Decimal(str(position_size_units))
        precision = Decimal('0.0001')
        if direction.upper() == 'LONG':
            pnl_usd = (close - entry) * size
            pnl_percent = ((close - entry) / entry * 100).quantize(precision, ROUND_HALF_UP) if entry != 0 else Decimal(0)
        elif direction.upper() == 'SHORT':
            pnl_usd = (entry - close) * size
            pnl_percent = ((entry - close) / entry * 100).quantize(precision, ROUND_HALF_UP) if entry != 0 else Decimal(0)
        else: return None
        pnl_usd = pnl_usd.quantize(Decimal('0.01'), ROUND_HALF_UP)
        return {'pnl_usd': pnl_usd, 'pnl_percent': pnl_percent}
    except Exception as e: logger.error(f"PnL hesaplanırken hata: {e}", exc_info=True); return None


# --- YENİ: Trailing Stop Mantığı ---
def _update_trailing_stop(pos: OpenPosition, current_price: float) -> Tuple[Optional[float], Optional[float]]:
    """
    Verilen pozisyon ve güncel fiyata göre Trailing Stop Loss (TSL) seviyesini günceller.
    (Yeni SL fiyatı, Yeni HighWaterMark) döndürür.
    """
    if not pos.trailing_stop_active or not pos.trailing_stop_distance:
        return None, None # Bu pozisyon TSL kullanmıyor

    new_sl = None
    new_hwm = pos.high_water_mark

    try:
        if pos.direction.upper() == 'LONG':
            # 1. High Water Mark'ı (HWM) Güncelle
            # Fiyat, şu ana kadar ulaştığı en yüksek seviyeyi geçti mi?
            if current_price > pos.high_water_mark:
                new_hwm = current_price # Yeni zirve
                logger.debug(f"   {pos.symbol} (LONG) için yeni HWM: {new_hwm}")
            
            # 2. Yeni SL Hesapla
            # Yeni potansiyel SL (zirveden takip mesafesi kadar aşağısı)
            potential_new_sl = new_hwm - pos.trailing_stop_distance
            
            # 3. SL'i Güncelle (Sadece yukarı taşı, asla aşağı indirme!)
            # Eğer potansiyel SL, mevcut SL'den YÜKSEKSE ve GİRİŞ FİYATINDAN YÜKSEKSE (kârı koru)
            if potential_new_sl > pos.sl_price and potential_new_sl > pos.entry_price:
                new_sl = potential_new_sl # SL'i yukarı çek
        
        elif pos.direction.upper() == 'SHORT':
            # 1. High Water Mark'ı (HWM) Güncelle (Aslında "Low Water Mark")
            # Fiyat, şu ana kadar ulaştığı en düşük seviyeyi geçti mi?
            if current_price < pos.high_water_mark:
                new_hwm = current_price # Yeni dip
                logger.debug(f"   {pos.symbol} (SHORT) için yeni LWM: {new_hwm}")
                
            # 2. Yeni SL Hesapla
            potential_new_sl = new_hwm + pos.trailing_stop_distance
            
            # 3. SL'i Güncelle (Sadece aşağı taşı, asla yukarı indirme!)
            # Eğer potansiyel SL, mevcut SL'den DÜŞÜKSE ve GİRİŞ FİYATINDAN DÜŞÜKSE (kârı koru)
            if potential_new_sl < pos.sl_price and potential_new_sl < pos.entry_price:
                new_sl = potential_new_sl # SL'i aşağı çek

        return new_sl, new_hwm

    except Exception as e:
        logger.error(f"   {pos.symbol} TSL hesaplanırken hata: {e}", exc_info=True)
        return None, None


# --- YENİ: Ghost Position için gerçek kapanış fiyatını bul ---
def _get_real_close_price_from_binance(symbol: str, open_time_ms: int, entry_price: float) -> Optional[float]:
    """
    Binance trades history'den pozisyonun gerçek kapanış fiyatını bul.
    
    Args:
        symbol: Coin sembolü (örn: XVGUSDT)
        open_time_ms: Pozisyon açılış zamanı (timestamp ms)
        entry_price: Pozisyon giriş fiyatı (fallback için)
    
    Returns:
        float: Gerçek kapanış fiyatı veya None
    """
    try:
        executor = get_executor()
        if not executor or not getattr(executor, 'client', None):
            logger.warning(f"⚠️ {symbol} için Binance client bulunamadı, trades history çekilemiyor")
            return None
        
        # Son 50 trade'i çek (pozisyon kapanış trade'i burada olmalı)
        trades = executor.client.futures_account_trades(symbol=symbol, limit=50)
        
        if not trades:
            logger.warning(f"⚠️ {symbol} için trades history boş")
            return None
        
        # Pozisyonun açılış zamanından sonra gerçekleşen kapanış trade'lerini bul
        # realizedPnl != 0 olan trade'ler pozisyon kapatan trade'lerdir
        closing_trades = []
        for trade in trades:
            trade_time = int(trade['time'])
            realized_pnl = float(trade.get('realizedPnl', 0))
            
            # Pozisyon açıldıktan sonra ve PnL realize eden trade'ler
            if trade_time > open_time_ms and realized_pnl != 0:
                closing_trades.append({
                    'time': trade_time,
                    'price': float(trade['price']),
                    'qty': float(trade['qty']),
                    'pnl': realized_pnl
                })
        
        if not closing_trades:
            logger.warning(f"⚠️ {symbol} için kapanış trade'i bulunamadı (açılış: {datetime.fromtimestamp(open_time_ms/1000)})")
            return None
        
        # En son kapanış trade'inin fiyatını kullan
        closing_trades.sort(key=lambda x: x['time'])
        last_close = closing_trades[-1]
        close_price = last_close['price']
        
        logger.info(f"✅ {symbol} gerçek kapanış fiyatı bulundu: ${close_price:.6f} (PnL: ${last_close['pnl']:.2f})")
        return close_price
        
    except BinanceAPIException as e:
        logger.error(f"❌ {symbol} trades history çekilirken Binance API hatası: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ {symbol} gerçek kapanış fiyatı bulunurken hata: {e}", exc_info=True)
        return None


# --- v5.0 AUTO-PILOT: Binance Senkronizasyonu ---
def sync_positions_with_binance(open_positions_lock: Lock) -> int:
    """
    DB'deki ACTIVE pozisyonları Binance API ile senkronize eder.
    Binance'de kapatılmış ama DB'de hala açık olan pozisyonları tespit eder ve kapatır.
    
    Returns:
        int: Kapatılan pozisyon sayısı
    """
    executor = get_executor()
    if not executor:
        logger.warning("⚠️ Executor başlatılmamış, senkronizasyon yapılamıyor")
        return 0
    
    closed_count = 0
    db = None
    
    try:
        # 1. Binance'den gerçek pozisyonları al
        binance_positions = executor.get_open_positions_from_binance()
        binance_symbols = {
            pos['symbol'] for pos in binance_positions 
            if float(pos.get('positionAmt', 0)) != 0
        }
        
        logger.debug(f"Binance'de {len(binance_symbols)} açık pozisyon var")
        
        # 2. DB'den bizim ACTIVE pozisyonlarımızı al
        with open_positions_lock:
            db = db_session()
            db_positions = db.query(OpenPosition).filter(
                OpenPosition.status == 'ACTIVE'
            ).all()
            db_symbols = {pos.symbol for pos in db_positions}
        
        logger.debug(f"DB'de {len(db_symbols)} ACTIVE pozisyon var")
        
        # 3. Sadece DB'de olan (Binance'de kapatılmış) pozisyonları bul
        closed_symbols = db_symbols - binance_symbols
        
        if not closed_symbols:
            logger.debug("✅ Tüm pozisyonlar senkronize")
            return 0
        
        logger.info(f"🔄 {len(closed_symbols)} pozisyon Binance tarafından kapatılmış, senkronize ediliyor...")
        
        # 4. Kapatılan pozisyonları işle
        for symbol in closed_symbols:
            with open_positions_lock:
                pos = db.query(OpenPosition).filter(
                    OpenPosition.symbol == symbol,
                    OpenPosition.status == 'ACTIVE'
                ).first()
                
                if not pos:
                    continue
                
                try:
                    # PnL bilgisini Binance'den al
                    pnl_data = executor.get_last_trade_pnl(symbol)
                    
                    if pnl_data:
                        close_price = pnl_data.get('close_price', pos.entry_price)
                        realized_pnl = pnl_data.get('pnl', 0)
                    else:
                        # PnL alınamazsa, pozisyon bilgisinden tahmin et
                        logger.warning(f"⚠️ {symbol} PnL bilgisi alınamadı, tahmin ediliyor")
                        close_price = pos.entry_price  # En kötü durum
                        realized_pnl = 0
                    
                    # PnL yüzdesini hesapla
                    pnl_result = _calculate_pnl(
                        pos.entry_price,
                        close_price,
                        pos.direction,
                        pos.position_size_units
                    )
                    
                    # TradeHistory'ye kaydet
                    history = TradeHistory(
                        symbol=pos.symbol,
                        strategy=pos.strategy,
                        direction=pos.direction,
                        quality_grade=pos.quality_grade,
                        entry_price=pos.entry_price,
                        close_price=close_price,
                        sl_price=pos.sl_price,
                        tp_price=pos.tp_price,
                        position_size_units=pos.position_size_units,
                        final_risk_usd=pos.final_risk_usd,
                        leverage=pos.leverage,
                        open_time=pos.open_time,
                        close_time=int(time.time()),
                        close_reason='SL_OR_TP_AUTO',  # Binance tarafından otomatik kapatılmış
                        pnl_usd=float(pnl_result['pnl_usd']) if pnl_result else realized_pnl,
                        pnl_percent=float(pnl_result['pnl_percent']) if pnl_result else 0
                    )
                    
                    db.add(history)
                    db.delete(pos)
                    db.commit()
                    
                    closed_count += 1
                    
                    logger.info(f"✅ {symbol} senkronizasyon ile kapatıldı (PnL: ${history.pnl_usd:.2f})")
                    
                    # Telegram bildirimi
                    try:
                        telegram_notifier.send_position_closed_alert({
                            'symbol': history.symbol,
                            'direction': history.direction,
                            'close_reason': 'SL/TP Otomatik',
                            'entry_price': history.entry_price,
                            'close_price': history.close_price,
                            'pnl_percent': history.pnl_percent
                        })
                    except Exception as tel_e:
                        logger.error(f"Telegram bildirimi hatası: {tel_e}")
                    
                except Exception as e:
                    logger.error(f"❌ {symbol} senkronizasyon hatası: {e}", exc_info=True)
                    db.rollback()
        
        return closed_count
        
    except Exception as e:
        logger.error(f"❌ Senkronizasyon genel hatası: {e}", exc_info=True)
        if db:
            db.rollback()
        return 0
    finally:
        if db:
            db_session.remove()
# -----------------------------------------------


# --- Ana İzleme Fonksiyonu (Güncellendi) ---

def continuously_check_positions(
    realtime_manager: RealTimeDataManager,
    open_positions_lock: Lock,
    stop_event: Event,
    config: object
):
    """
    Ana trade manager thread'i. DB'deki pozisyonları izler,
    RealTimeManager'dan (WebSocket) anlık fiyatları alır,
    TRAILING STOP ve SL/TP kontrollerini yapar, kapananları 'trade_history'ye taşır.
    """
    sleep_duration = getattr(config, 'TRADE_MANAGER_SLEEP_SECONDS', 3)
    logger.info(f"✅ Trade Manager thread'i başlatıldı. Her {sleep_duration} saniyede bir DB/Cache kontrolü yapılacak.")
    
    # v5.0 AUTO-PILOT: Senkronizasyon sayacı (her 10 döngüde bir senkronize et)
    sync_counter = 0
    sync_interval = 10  # Her 30 saniyede bir (3sn * 10 = 30sn)
    
    # v7.1 YENİ: Margin raporu sayacı (her 20 döngüde bir rapor)
    margin_report_counter = 0
    margin_report_interval = 20  # Her 60 saniyede bir (3sn * 20 = 60sn)
    
    # Margin tracker başlat
    try:
        from src.trade_manager.margin_tracker import create_margin_tracker
        margin_tracker = create_margin_tracker(config)
        margin_tracking_enabled = True
        logger.info("📊 Margin tracking sistemi aktif")
    except Exception as mt_e:
        logger.warning(f"⚠️ Margin tracker başlatılamadı: {mt_e}")
        margin_tracking_enabled = False
    
    while not stop_event.is_set():
        # v5.0: Binance senkronizasyonu (her X döngüde bir)
        sync_counter += 1
        if sync_counter >= sync_interval:
            try:
                closed_count = sync_positions_with_binance(open_positions_lock)
                if closed_count > 0:
                    logger.info(f"🔄 Senkronizasyon: {closed_count} pozisyon kapatıldı")
                sync_counter = 0
            except Exception as sync_e:
                logger.error(f"Senkronizasyon hatası: {sync_e}", exc_info=True)
        
        # v7.1 YENİ: Periyodik margin raporu
        margin_report_counter += 1
        if margin_tracking_enabled and margin_report_counter >= margin_report_interval:
            try:
                db_for_margin = db_session()
                try:
                    margin_tracker.log_margin_health_report(db_for_margin)
                    margin_report_counter = 0
                except Exception as margin_e:
                    logger.error(f"Margin raporu hatası: {margin_e}", exc_info=True)
                finally:
                    db_session.remove()
            except Exception as e:
                logger.error(f"Margin raporu DB erişim hatası: {e}", exc_info=True)
        
        positions_to_close = []   # (pos_obj, close_reason, close_price)
        positions_to_update = []  # (pos_obj, new_sl, new_hwm) TSL için
        positions_to_check = []
        db = None

        try:
            # --- Adım 1: Kilit altında DB'den pozisyonları oku ---
            with open_positions_lock:
                db = db_session()
                positions_to_check = db.query(OpenPosition).all()
            
            if not positions_to_check:
                logger.debug("TradeManager: İzlenecek açık pozisyon yok.")
                stop_event.wait(sleep_duration)
                continue
                
            logger.info(f"TradeManager: {len(positions_to_check)} adet açık pozisyon kontrol ediliyor...")

            # --- YENİ: Aşama 3 - Gerçek Zamanlı Portföy Değerleme Motoru (BINANCE API) ---
            total_unrealized_pnl_usd = 0.0
            total_margin_used = 0.0
            live_positions_details = []
            
            # Binance'den gerçek pozisyon verilerini çek
            binance_positions_map = {}
            try:
                from src.trade_manager.executor import get_executor
                executor = get_executor()  # Argüman YOK! Singleton pattern kullanılıyor
                binance_positions = executor.get_position_risk()  # Leverage, margin, PnL dahil
                
                # Symbol bazında map oluştur
                binance_positions_map = {p['symbol']: p for p in binance_positions}
                
                if binance_positions:
                    logger.debug(f"📊 Binance'den {len(binance_positions)} pozisyon bilgisi alındı")
            except Exception as e_binance:
                logger.warning(f"⚠️ Binance pozisyon verileri alınamadı, manuel hesaplama yapılacak: {e_binance}")
            # ----------------------------------------------------------------

            # --- Adım 2: Pozisyon Kontrolü (Binance Verisiyle) ---
            for pos in positions_to_check:
                if stop_event.is_set(): break
                
                symbol = pos.symbol
                
                # 🆕 v7.1: SİMÜLASYON POZİSYONLARINI GHOST KONTROLÜNDEN MUAF TUT
                is_simulated = (pos.status == 'SIMULATED')
                
                if is_simulated:
                    # Simülasyon pozisyonu - Binance'de olmayacak, ghost kontrolü yapma
                    logger.debug(f"🎮 {symbol} simülasyon pozisyonu, Binance kontrolü atlanıyor")
                    # Sadece fiyat bazlı SL/TP kontrolü yapılacak
                else:
                    # GERÇEK POZİSYON - Grace period ve ghost kontrolü yap
                    # 🆕 GRACE PERIOD: Yeni açılan pozisyonları ghost kontrolünden koru
                    NEWLY_OPENED_GRACE_PERIOD = 60  # 60 saniye koruma süresi
                    position_age = time.time() - pos.open_time
                    
                    if position_age < NEWLY_OPENED_GRACE_PERIOD:
                        # Pozisyon çok yeni, Binance API henüz güncellememiş olabilir
                        logger.debug(f"🆕 {symbol} yeni açıldı ({position_age:.0f}s), ghost kontrolü atlanıyor")
                        # Ghost kontrolü yapma, normal kontrollere geç
                    else:
                        # ⚠️ KRİTİK: Database'de var ama Binance'de kapanmış pozisyonları temizle
                        binance_position = binance_positions_map.get(symbol)
                        if binance_position:
                            # Binance pozisyonu miktarını kontrol et
                            position_amt = float(binance_position.get('positionAmt', 0))
                            if abs(position_amt) < 0.00001:  # Pozisyon kapalı
                                logger.warning(f"👻 {symbol} database'de var ama Binance'de KAPALI! Temizleniyor...")
                                positions_to_close.append((pos, 'BINANCE_CLOSED', None))
                                continue
                        else:
                            # Binance'de hiç pozisyon yok
                            logger.warning(f"👻 {symbol} database'de var ama Binance'de BULUNAMADI! Temizleniyor...")
                            positions_to_close.append((pos, 'BINANCE_CLOSED', None))
                            continue
                
                current_price = realtime_manager.get_price(symbol)
                
                if current_price is None:
                    # WebSocket'ten henüz veri gelmemişse API'den çek (fallback)
                    logger.debug(f"TradeManager: {symbol} WS cache'de yok, API'den çekiliyor...")
                    current_price = binance_fetcher.get_current_price(symbol)
                    if current_price is None:
                         logger.warning(f"TradeManager: {symbol} için fiyat alınamadı, atlanıyor.")
                         continue
                
                # --- Pozisyon Değerleme: Binance Verisi Varsa Kullan ---
                try:
                    binance_pos = binance_positions_map.get(symbol)
                    
                    if binance_pos:
                        # 🎯 BİNANCE VERİSİ KULLANILIYOR (GERÇEK DEĞERLER)
                        pnl_usd = float(binance_pos.get('unRealizedProfit', 0))
                        initial_margin = float(binance_pos.get('isolatedMargin', 0))
                        notional_value_usd = abs(float(binance_pos.get('notional', 0)))
                        leverage = int(binance_pos.get('leverage', pos.leverage))
                        position_size = abs(float(binance_pos.get('positionAmt', pos.position_size_units)))
                        mark_price = float(binance_pos.get('markPrice', current_price))
                        entry_price = float(binance_pos.get('entryPrice', pos.entry_price))
                        
                        # Binance'in liquidation price'ı varsa kullan
                        liq_price = float(binance_pos.get('liquidationPrice', 0))
                        
                        # PnL yüzdesi (Binance margin'ına göre)
                        if initial_margin > 0:
                            pnl_percent = (pnl_usd / initial_margin) * 100
                        else:
                            pnl_percent = 0
                        
                        logger.debug(f"✅ {symbol}: Binance verisi kullanıldı - PnL=${pnl_usd:.2f} ({pnl_percent:.2f}%)")
                    
                    else:
                        # ⚠️ MANUEL HESAPLAMA (FALLBACK)
                        logger.debug(f"⚠️ {symbol}: Binance verisi yok, manuel hesaplama yapılıyor")
                        
                        position_size = pos.position_size_units if pos.position_size_units else 0
                        entry_price = pos.entry_price if pos.entry_price else 0
                        leverage = pos.leverage if pos.leverage else 2
                        mark_price = current_price
                        
                        # Notional değer
                        notional_value_usd = position_size * entry_price
                        
                        # GERÇEK MARGIN
                        initial_margin = notional_value_usd / leverage
                        
                        # Anlık pozisyon değeri
                        current_notional_value = position_size * current_price
                        
                        # PnL Hesaplama
                        if pos.direction and pos.direction.upper() == 'LONG':
                            pnl_usd = current_notional_value - notional_value_usd
                        elif pos.direction and pos.direction.upper() == 'SHORT':
                            pnl_usd = notional_value_usd - current_notional_value
                        else:
                            pnl_usd = 0
                        
                        # PnL Yüzdesi
                        if initial_margin > 0:
                            pnl_percent = (pnl_usd / initial_margin) * 100
                        else:
                            pnl_percent = 0
                        
                        # Tasfiye fiyatı
                        if leverage > 0:
                            liquidation_distance_percent = 1.0 / leverage
                            if pos.direction and pos.direction.upper() == 'LONG':
                                liq_price = entry_price * (1 - liquidation_distance_percent)
                            elif pos.direction and pos.direction.upper() == 'SHORT':
                                liq_price = entry_price * (1 + liquidation_distance_percent)
                            else:
                                liq_price = 0
                        else:
                            liq_price = 0
                    
                    # Pozisyon detaylarını listeye ekle
                    live_positions_details.append({
                        'symbol': symbol,
                        'direction': pos.direction,
                        'entry_price': entry_price,
                        'mark_price': mark_price,
                        'pnl_usd': pnl_usd,
                        'pnl_percent': pnl_percent,
                        'liq_price': liq_price,
                        'margin': initial_margin,
                        'notional': notional_value_usd,
                        'leverage': leverage,
                        'position_size': position_size
                    })
                    
                    # Toplam değerlere ekle
                    total_unrealized_pnl_usd += pnl_usd
                    total_margin_used += initial_margin
                    
                except Exception as e_valuation:
                    logger.error(f"Pozisyon değerleme hatası ({symbol}): {e_valuation}", exc_info=True)
                # -----------------------------------------------------------------
                
                close_reason = None
                
                # --- Adım 2a: Partial TP-1 Kontrolü (v4.0 Enhanced) ---
                if (pos.partial_tp_1_price is not None and 
                    not pos.partial_tp_1_taken and 
                    pos.partial_tp_1_percent is not None):
                    
                    partial_hit = False
                    if pos.direction.upper() == 'LONG' and current_price >= pos.partial_tp_1_price:
                        partial_hit = True
                    elif pos.direction.upper() == 'SHORT' and current_price <= pos.partial_tp_1_price:
                        partial_hit = True
                    
                    if partial_hit:
                        # Kısmi kar al: Pozisyonun bir kısmını kapat
                        partial_size = pos.position_size_units * (pos.partial_tp_1_percent / 100.0)
                        remaining_size = pos.position_size_units - partial_size
                        
                        # Kısmi PnL hesapla
                        partial_pnl = _calculate_pnl(
                            pos.entry_price, 
                            current_price, 
                            pos.direction, 
                            partial_size
                        )
                        
                        logger.info(f"🎯 PARTIAL TP-1 HIT! {pos.symbol} ({pos.direction})")
                        logger.info(f"   Kapanan: {partial_size:.4f} ({pos.partial_tp_1_percent:.0f}%)")
                        logger.info(f"   Kalan: {remaining_size:.4f} ({100-pos.partial_tp_1_percent:.0f}%)")
                        if partial_pnl:
                            logger.info(f"   Kısmi PnL: {float(partial_pnl['pnl_usd']):.2f} USD ({float(partial_pnl['pnl_percent']):.2f}%)")
                        
                        # DB güncellemesi için işaretle
                        positions_to_update.append((pos, None, None, True, remaining_size, current_price))
                        continue  # Bu cycle'da başka kontrol yapma
                
                # --- Adım 2a-2: Partial TP-2 Kontrolü (v8.1 NEW) ---
                if (pos.partial_tp_2_price is not None and 
                    pos.partial_tp_1_taken and  # TP1 alınmış olmalı
                    not pos.partial_tp_2_taken and 
                    pos.partial_tp_2_percent is not None):
                    
                    partial_hit_2 = False
                    if pos.direction.upper() == 'LONG' and current_price >= pos.partial_tp_2_price:
                        partial_hit_2 = True
                    elif pos.direction.upper() == 'SHORT' and current_price <= pos.partial_tp_2_price:
                        partial_hit_2 = True
                    
                    if partial_hit_2:
                        # TP2: Kalan pozisyonun tamamını kapat (genelde %100 of remaining)
                        partial_size_2 = pos.position_size_units  # Kalan tüm pozisyon
                        
                        # Kısmi PnL hesapla
                        partial_pnl_2 = _calculate_pnl(
                            pos.entry_price, 
                            current_price, 
                            pos.direction, 
                            partial_size_2
                        )
                        
                        logger.info(f"🎯🎯 PARTIAL TP-2 HIT! {pos.symbol} ({pos.direction})")
                        logger.info(f"   Kapanan: {partial_size_2:.4f} (FULL EXIT - Remaining {pos.partial_tp_2_percent:.0f}%)")
                        if partial_pnl_2:
                            logger.info(f"   Kısmi PnL: {float(partial_pnl_2['pnl_usd']):.2f} USD ({float(partial_pnl_2['pnl_percent']):.2f}%)")
                        
                        # TP2 hit = pozisyon tamamen kapanıyor
                        positions_to_close.append((pos, 'PARTIAL_TP_2', current_price))
                        continue  # Bu cycle'da başka kontrol yapma
                
                # --- Adım 2b: SL/TP Kontrolü ---
                if pos.direction.upper() == 'LONG':
                    if current_price <= pos.sl_price: close_reason = 'STOP_LOSS'
                    elif current_price >= pos.tp_price: close_reason = 'TAKE_PROFIT'
                elif pos.direction.upper() == 'SHORT':
                    if current_price >= pos.sl_price: close_reason = 'STOP_LOSS'
                    elif current_price <= pos.tp_price: close_reason = 'TAKE_PROFIT'

                if close_reason:
                    positions_to_close.append((pos, close_reason, current_price))
                    continue # Pozisyon kapandıysa TSL'e bakmaya gerek yok

                # --- Adım 2c: Trailing Stop Kontrolü (Eğer pozisyon kapanmadıysa) ---
                if pos.trailing_stop_active:
                    new_sl, new_hwm = _update_trailing_stop(pos, current_price)
                    if new_sl is not None:
                        # v5.0 AUTO-PILOT: Binance'de SL emrini güncelle
                        executor = get_executor()
                        if executor:
                            try:
                                logger.info(f"   🔄 {pos.symbol} Trailing SL güncelleniyor: {pos.sl_price:.4f} → {new_sl:.4f}")
                                
                                # 1. Eski SL emrini iptal et
                                if pos.sl_order_id:
                                    executor.cancel_order(pos.symbol, pos.sl_order_id)
                                
                                # 2. Yeni SL emrini yerleştir (fiyatı yuvarla!)
                                close_side = 'SELL' if pos.direction == 'LONG' else 'BUY'
                                rounded_sl = executor.round_price(pos.symbol, new_sl)
                                
                                new_sl_order = executor.client.futures_create_order(
                                    symbol=pos.symbol,
                                    side=close_side,
                                    type='STOP_MARKET',
                                    quantity=executor.round_quantity(pos.symbol, pos.position_size_units),
                                    stopPrice=rounded_sl,
                                    reduceOnly=True,
                                    timeInForce='GTE_GTC'
                                )
                                
                                # Güncellenecekler listesine ekle (yeni order_id ile)
                                positions_to_update.append((pos, rounded_sl, new_hwm, False, None, new_sl_order['orderId']))
                                
                                logger.info(f"   ✅ {pos.symbol} Trailing SL güncellendi! Yeni emir: {new_sl_order['orderId']} (SL: {rounded_sl})")
                                
                            except Exception as tsl_e:
                                logger.error(f"   ❌ {pos.symbol} Trailing SL güncellenemedi: {tsl_e}", exc_info=True)
                        else:
                            # Executor yoksa sadece DB'yi güncelle
                            positions_to_update.append((pos, new_sl, new_hwm, False, None, None))
                    elif new_hwm != pos.high_water_mark:
                        # Sadece HWM güncelleniyor
                        positions_to_update.append((pos, None, new_hwm, False, None, None))

            # --- YENİ: Aşama 3 - Anlık Portföy Durumu Loglama (BINANCE DATA) ---
            if live_positions_details:
                # Binance verisi kullanıldı mı kontrol et
                using_binance_data = any(binance_positions_map.get(d['symbol']) for d in live_positions_details)
                data_source = "PORTFÖY (Binance API)" if using_binance_data else "PORTFÖY (Manuel Hesap)"
                
                logger.info(f"💼 {data_source}:")
                logger.info(f"   📊 Açık Pozisyon: {len(live_positions_details)}")
                logger.info(f"   💰 Kullanılan Margin: ${total_margin_used:.2f}")
                
                pnl_percent_total = (total_unrealized_pnl_usd/total_margin_used*100) if total_margin_used > 0 else 0
                pnl_emoji = "📈" if total_unrealized_pnl_usd >= 0 else "📉"
                logger.info(f"   {pnl_emoji} Gerçekleşmemiş K/Z: ${total_unrealized_pnl_usd:.2f} ({pnl_percent_total:.2f}%)")
                
                for detail in live_positions_details:
                    logger.debug(f"   {detail['symbol']} {detail['direction']}:")
                    logger.debug(f"      Giriş: ${detail['entry_price']:.4f} → Şimdi: ${detail['mark_price']:.4f}")
                    logger.debug(f"      Notional: ${detail['notional']:.2f} | Margin: ${detail['margin']:.2f} | Kaldıraç: {detail['leverage']}x")
                    
                    pnl_sign = "+" if detail['pnl_usd'] >= 0 else ""
                    logger.debug(f"      PnL: {pnl_sign}${detail['pnl_usd']:.2f} ({pnl_sign}{detail['pnl_percent']:.2f}%)")
                    logger.debug(f"      Likidasyon: ${detail['liq_price']:.4f}")
            # -----------------------------------------------------------------

            # --- Adım 3: Kilit altında DB Güncelleme (TSL, Kapatma, Kaydetme) ---
            if positions_to_close or positions_to_update:
                
                with open_positions_lock:
                    logger.debug(f"TradeManager: Kilit alındı. Kapanacak: {len(positions_to_close)}, Güncellenecek: {len(positions_to_update)}")
                    if db is None: db = db_session()
                    
                    closed_positions_details_for_notify = []

                    # 1. Kapanacakları işle
                    for pos, close_reason, close_price in positions_to_close:
                        pos_in_db = db.get(OpenPosition, pos.id) # DB'deki en güncel hali al
                        if pos_in_db is None:
                            logger.debug(f"Pozisyon ID {pos.id} zaten kapatılmış, atlıyoruz")
                            continue # Zaten kapatılmış
                        
                        try:
                            # 🔥 KRİTİK: BİNANCE'DE POZİSYONU KAPAT!
                            # ANCAK: BINANCE_CLOSED ise zaten kapanmış, emir gönderme!
                            executor = get_executor()
                            if executor and close_reason != 'BINANCE_CLOSED':
                                try:
                                    logger.info(f"🔥 {pos_in_db.symbol} pozisyonu Binance'de kapatılıyor ({close_reason})...")
                                    
                                    # MARKET emri ile pozisyonu kapat
                                    close_order = executor.close_position_market(
                                        symbol=pos_in_db.symbol,
                                        quantity_units=pos_in_db.position_size_units
                                    )
                                    
                                    if close_order:
                                        logger.info(f"✅ {pos_in_db.symbol} Binance'de kapatıldı! Emir ID: {close_order.get('orderId', 'N/A')}")
                                        # Gerçek kapanış fiyatını al (eğer varsa)
                                        if 'avgPrice' in close_order and close_order['avgPrice']:
                                            actual_close_price = float(close_order['avgPrice'])
                                            close_price = actual_close_price
                                    else:
                                        logger.error(f"❌ {pos_in_db.symbol} Binance'de kapatılamadı!")
                                        
                                except Exception as close_ex:
                                    logger.error(f"❌ {pos_in_db.symbol} kapatma hatası: {close_ex}", exc_info=True)
                            elif close_reason == 'BINANCE_CLOSED':
                                # Pozisyon zaten Binance'de kapanmış, gerçek kapanış fiyatını bul
                                logger.info(f"👻 {pos_in_db.symbol} Binance'de zaten kapanmış, gerçek kapanış fiyatı aranıyor...")
                                
                                # 1. Önce Binance trades history'den gerçek kapanış fiyatını çek
                                real_close_price = _get_real_close_price_from_binance(
                                    symbol=pos_in_db.symbol,
                                    open_time_ms=pos_in_db.open_time * 1000,  # Unix timestamp → ms
                                    entry_price=pos_in_db.entry_price
                                )
                                
                                if real_close_price:
                                    close_price = real_close_price
                                    logger.info(f"✅ {pos_in_db.symbol} gerçek kapanış fiyatı bulundu: ${close_price:.6f}")
                                else:
                                    # 2. Trades history'de bulunamazsa, güncel fiyatı kullan
                                    logger.warning(f"⚠️ {pos_in_db.symbol} trades history'de bulunamadı, güncel fiyat kullanılıyor")
                                    current_price = None
                                    try:
                                        if realtime_manager:
                                            current_price = realtime_manager.get_price(pos_in_db.symbol)
                                    except Exception as _e:
                                        logger.debug(f"Realtime fiyat okunamadı, REST'e düşüyoruz: {_e}")
                                    if not current_price:
                                        try:
                                            current_price = get_current_price(pos_in_db.symbol)
                                        except Exception as _e2:
                                            logger.error(f"REST fiyat alınamadı: {_e2}")
                                    
                                    if current_price:
                                        close_price = current_price
                                        logger.info(f"📊 {pos_in_db.symbol} güncel fiyat: ${close_price:.6f}")
                                    else:
                                        # 3. Son çare: entry price (en kötü senaryo)
                                        logger.error(f"❌ {pos_in_db.symbol} için güncel fiyat da alınamadı! Entry price kullanılıyor (fallback)")
                                        close_price = pos_in_db.entry_price
                            else:
                                logger.warning(f"⚠️ Executor yok, {pos_in_db.symbol} sadece DB'den silinecek")
                            
                            pnl_result = _calculate_pnl(pos_in_db.entry_price, close_price, pos_in_db.direction, pos_in_db.position_size_units)
                            pnl_usd = float(pnl_result['pnl_usd']) if pnl_result else None
                            pnl_percent = float(pnl_result['pnl_percent']) if pnl_result else None
                            
                            logger.info(f"=== POZİSYON KAPATILDI ({close_reason}) ===")
                            logger.info(f"   Sembol: {pos_in_db.symbol} ({pos_in_db.direction}) | Giriş: {pos_in_db.entry_price}, Kapanış: {close_price}")
                            if pnl_result: logger.info(f"   PnL: {pnl_usd:.2f} USD ({pnl_percent:.2f}%)")

                            # ✅ FIX: TradeHistory'ye SADECE BİR KERE ekle (duplicate önleme)
                            # Önce aynı pozisyon zaten kaydedilmiş mi kontrol et
                            existing_history = db.query(TradeHistory).filter(
                                TradeHistory.symbol == pos_in_db.symbol,
                                TradeHistory.open_time == pos_in_db.open_time,
                                TradeHistory.entry_price == pos_in_db.entry_price,
                                TradeHistory.close_reason == close_reason
                            ).first()
                            
                            if existing_history:
                                logger.warning(f"⚠️ {pos_in_db.symbol} zaten TradeHistory'de var, duplicate eklenmedi!")
                            else:
                                # Geçmişe Ekle
                                history_entry = TradeHistory(
                                    symbol=pos_in_db.symbol, strategy=pos_in_db.strategy, direction=pos_in_db.direction,
                                    quality_grade=pos_in_db.quality_grade, entry_price=pos_in_db.entry_price,
                                    close_price=close_price, sl_price=pos_in_db.sl_price, tp_price=pos_in_db.tp_price,
                                    position_size_units=pos_in_db.position_size_units, final_risk_usd=pos_in_db.final_risk_usd,
                                    open_time=pos_in_db.open_time, close_time=int(time.time()),
                                    close_reason=close_reason, pnl_usd=pnl_usd, pnl_percent=pnl_percent,
                                    leverage=pos_in_db.leverage  # YENİ: Aşama 2
                                )
                                db.add(history_entry)
                                notify_detail = history_entry.__dict__.copy()
                                # Telegram için ek bilgiler
                                notify_detail['position_size_usd'] = pos_in_db.entry_price * pos_in_db.position_size_units
                                closed_positions_details_for_notify.append(notify_detail)
                                logger.debug(f"✅ {pos_in_db.symbol} TradeHistory'ye eklendi")

                            # Açık Pozisyonlardan Sil
                            db.delete(pos_in_db)
                        except Exception as e:
                             logger.error(f"Pozisyon {pos.symbol} kapatılırken/kaydedilirken DB hatası: {e}", exc_info=True)
                             db.rollback()

                    # 2. Güncellemeleri işle (TSL + Partial TP)
                    partial_tp_notifications = []
                    for update_tuple in positions_to_update:
                        # v5.0 format: (pos, new_sl, new_hwm, is_partial_tp, remaining_size, new_sl_order_id)
                        pos = update_tuple[0]
                        new_sl = update_tuple[1] if len(update_tuple) > 1 else None
                        new_hwm = update_tuple[2] if len(update_tuple) > 2 else None
                        is_partial_tp = update_tuple[3] if len(update_tuple) > 3 else False
                        remaining_size = update_tuple[4] if len(update_tuple) > 4 else None
                        new_sl_order_id = update_tuple[5] if len(update_tuple) > 5 else None  # v5.0: Yeni SL emir ID
                        
                        # Kapananlar listesinde olmadığından emin ol
                        if pos in [p[0] for p in positions_to_close]: continue
                        
                        pos_in_db = db.get(OpenPosition, pos.id)
                        if pos_in_db is None: continue
                        
                        try:
                            # Trailing Stop güncellemesi
                            if new_sl is not None:
                                pos_in_db.sl_price = new_sl
                                if new_sl_order_id:  # v5.0: Emir ID'yi güncelle
                                    pos_in_db.sl_order_id = new_sl_order_id
                                logger.debug(f"   DB: {pos.symbol} SL güncellendi: {new_sl:.4f}")
                            
                            if new_hwm is not None:
                                pos_in_db.high_water_mark = new_hwm
                                logger.debug(f"   DB: {pos.symbol} HWM güncellendi: {new_hwm:.4f}")
                            
                            # Partial TP işlemi
                            if is_partial_tp and remaining_size is not None:
                                partial_size = pos_in_db.position_size_units - remaining_size
                                partial_price = update_tuple[5] if len(update_tuple) > 5 else current_price  # Kapanış fiyatı
                                partial_pnl = _calculate_pnl(
                                    pos_in_db.entry_price,
                                    partial_price,
                                    pos_in_db.direction,
                                    partial_size
                                )
                                
                                # Kısmi kar history'ye ekle
                                partial_history = TradeHistory(
                                    symbol=pos_in_db.symbol,
                                    strategy=pos_in_db.strategy,
                                    direction=pos_in_db.direction,
                                    quality_grade=pos_in_db.quality_grade,
                                    entry_price=pos_in_db.entry_price,
                                    close_price=partial_price,
                                    sl_price=pos_in_db.sl_price,
                                    tp_price=pos_in_db.partial_tp_1_price,
                                    position_size_units=partial_size,
                                    final_risk_usd=pos_in_db.final_risk_usd * (pos_in_db.partial_tp_1_percent / 100.0),
                                    open_time=pos_in_db.open_time,
                                    close_time=int(time.time()),
                                    close_reason='PARTIAL_TP_1',
                                    pnl_usd=float(partial_pnl['pnl_usd']) if partial_pnl else None,
                                    pnl_percent=float(partial_pnl['pnl_percent']) if partial_pnl else None,
                                    leverage=pos_in_db.leverage  # YENİ: Aşama 2
                                )
                                db.add(partial_history)
                                
                                # OpenPosition'ı güncelle
                                pos_in_db.partial_tp_1_taken = True
                                pos_in_db.position_size_units = remaining_size
                                pos_in_db.remaining_position_size = remaining_size
                                # 🔥 FIX: Risk miktarını da güncelle (TP1 sonrası %50 kaldı ise risk yarıya iner)
                                remaining_percent = 100.0 - pos_in_db.partial_tp_1_percent
                                pos_in_db.final_risk_usd = pos_in_db.final_risk_usd * (remaining_percent / 100.0)
                                
                                # 🔥 FIX: SL'yi Break-Even'a çek (risk-free trade)
                                logger.info(f"   📌 SL güncelleniyor: {pos_in_db.sl_price:.6f} → {pos_in_db.entry_price:.6f} (Break-Even)")
                                pos_in_db.sl_price = pos_in_db.entry_price
                                
                                db.merge(pos_in_db)
                                
                                # Bildirim için kaydet
                                partial_tp_notifications.append({
                                    'symbol': pos_in_db.symbol,
                                    'direction': pos_in_db.direction,
                                    'partial_percent': pos_in_db.partial_tp_1_percent,
                                    'partial_price': partial_price,
                                    'pnl_usd': float(partial_pnl['pnl_usd']) if partial_pnl else 0,
                                    'pnl_percent': float(partial_pnl['pnl_percent']) if partial_pnl else 0,
                                    'remaining_size': remaining_size
                                })
                                
                                logger.info(f"✅ {pos_in_db.symbol} Partial TP-1 DB'ye kaydedildi")
                            
                            # TSL güncellemesi
                            elif new_sl is not None or new_hwm != pos_in_db.high_water_mark:
                                if new_sl is not None:
                                    logger.info(f"   TRAILING STOP GÜNCELLENDİ: {pos_in_db.symbol}")
                                    logger.info(f"   Eski SL: {pos_in_db.sl_price:.4f} -> Yeni SL: {new_sl:.4f}")
                                    pos_in_db.sl_price = new_sl
                                if new_hwm != pos_in_db.high_water_mark:
                                    pos_in_db.high_water_mark = new_hwm
                                db.merge(pos_in_db)
                                
                        except Exception as e:
                             logger.error(f"Pozisyon {pos.symbol} güncellenirken DB hatası: {e}", exc_info=True)
                             db.rollback()

                    db.commit() # Tüm değişiklikleri onayla
                
                # (Kilit bitti)

                # --- Adım 4: Bildirim Gönderme (Kilitsiz) ---
                if telegram_notifier and hasattr(telegram_notifier, 'send_message'):
                    # Tam kapanış bildirimleri
                    if closed_positions_details_for_notify:
                        for closed_detail in closed_positions_details_for_notify:
                            try:
                                close_message = telegram_notifier.format_close_message(closed_detail)
                                telegram_notifier.send_message(close_message)
                            except Exception as e_notify:
                                 logger.error(f"Kapanış bildirimi gönderilemedi ({closed_detail.get('symbol')}): {e_notify}")
                    
                    # Partial TP bildirimleri
                    if partial_tp_notifications:
                        for ptp in partial_tp_notifications:
                            try:
                                partial_percent_str = f"{ptp['partial_percent']:.0f}%"
                                partial_price_str = f"{ptp['partial_price']:.6f}"
                                pnl_str = f"{ptp['pnl_usd']:.2f} USD ({ptp['pnl_percent']:.2f}%)"
                                remaining_str = f"{ptp['remaining_size']:.4f}"
                                
                                ptp_msg = (
                                    f"🎯 *PARTIAL TP\\-1 HIT*\n\n"
                                    f"Sembol: `{telegram_notifier.escape_markdown_v2(ptp['symbol'])}`\n"
                                    f"Yön: {telegram_notifier.escape_markdown_v2(ptp['direction'])}\n"
                                    f"Kapanan: {telegram_notifier.escape_markdown_v2(partial_percent_str)}\n"
                                    f"Fiyat: {telegram_notifier.escape_markdown_v2(partial_price_str)}\n"
                                    f"PnL: {telegram_notifier.escape_markdown_v2(pnl_str)}\n"
                                    f"Kalan Pozisyon: {telegram_notifier.escape_markdown_v2(remaining_str)}"
                                )
                                telegram_notifier.send_message(ptp_msg)
                            except Exception as e_notify:
                                logger.error(f"Partial TP bildirimi gönderilemedi: {e_notify}")


        except Exception as e:
            logger.error(f"❌ Trade Manager ana döngüsünde kritik hata: {e}", exc_info=True)
            if db: db.rollback()
            stop_event.wait(60)
        finally:
            if db: db_session.remove()
            
        stop_event.wait(sleep_duration)

    logger.info("🛑 Trade Manager thread'i durduruldu.")

def monitor_positions_loop():
    """
    Açık pozisyonları sürekli takip eder, SL/TP kontrolü yapar.
    """
    logger.info("🔄 Trade Manager başlatıldı - pozisyon takibi aktif")
    
    while True:
        try:
            from main_orchestrator import open_positions_lock
            
            # Pozisyonları güvenli şekilde oku (YENİ: context manager)
            with open_positions_lock:
                with get_db_session() as db:  # YENİ
                    open_positions = db.query(OpenPosition).all()
                    positions_data = [
                        {
                            'id': pos.id,
                            'symbol': pos.symbol,
                            'direction': pos.direction,
                            'entry_price': pos.entry_price,
                            'sl_price': pos.sl_price,
                            'tp_price': pos.tp_price,
                            'position_size': pos.position_size,
                            'planned_risk_percent': pos.planned_risk_percent,
                            'quality_grade': pos.quality_grade,
                            # v10.4: Margin-based TP/SL alanları
                            'initial_margin': getattr(pos, 'initial_margin', None),
                            'tp_margin': getattr(pos, 'tp_margin', None),
                            'sl_margin': getattr(pos, 'sl_margin', None)
                        }
                        for pos in open_positions
                    ]
            
            # Lock dışında fiyat kontrolü yap (Binance API çağrıları yavaş)
            for pos_data in positions_data:
                try:
                    current_price = get_current_price(pos_data['symbol'])
                    if current_price is None:
                        continue
                    
                    should_close = False
                    close_reason = ""
                    
                    # v10.4: Margin-based TP/SL kontrolü (fast mode için)
                    if pos_data.get('initial_margin') is not None and pos_data.get('tp_margin') is not None:
                        # Margin-based sistem aktif
                        unrealized_pnl = 0.0
                        if pos_data['direction'] == 'LONG':
                            unrealized_pnl = pos_data['position_size'] * (current_price - pos_data['entry_price'])
                        else:  # SHORT
                            unrealized_pnl = pos_data['position_size'] * (pos_data['entry_price'] - current_price)
                        
                        current_margin = pos_data['initial_margin'] + unrealized_pnl
                        
                        # TP kontrolü: margin >= tp_margin
                        if current_margin >= pos_data['tp_margin']:
                            should_close = True
                            close_reason = f"TP (Margin: ${current_margin:.2f} >= ${pos_data['tp_margin']:.2f})"
                        # SL kontrolü: margin <= sl_margin
                        elif current_margin <= pos_data['sl_margin']:
                            should_close = True
                            close_reason = f"SL (Margin: ${current_margin:.2f} <= ${pos_data['sl_margin']:.2f})"
                    else:
                        # Eski sistem: Price-based TP/SL kontrolü
                        if pos_data['direction'] == 'LONG':
                            if current_price <= pos_data['sl_price']:
                                should_close = True
                                close_reason = "SL"
                            elif current_price >= pos_data['tp_price']:
                                should_close = True
                                close_reason = "TP"
                        else:  # SHORT
                            if current_price >= pos_data['sl_price']:
                                should_close = True
                                close_reason = "SL"
                            elif current_price <= pos_data['tp_price']:
                                should_close = True
                                close_reason = "TP"
                    
                    if should_close:
                        # Pozisyon kapatma işlemi lock içinde
                        with open_positions_lock:
                            close_position(pos_data['id'], current_price, close_reason)
                
                except Exception as e:
                    logger.error(f"❌ {pos_data['symbol']} pozisyon kontrolünde hata: {e}", exc_info=True)
                    continue
            
            time.sleep(config.TRADE_MANAGER_SLEEP_SECONDS)
        
        except Exception as e:
            logger.error(f"❌ Trade manager döngüsünde kritik hata: {e}", exc_info=True)
            time.sleep(30)  # Hata durumunda biraz bekle

def close_position(position_id: int, exit_price: float, reason: str):
    """
    Pozisyonu kapatır ve trade history'ye taşır.
    🆕 v9.1 FIX: Artık Binance'de gerçekten pozisyon kapatıyor!
    """
    with get_db_session() as db:  # YENİ: context manager kullan
        position = db.query(OpenPosition).filter_by(id=position_id).first()
        
        if not position:
            logger.warning(f"Kapatılacak pozisyon bulunamadı: ID={position_id}")
            return
        
        # 🆕 STEP 1: BİNANCE'DE GERÇEKTEKİ POZİSYONU KAPAT!
        executor = get_executor()
        if executor and position.status == 'ACTIVE':  # Sadece gerçek pozisyonları kapat
            try:
                symbol_clean = position.symbol.replace('/', '')  # BTCUSDT formatına çevir
                logger.info(f"🔴 {position.symbol} Binance'de kapatılıyor... (Reason: {reason})")
                
                # 🆕 1.1: TP/SL emirlerini iptal et (eğer varsa)
                if reason.startswith('TP'):
                    # TP tetiklendi → SL emrini iptal et
                    if position.sl_order_id:
                        try:
                            executor.client.futures_cancel_order(
                                symbol=symbol_clean,
                                orderId=position.sl_order_id
                            )
                            logger.info(f"   ✅ SL emri iptal edildi: {position.sl_order_id}")
                        except Exception as cancel_err:
                            logger.warning(f"   ⚠️ SL emri iptal edilemedi (zaten dolu olabilir): {cancel_err}")
                
                elif reason.startswith('SL'):
                    # SL tetiklendi → TP emrini iptal et
                    if position.tp_order_id:
                        try:
                            executor.client.futures_cancel_order(
                                symbol=symbol_clean,
                                orderId=position.tp_order_id
                            )
                            logger.info(f"   ✅ TP emri iptal edildi: {position.tp_order_id}")
                        except Exception as cancel_err:
                            logger.warning(f"   ⚠️ TP emri iptal edilemedi (zaten dolu olabilir): {cancel_err}")
                
                # 1.2: Market emri ile pozisyonu kapat
                close_side = 'SELL' if position.direction == 'LONG' else 'BUY'
                close_order = executor.client.futures_create_order(
                    symbol=symbol_clean,
                    side=close_side,
                    type='MARKET',
                    quantity=position.position_size_units,
                    reduceOnly=True  # Sadece mevcut pozisyonu kapat
                )
                
                # Gerçek kapanış fiyatını al
                if 'avgPrice' in close_order and close_order['avgPrice']:
                    exit_price = float(close_order['avgPrice'])
                    logger.info(f"✅ {position.symbol} Binance'de kapatıldı! Gerçek fiyat: {exit_price}")
                else:
                    logger.warning(f"⚠️ Kapanış fiyatı alınamadı, tahmin edilen fiyat kullanılıyor: {exit_price}")
                
            except BinanceAPIException as api_e:
                logger.error(f"❌ Binance API hatası ({position.symbol}): {api_e}", exc_info=True)
                # Pozisyon zaten kapalı olabilir, devam et
            except Exception as e:
                logger.error(f"❌ {position.symbol} Binance kapatma hatası: {e}", exc_info=True)
        elif position.status == 'SIMULATED':
            logger.info(f"🎮 {position.symbol} simülasyon pozisyonu, Binance işlemi yok")
        else:
            logger.warning(f"⚠️ Executor yok, {position.symbol} sadece DB'den silinecek")
        
        # STEP 2: PnL hesaplama (orijinal mantık korunuyor)
        size_units = getattr(position, 'position_size_units', getattr(position, 'position_size', 0))
        if position.direction == 'LONG':
            pnl_usd = (exit_price - position.entry_price) * size_units
        else:
            pnl_usd = (position.entry_price - exit_price) * size_units

        cost_basis = position.entry_price * size_units if size_units else 0
        pnl_percent = (pnl_usd / cost_basis * 100) if cost_basis else 0
        
        # STEP 3: Trade history'ye kaydet (duplicate kontrolü ile)
        # Önce aynı pozisyon zaten kaydedilmiş mi kontrol et
        open_time_value = getattr(position, 'open_time', None)
        
        existing_history = db.query(TradeHistory).filter(
            TradeHistory.symbol == position.symbol,
            TradeHistory.entry_price == position.entry_price,
            TradeHistory.close_reason == reason
        )
        
        # open_time varsa daha kesin filtreleme yap
        if open_time_value is not None:
            existing_history = existing_history.filter(TradeHistory.open_time == open_time_value)
        
        existing_history = existing_history.first()
        
        if existing_history:
            logger.warning(f"⚠️ {position.symbol} zaten TradeHistory'de var (close_position), duplicate eklenmedi!")
            trade_history = existing_history  # Telegram için mevcut kaydı kullan
        else:
            trade_history = TradeHistory(
                symbol=position.symbol,
                direction=position.direction,
                entry_price=position.entry_price,
                exit_price=exit_price,
                sl_price=position.sl_price,
                tp_price=position.tp_price,
                position_size_units=size_units,
                pnl_usd=pnl_usd,
                pnl_percent=pnl_percent,
                close_reason=reason,
                open_time=open_time_value if open_time_value else int(time.time()),
                close_time=int(time.time()),
                quality_grade=getattr(position, 'quality_grade', None),
                planned_risk_percent=getattr(position, 'planned_risk_percent', None),
                confluence_score=getattr(position, 'confluence_score', None),  # 🆕 v11.3
                htf_score=getattr(position, 'htf_score', None),  # 🆕 v11.3
                ltf_score=getattr(position, 'ltf_score', None),  # 🆕 v11.3
                strategy=getattr(position, 'strategy', None)  # ✅ FIX: strategy eklendi
            )
            db.add(trade_history)
            logger.debug(f"✅ {position.symbol} TradeHistory'ye eklendi (close_position)")
        
        # STEP 4: Açık pozisyonu DB'den sil
        db.delete(position)
        # commit otomatik (context manager)
    
    # STEP 5: Telegram bildirimi
    send_position_closed_alert(trade_history)
    
    logger.info(f"{'🟢' if pnl_usd > 0 else '🔴'} Pozisyon kapatıldı: {position.symbol} {reason} | PnL: ${pnl_usd:.2f} ({pnl_percent:.2f}%)")

# --- Gerçek Emir Fonksiyonları (Yeni) ---

def place_real_order(signal_data):
    """
    Binance Futures'da gerçek emir aç
    
    Args:
        signal_data: {
            'symbol': 'BTCUSDT',
            'direction': 'LONG' or 'SHORT',
            'quantity': 0.001,  # position size (coin amount)
            'entry_price': 50000.0,
            'tp_price': 51000.0,
            'sl_price': 49500.0
        }
    
    Returns:
        {
            'entry_order_id': '...',
            'tp_order_id': '...',
            'sl_order_id': '...'
        } or None on failure
    """
    if not ENABLE_REAL_TRADING:
        logger.warning("ENABLE_REAL_TRADING=False - Sadece simülasyon modu")
        return None
    
    try:
        symbol = signal_data['symbol'].replace('/', '')  # BTCUSDT formatına çevir
        direction = signal_data['direction'].upper()
        quantity = signal_data['quantity']
        entry_price = signal_data['entry_price']
        tp_price = signal_data['tp_price']
        sl_price = signal_data['sl_price']
        
        # Direction -> Binance side mapping
        side = 'BUY' if direction == 'LONG' else 'SELL'
        close_side = 'SELL' if direction == 'LONG' else 'BUY'
        
        logger.info(f"📊 Binance Emir Detayları:")
        logger.info(f"   Symbol: {symbol} | Direction: {direction} ({side})")
        logger.info(f"   Quantity: {quantity} | Entry: ${entry_price}")
        logger.info(f"   TP: ${tp_price} | SL: ${sl_price}")
        
        # 0. Executor kontrol
        executor = get_executor()
        if not executor or not getattr(executor, 'client', None):
            logger.error("❌ Executor client bulunamadı - Binance bağlantısı yok!")
            return None

        # 0.1. Kaldıraç ve Margin Mode ayarla (Config'den)
        leverage = config.FUTURES_LEVERAGE  # 10x (config.py'dan)
        margin_type = 'ISOLATED'  # Isolated mode (güvenlik)
        
        try:
            # Kaldıraç ayarla
            logger.info(f"🔧 {symbol} kaldıraç ayarlanıyor: {leverage}x ({margin_type})")
            executor.set_leverage(symbol, leverage)
            
            # Margin mode ayarla (ISOLATED)
            try:
                executor.client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
                logger.info(f"   ✅ Margin mode: {margin_type}")
            except Exception as margin_error:
                # Eğer zaten ISOLATED ise hata verir, önemli değil
                if 'No need to change margin type' in str(margin_error):
                    logger.debug(f"   ℹ️ Margin mode zaten {margin_type}")
                else:
                    logger.warning(f"   ⚠️ Margin mode ayarlanamadı: {margin_error}")
        except Exception as leverage_error:
            logger.error(f"❌ Kaldıraç ayarlanamadı: {leverage_error}")
            logger.error(f"   Pozisyon açılmayacak - güvenlik riski!")
            return None

        # 0.2. Precision kontrolü - quantity ve fiyatları Binance kurallarına göre yuvarla
        quantity = executor.round_quantity(symbol, quantity)
        tp_price = executor.round_price(symbol, tp_price)
        sl_price = executor.round_price(symbol, sl_price)
        
        logger.info(f"   ✅ Precision uygulandı: Qty={quantity}, TP=${tp_price}, SL=${sl_price}")

        # 1. Market emri ile pozisyon aç (entry_price yerine MARKET kullan, Futures'ta daha hızlı)
        entry_order = executor.client.futures_create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=quantity
        )
        
        logger.info(f"✅ Entry emri FILLED: OrderID={entry_order['orderId']}")
        
        # 2. Take Profit emri (Limit, reduceOnly)
        try:
            tp_order = executor.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='LIMIT',
                quantity=quantity,
                price=tp_price,  # Artık rounded, str() gereksiz
                timeInForce='GTC',
                reduceOnly='true'
            )
            logger.info(f"✅ TP emri yerleştirildi: OrderID={tp_order['orderId']} @ ${tp_price}")
        except Exception as tp_error:
            logger.error(f"❌ TP emri başarısız: {tp_error}")
            logger.warning(f"🔄 Entry pozisyonu kapatılıyor (TP hatası nedeniyle)...")
            try:
                # Entry'yi geri al (ters işlem yap)
                close_order = executor.client.futures_create_order(
                    symbol=symbol,
                    side=close_side,
                    type='MARKET',
                    quantity=quantity
                )
                logger.info(f"✅ Pozisyon kapatıldı (emergency close): {close_order['orderId']}")
            except Exception as close_error:
                logger.critical(f"⚠️⚠️⚠️ POZİSYON AÇIK KALDI - MANUEL KAPATIN! {symbol} {direction} x{quantity}")
                logger.critical(f"Close hatası: {close_error}")
            return None
        
        # 3. Stop Loss emri (STOP_MARKET, reduceOnly)
        try:
            sl_order = executor.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='STOP_MARKET',
                stopPrice=sl_price,  # Artık rounded, str() gereksiz
                quantity=quantity,
                reduceOnly='true'
            )
            logger.info(f"✅ SL emri yerleştirildi: OrderID={sl_order['orderId']} @ ${sl_price}")
        except Exception as sl_error:
            logger.error(f"❌ SL emri başarısız: {sl_error}")
            logger.warning(f"🔄 Pozisyon kapatılıyor (SL hatası nedeniyle) ve TP emri iptal ediliyor...")
            try:
                # TP emrini iptal et
                executor.client.futures_cancel_order(symbol=symbol, orderId=tp_order['orderId'])
                logger.info(f"✅ TP emri iptal edildi: {tp_order['orderId']}")
                
                # Entry'yi geri al (ters işlem yap)
                close_order = executor.client.futures_create_order(
                    symbol=symbol,
                    side=close_side,
                    type='MARKET',
                    quantity=quantity
                )
                logger.info(f"✅ Pozisyon kapatıldı (emergency close): {close_order['orderId']}")
            except Exception as close_error:
                logger.critical(f"⚠️⚠️⚠️ POZİSYON AÇIK KALDI - MANUEL KAPATIN! {symbol} {direction} x{quantity}")
                logger.critical(f"TP var ama SL yok! TP OrderID: {tp_order['orderId']}")
                logger.critical(f"Close hatası: {close_error}")
            return None
        
        logger.info(f"🎯 Pozisyon AÇILDI: {symbol} {direction} x{quantity}")
        
        return {
            'entry_order_id': entry_order['orderId'],
            'tp_order_id': tp_order['orderId'],
            'sl_order_id': sl_order['orderId'],
            'entry_filled_price': entry_order.get('avgPrice', entry_price)
        }
        
    except Exception as e:
        logger.error(f"❌ Binance emir hatası ({signal_data.get('symbol')}): {e}", exc_info=True)
        return None


def cancel_oco_order(symbol, order_list_id):
    """
    OCO emrini iptal et (pozisyon manuel kapatılırsa)
    """
    executor = get_executor()
    if not executor or not getattr(executor, 'client', None):
        logger.error("Executor client yok, OCO iptali yapılamadı")
        return None
    try:
        # Not: Bu sistemde TP/SL ayrı emirlerle veriliyor; ID'ler tutuluyorsa ayrı iptal edilmeli.
        logger.warning("OCO cancel placeholder: TP/SL ayrı emirler, uygun yerden tekil iptal edilmeli")
        return True
    except Exception as e:
        logger.error(f"❌ OCO iptal hatası: {e}", exc_info=True)
        return None