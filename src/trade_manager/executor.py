# src/trade_manager/executor.py

"""
Binance Futures API Executor
Tüm gerçek emir yürütme işlemlerini yöneten izole modül.
"""

import logging
import time
from typing import Optional, Dict, List
from decimal import Decimal, ROUND_DOWN, ROUND_UP

logger = logging.getLogger(__name__)

# --- Binance Client Import ---
try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException, BinanceRequestException
except ImportError:
    logger.critical("❌ python-binance kütüphanesi bulunamadı! pip install python-binance")
    raise


class BinanceFuturesExecutor:
    """
    Binance Futures API ile emir yürütme sınıfı.
    Singleton pattern - tek instance kullanılır.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        Args:
            api_key: Binance API Key
            api_secret: Binance API Secret
            testnet: True ise Binance Testnet kullanır
        """
        # Sadece ilk initialization'da çalışır
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client: Optional[Client] = None
        
        self._initialize_client()
        self._initialized = True
    
    def _initialize_client(self):
        """Binance client'ı başlatır."""
        try:
            if self.testnet:
                logger.info("⚠️ TESTNET MODUNDA - Gerçek para kullanılmıyor!")
                self.client = Client(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    testnet=True
                )
            else:
                logger.warning("🔴 CANLI MOD - Gerçek para kullanılıyor!")
                self.client = Client(
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )
            
            # Bağlantıyı test et
            account_info = self.client.futures_account()
            logger.info(f"✅ Binance Futures bağlantısı başarılı. Bakiye: {account_info['totalWalletBalance']} USDT")
            
        except BinanceAPIException as e:
            logger.critical(f"❌ Binance API hatası: {e}")
            raise
        except Exception as e:
            logger.critical(f"❌ Executor başlatılamadı: {e}")
            raise
    
    # ==================== OKUMA FONKSİYONLARI ====================
    
    def get_futures_account_balance(self) -> float:
        """
        Futures cüzdan bakiyesini (USDT) döndürür.
        
        Returns:
            float: Toplam USDT bakiyesi
        """
        try:
            account = self.client.futures_account()
            total_balance = float(account.get('totalWalletBalance', 0))
            logger.debug(f"Futures Bakiye: {total_balance} USDT")
            return total_balance
            
        except BinanceAPIException as e:
            logger.error(f"❌ Bakiye sorgulanamadı: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (bakiye): {e}", exc_info=True)
            return 0.0
    
    def get_open_positions_from_binance(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Binance'den gerçek açık pozisyonları çeker.
        
        Args:
            symbol: Belirli bir sembol için filtrele (opsiyonel)
        
        Returns:
            List[Dict]: Açık pozisyon listesi
            Her pozisyon: {'symbol': str, 'positionAmt': float, 'entryPrice': float, 
                          'unrealizedProfit': float, 'leverage': int, ...}
        """
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            
            # Sadece açık pozisyonları filtrele (positionAmt != 0)
            open_positions = [
                pos for pos in positions 
                if float(pos.get('positionAmt', 0)) != 0
            ]
            
            logger.debug(f"Binance'den {len(open_positions)} açık pozisyon alındı")
            return open_positions
            
        except BinanceAPIException as e:
            logger.error(f"❌ Pozisyonlar sorgulanamadı: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (pozisyonlar): {e}", exc_info=True)
            return []
    
    def get_position_info(self, symbol: str) -> Optional[Dict]:
        """
        Belirli bir sembolün detaylı pozisyon bilgisini çeker.
        
        Args:
            symbol: İşlem çifti (örn: 'BTCUSDT')
        
        Returns:
            Dict veya None: Pozisyon bilgileri
        """
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            
            if positions and len(positions) > 0:
                pos = positions[0]
                
                # Kullanışlı formatta döndür
                return {
                    'symbol': pos['symbol'],
                    'position_amount': float(pos['positionAmt']),
                    'entry_price': float(pos['entryPrice']),
                    'unrealized_pnl': float(pos['unRealizedProfit']),
                    'leverage': int(pos.get('leverage', 1)),  # ✅ Testnet'te leverage field yok, default 1
                    'liquidation_price': float(pos.get('liquidationPrice', 0)),
                    'margin_type': pos.get('marginType', 'cross'),
                    'isolated_margin': float(pos.get('isolatedMargin', 0)) if pos.get('marginType') == 'isolated' else 0
                }
            
            return None
            
        except BinanceAPIException as e:
            logger.error(f"❌ {symbol} pozisyon bilgisi alınamadı: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (pozisyon bilgisi): {e}", exc_info=True)
            return None
    
    def get_last_trade_pnl(self, symbol: str) -> Optional[Dict]:
        """
        Belirli bir sembolün son kapatılan işleminin PnL bilgisini çeker.
        
        Args:
            symbol: İşlem çifti
        
        Returns:
            Dict veya None: {'pnl': float, 'pnl_percent': float, 'close_price': float}
        """
        try:
            # Son işlemleri al (limit=1 - en son işlem)
            trades = self.client.futures_account_trades(symbol=symbol, limit=1)
            
            if not trades:
                logger.warning(f"⚠️ {symbol} için işlem geçmişi bulunamadı")
                return None
            
            last_trade = trades[0]
            
            # PnL hesapla
            realized_pnl = float(last_trade.get('realizedPnl', 0))
            close_price = float(last_trade.get('price', 0))
            
            # Yüzde hesabı için entry price lazım - position info'dan alalım
            # Not: Bu ideal değil, çünkü pozisyon zaten kapalı. 
            # Daha iyi bir yöntem: TradeHistory tablosundaki entry_price'ı kullanmak
            
            return {
                'pnl': realized_pnl,
                'close_price': close_price,
                'commission': float(last_trade.get('commission', 0)),
                'time': last_trade.get('time')
            }
            
        except BinanceAPIException as e:
            logger.error(f"❌ {symbol} işlem geçmişi alınamadı: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (işlem geçmişi): {e}", exc_info=True)
            return None
    
    def get_open_orders(self, symbol: str) -> List[Dict]:
        """
        Belirli bir sembol için açık emirleri getirir.
        
        Args:
            symbol: İşlem çifti
        
        Returns:
            List[Dict]: Açık emir listesi
        """
        try:
            orders = self.client.futures_get_open_orders(symbol=symbol)
            logger.debug(f"{symbol} için {len(orders)} açık emir var")
            return orders
            
        except BinanceAPIException as e:
            logger.error(f"❌ {symbol} açık emirler alınamadı: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (açık emirler): {e}", exc_info=True)
            return []
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Sembol bilgilerini çeker (lot size, tick size, vb).
        
        Args:
            symbol: İşlem çifti
        
        Returns:
            Dict veya None: Sembol filtreleri ve kuralları
        """
        try:
            exchange_info = self.client.futures_exchange_info()
            
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    # Filtreleri parse et
                    filters = {f['filterType']: f for f in s['filters']}
                    
                    return {
                        'symbol': symbol,
                        'status': s['status'],
                        'price_precision': int(s['pricePrecision']),
                        'quantity_precision': int(s['quantityPrecision']),
                        'min_qty': float(filters.get('LOT_SIZE', {}).get('minQty', 0)),
                        'max_qty': float(filters.get('LOT_SIZE', {}).get('maxQty', 0)),
                        'step_size': float(filters.get('LOT_SIZE', {}).get('stepSize', 0)),
                        'min_notional': float(filters.get('MIN_NOTIONAL', {}).get('notional', 0)),
                        'tick_size': float(filters.get('PRICE_FILTER', {}).get('tickSize', 0))
                    }
            
            logger.warning(f"⚠️ {symbol} sembol bilgisi bulunamadı")
            return None
            
        except BinanceAPIException as e:
            logger.error(f"❌ Sembol bilgisi alınamadı: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (sembol bilgisi): {e}", exc_info=True)
            return None
    
    def round_quantity(self, symbol: str, quantity: float) -> float:
        """
        Miktarı sembol kurallarına göre yuvarlar.
        
        Args:
            symbol: İşlem çifti
            quantity: Yuvarlanacak miktar
        
        Returns:
            float: Yuvarlanmış miktar
        """
        try:
            symbol_info = self.get_symbol_info(symbol)
            
            if not symbol_info:
                logger.warning(f"⚠️ {symbol} için sembol bilgisi yok, yuvarlanamadı")
                return quantity
            
            step_size = Decimal(str(symbol_info['step_size']))
            quantity_decimal = Decimal(str(quantity))
            
            # Step size'a göre yuvarla
            rounded = (quantity_decimal // step_size) * step_size
            
            # Float'a çevir
            return float(rounded.quantize(step_size, rounding=ROUND_DOWN))
            
        except Exception as e:
            logger.error(f"❌ Miktar yuvarlama hatası: {e}", exc_info=True)
            return quantity
    
    def round_price(self, symbol: str, price: float) -> float:
        """
        Fiyatı sembol kurallarına göre yuvarlar (tick_size bazlı).
        
        Args:
            symbol: İşlem çifti
            price: Yuvarlanacak fiyat
        
        Returns:
            float: Yuvarlanmış fiyat
        """
        try:
            symbol_info = self.get_symbol_info(symbol)
            
            if not symbol_info:
                logger.warning(f"⚠️ {symbol} için sembol bilgisi yok, fiyat yuvarlanamadı")
                return price
            
            tick_size = Decimal(str(symbol_info['tick_size']))
            price_decimal = Decimal(str(price))
            
            # Tick size'a göre yuvarla (quantity ile aynı mantık)
            rounded = (price_decimal // tick_size) * tick_size
            
            # Float'a çevir
            return float(rounded.quantize(tick_size, rounding=ROUND_DOWN))
            
        except Exception as e:
            logger.error(f"❌ Fiyat yuvarlama hatası: {e}", exc_info=True)
            return price
    
    # ==================== YAZMA FONKSİYONLARI (⚠️ DİKKAT: GERÇEK İŞLEMLER!) ====================
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Sembol için kaldıraç ayarlar ve doğrular.
        
        Args:
            symbol: İşlem çifti
            leverage: Kaldıraç değeri (1-125 arası)
        
        Returns:
            bool: Başarılıysa True
        """
        try:
            logger.info(f"🔧 {symbol} için kaldıraç ayarlanıyor: {leverage}x")
            
            response = self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            
            logger.info(f"✅ {symbol} kaldıraç ayarlama komutu gönderildi: {leverage}x")
            
            # 🆕 DOĞRULAMA: Kaldıraç gerçekten ayarlandı mı kontrol et
            try:
                position_info = self.client.futures_position_information(symbol=symbol)
                if position_info and len(position_info) > 0:
                    actual_leverage = int(position_info[0].get('leverage', 0))
                    if actual_leverage == leverage:
                        logger.info(f"   ✅ DOĞRULANDI: {symbol} Binance kaldıraç = {actual_leverage}x")
                    else:
                        logger.warning(f"   ⚠️ UYUMSUZLUK: İstenilen {leverage}x, Gerçek {actual_leverage}x")
            except Exception as verify_e:
                logger.debug(f"   ℹ️ Kaldıraç doğrulama yapılamadı: {verify_e}")
            
            return True
            
        except BinanceAPIException as e:
            # Bazı hatalar önemli değil (kaldıraç zaten ayarlıysa)
            if 'No need to change margin type' in str(e) or 'leverage' in str(e).lower():
                logger.debug(f"ℹ️ {symbol} kaldıraç zaten {leverage}x veya değiştirilemedi: {e}")
                return True  # Bu durum hata sayılmaz
            
            logger.error(f"❌ {symbol} kaldıraç ayarlanamadı: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (kaldıraç): {e}", exc_info=True)
            return False
    
    def set_margin_type(self, symbol: str, margin_type: str = 'ISOLATED') -> bool:
        """
        Sembol için margin tipini ayarlar.
        
        Args:
            symbol: İşlem çifti
            margin_type: 'ISOLATED' veya 'CROSSED'
        
        Returns:
            bool: Başarılıysa True
        """
        try:
            logger.info(f"🔧 {symbol} için margin tipi ayarlanıyor: {margin_type}")
            
            response = self.client.futures_change_margin_type(
                symbol=symbol,
                marginType=margin_type
            )
            
            logger.info(f"✅ {symbol} margin tipi başarıyla {margin_type} olarak ayarlandı")
            return True
            
        except BinanceAPIException as e:
            # Margin tipi zaten ayarlıysa hata döner, bu normal
            if 'No need to change margin type' in str(e):
                logger.debug(f"ℹ️ {symbol} margin tipi zaten {margin_type}")
                return True
            
            logger.error(f"❌ {symbol} margin tipi ayarlanamadı: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (margin tipi): {e}", exc_info=True)
            return False
    
    def open_market_order(self, symbol: str, direction: str, quantity_units: float, entry_price: Optional[float] = None, leverage: Optional[int] = None) -> Optional[Dict]:
        """
        Piyasa emri ile pozisyon açar.
        
        Args:
            symbol: İşlem çifti (örn: 'BTCUSDT')
            direction: 'LONG' veya 'SHORT'
            quantity_units: İşlem miktarı (coin adedi, USDT değil!)
        
        Returns:
            Dict: Emir bilgileri {'orderId', 'symbol', 'side', 'avgPrice', ...} veya None
        """
        try:
            # Miktarı yuvarla (aşağı)
            rounded_qty = self.round_quantity(symbol, quantity_units)
            original_qty = quantity_units
            # Min margin enforcement (post-rounding): Gerekliyse yukarı yuvarla
            try:
                # Config'ten min margin ayarları
                try:
                    from src import config as app_config
                except Exception:
                    app_config = None
                min_static = getattr(app_config, 'MIN_MARGIN_USD', 10.0) if app_config else 10.0
                min_per_lev = getattr(app_config, 'MIN_PER_LEVERAGE_USD', 0.0) if app_config else 0.0

                # Fiyat belirle (entry_price yoksa mark price)
                price = entry_price
                if price is None:
                    try:
                        mp = self.client.futures_mark_price(symbol=symbol)
                        price = float(mp.get('markPrice', 0))
                    except Exception:
                        price = None
                if not price or price <= 0:
                    # Son çare: son trade price
                    try:
                        ticker = self.client.futures_symbol_ticker(symbol=symbol)
                        price = float(ticker.get('price', 0))
                    except Exception:
                        price = 0.0

                # Kaldıraç belirle
                lev = leverage
                if lev is None or lev <= 0:
                    pos_info = self.get_position_info(symbol)
                    lev = int(pos_info.get('leverage', 0)) if pos_info else 0
                if lev is None or lev <= 0:
                    lev = getattr(app_config, 'FUTURES_LEVERAGE', 5) if app_config else 5

                # Sabit min margin (10$) – kaldıraç ölçekli min kapalı
                effective_min_margin = min_static
                if price and price > 0 and rounded_qty > 0:
                    margin_now = (rounded_qty * price) / lev
                else:
                    margin_now = 0.0

                if price and price > 0 and margin_now + 1e-8 < effective_min_margin:
                    # Gerekli minimum notional'a göre minimum adet hesapla
                    required_notional = effective_min_margin * lev
                    required_units = required_notional / price
                    # Step size al ve yukarı yuvarla
                    sym = self.get_symbol_info(symbol)
                    step = Decimal(str(sym['step_size'])) if sym and sym.get('step_size') else Decimal('0.0001')
                    units_dec = Decimal(str(required_units))
                    n = (units_dec / step).quantize(Decimal('1'), rounding=ROUND_UP)
                    rounded_up_units = float(n * step)
                    if rounded_up_units > rounded_qty:
                        logger.info(
                            f"   🛡️ MinMargin Enforce@Exec: Qty {rounded_qty} → {rounded_up_units} | Price={price:.6f} | Lev={lev}x | MinMargin=${effective_min_margin:.2f}"
                        )
                        rounded_qty = rounded_up_units
                else:
                    logger.debug(f"   🛡️ MinMargin OK@Exec: Margin=${margin_now:.2f} >= ${effective_min_margin:.2f}")
            except Exception as e:
                logger.error(f"   ❌ MinMargin enforcement (executor) hatası: {e}")
            
            if rounded_qty == 0:
                logger.error(f"❌ {symbol} için geçersiz miktar: {quantity_units} → {rounded_qty}")
                return None
            
            # LONG = BUY, SHORT = SELL
            side = 'BUY' if direction.upper() == 'LONG' else 'SELL'
            
            logger.warning(f"⚠️ GERÇEK EMİR GÖNDERİLİYOR: {symbol} {side} {rounded_qty} (MARKET) — orijinal={original_qty}")
            
            # Piyasa emri gönder
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=rounded_qty
            )
            
            order_id = order['orderId']
            logger.info(f"✅ {symbol} pozisyon emri gönderildi: Order ID {order_id}")
            
            # 🔄 KRİTİK: Market order asenkron dolabilir, kısa bekleyip tekrar sorgula
            import time
            time.sleep(0.5)  # 500ms bekle (market order fill için)
            
            # Order bilgisini tekrar sorgula (güncel executedQty için)
            try:
                order_info = self.client.futures_get_order(symbol=symbol, orderId=order_id)
                executed_qty = float(order_info.get('executedQty', 0))
                avg_price = float(order_info.get('avgPrice', 0))
                order_status = order_info.get('status', 'UNKNOWN')
                
                logger.info(f"📊 {symbol} Order Durumu (500ms sonra):")
                logger.info(f"   Order ID: {order_id}")
                logger.info(f"   Status: {order_status}")
                logger.info(f"   Side: {side}")
                logger.info(f"   Requested Qty: {rounded_qty}")
                logger.info(f"   Executed Qty: {executed_qty}")
                logger.info(f"   Avg Price: {avg_price}")
            except Exception as e:
                logger.warning(f"⚠️ Order bilgisi sorgulanamadı, ilk yanıtı kullanıyorum: {e}")
                executed_qty = float(order.get('executedQty', 0))
                avg_price = float(order.get('avgPrice', 0))
                order_status = order.get('status', 'UNKNOWN')
            
            # 🚨 EXECUTED QTY = 0 KONTROLÜ
            if executed_qty <= 0:
                logger.error(f"❌ {symbol} POZİSYON AÇILAMADI: Executed Quantity = {executed_qty} (SIFIR veya NEGATİF!)")
                logger.error(f"   Order ID: {order_id}, Status: {order_status}")
                
                # Status NEW ise, biraz daha bekleyip tekrar dene
                if order_status == 'NEW':
                    logger.warning(f"   ⏳ Order Status=NEW, 1 saniye daha bekleniyor...")
                    time.sleep(1.0)
                    try:
                        order_info = self.client.futures_get_order(symbol=symbol, orderId=order_id)
                        executed_qty = float(order_info.get('executedQty', 0))
                        avg_price = float(order_info.get('avgPrice', 0))
                        order_status = order_info.get('status', 'UNKNOWN')
                        logger.info(f"   🔄 2. Kontrol: Executed Qty = {executed_qty}, Status = {order_status}")
                    except Exception as e:
                        logger.error(f"   ❌ 2. kontrol başarısız: {e}")
                
                # Hala 0 ise, gerçekten sorun var
                if executed_qty <= 0:
                    logger.error(f"   OLASI NEDENLER:")
                    logger.error(f"   1. Minimum notional değer çok düşük (genelde ~$100 gerekir)")
                    logger.error(f"   2. Step size yuvarlama hatası")
                    logger.error(f"   3. Market depth yetersiz (likidite problemi)")
                    logger.error(f"   4. Symbol askıya alınmış olabilir (TRADING durumu kontrol et)")
                    return None
            
            # 🚨 AVG PRICE = 0 KONTROLÜ
            if avg_price <= 0:
                logger.error(f"❌ {symbol} POZİSYON AÇILAMADI: Avg Price = {avg_price} (GEÇERSİZ!)")
                logger.error(f"   Executed Qty: {executed_qty}, Order ID: {order_id}")
                return None
            
            logger.info(f"✅ {symbol} POZİSYON BAŞARIYLA AÇILDI: {executed_qty} adet @ ${avg_price}")
            
            # Güncellenmiş order bilgisini döndür
            order['executedQty'] = str(executed_qty)
            order['avgPrice'] = str(avg_price)
            order['status'] = order_status
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"❌ {symbol} pozisyon açılamadı (API Hatası): {e}")
            
            # Hata nedenlerini detaylıca logla
            if 'Insufficient balance' in str(e) or '-2019' in str(e):
                logger.error(f"   NEDEN: Yetersiz bakiye!")
            elif 'LOT_SIZE' in str(e) or '-1111' in str(e):
                logger.error(f"   NEDEN: Geçersiz miktar (min/max/step size kontrolü gerekli)")
            elif 'NOTIONAL' in str(e) or '-1013' in str(e):
                logger.error(f"   NEDEN: İşlem değeri çok düşük (min notional: ~$100)")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ {symbol} pozisyon açılırken beklenmeyen hata: {e}", exc_info=True)
            return None
    
    def place_sl_tp_orders(
        self, 
        symbol: str, 
        direction: str, 
        quantity_units: float, 
        sl_price: float, 
        tp_price: float,
        entry_price: float = None  # Yuvarlama kontrolü için giriş fiyatı
    ) -> Optional[Dict]:
        """
        SL ve TP emirlerini yerleştirir (reduceOnly=True).
        
        Args:
            symbol: İşlem çifti
            direction: 'LONG' veya 'SHORT'
            quantity_units: İşlem miktarı
            sl_price: Stop Loss fiyatı
            tp_price: Take Profit fiyatı
            entry_price: Pozisyon giriş fiyatı (opsiyonel, yuvarlama kontrolü için)
        
        Returns:
            Dict: {'sl_order_id', 'tp_order_id'} veya None
        """
        try:
            # 🚨 KRİTİK: Quantity kontrolü (0 ise SL/TP yerleştirme!)
            if quantity_units <= 0:
                logger.error(f"❌ {symbol} SL/TP yerleştirilemez: Quantity = {quantity_units} (SIFIR veya NEGATİF!)")
                return None
            
            rounded_qty = self.round_quantity(symbol, quantity_units)
            
            # ✅ Yuvarlama sonrası tekrar kontrol
            if rounded_qty <= 0:
                logger.error(f"❌ {symbol} SL/TP yerleştirilemez: Rounded Quantity = {rounded_qty} (orijinal: {quantity_units})")
                logger.error(f"   NEDEN: Step size çok büyük, quantity çok küçük yuvarlandı!")
                return None
            
            # FİYATLARI YUVARLA
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info:
                # ✅ DÜZELTME: Tick size ile düzgün yuvarlama (Decimal kullan)
                tick_size = Decimal(str(symbol_info.get('tick_size', 0.00001)))
                sl_price_original = sl_price
                tp_price_original = tp_price
                
                # Tick size'a göre yuvarla (ROUND_DOWN kullan - Binance kuralı)
                sl_decimal = Decimal(str(sl_price))
                tp_decimal = Decimal(str(tp_price))
                
                sl_rounded = (sl_decimal / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
                tp_rounded = (tp_decimal / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
                
                # Float'a çevir (API için gerekli)
                sl_price = float(sl_rounded)
                tp_price = float(tp_rounded)
                
                # ⚠️ KRİTİK: Yuvarlama sonrası entry fiyatına çok yakınsa, 1 tick uzaklaştır
                tick_size_float = float(tick_size)
                
                if direction.upper() == 'LONG':
                    # LONG: SL giriş altında, TP giriş üstünde olmalı
                    if sl_price >= entry_price:  # SL yuvarlama sonrası entry'ye eşit/üstünde
                        sl_price = entry_price - (tick_size_float * 2)  # 2 tick aşağı
                        logger.warning(f"   ⚠️ SL yuvarlanınca entry'ye yaklaştı, düzeltildi: {sl_price_original:.6f} → {sl_price}")
                    if tp_price <= entry_price:  # TP yuvarlama sonrası entry'ye eşit/altında
                        tp_price = entry_price + (tick_size_float * 2)  # 2 tick yukarı
                        logger.warning(f"   ⚠️ TP yuvarlanınca entry'ye yaklaştı, düzeltildi: {tp_price_original:.6f} → {tp_price}")
                else:  # SHORT
                    # SHORT: SL giriş üstünde, TP giriş altında olmalı
                    if sl_price <= entry_price:
                        sl_price = entry_price + (tick_size_float * 2)
                        logger.warning(f"   ⚠️ SL yuvarlanınca entry'ye yaklaştı, düzeltildi: {sl_price_original:.6f} → {sl_price}")
                    if tp_price >= entry_price:
                        tp_price = entry_price - (tick_size_float * 2)
                        logger.warning(f"   ⚠️ TP yuvarlanınca entry'ye yaklaştı, düzeltildi: {tp_price_original:.6f} → {tp_price}")
                
                logger.info(f"   📏 Tick Size: {tick_size_float} → SL={sl_price}, TP={tp_price}")
            
            # LONG pozisyonda SL ve TP SELL, SHORT'ta BUY
            close_side = 'SELL' if direction.upper() == 'LONG' else 'BUY'
            
            logger.info(f"🎯 {symbol} için SL/TP emirleri yerleştiriliyor...")
            
            # Fiyatları format string ile düzgün hassasiyette gönder
            price_precision = symbol_info.get('price_precision', 5)
            sl_price_str = f"{sl_price:.{price_precision}f}"
            tp_price_str = f"{tp_price:.{price_precision}f}"
            
            logger.info(f"   📏 SL={sl_price_str}, TP={tp_price_str} (precision={price_precision})")
            
            # 1. STOP LOSS emri
            sl_order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='STOP_MARKET',
                quantity=rounded_qty,
                stopPrice=sl_price_str,  # String olarak gönder
                reduceOnly=True,  # ⚠️ KRİTİK: Sadece pozisyonu kapat
                timeInForce='GTE_GTC'
            )
            
            logger.info(f"   ✅ SL Emri: {sl_order['orderId']} @ {sl_price_str}")
            
            # 2. TAKE PROFIT emri
            tp_order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='TAKE_PROFIT_MARKET',
                quantity=rounded_qty,
                stopPrice=tp_price_str,  # String olarak gönder
                reduceOnly=True,
                timeInForce='GTE_GTC'
            )
            
            logger.info(f"   ✅ TP Emri: {tp_order['orderId']} @ {tp_price_str}")
            
            return {
                'sl_order_id': sl_order['orderId'],
                'tp_order_id': tp_order['orderId'],
                'sl_price': sl_price,
                'tp_price': tp_price
            }
            
        except BinanceAPIException as e:
            logger.error(f"❌ {symbol} SL/TP emirleri yerleştirilemedi: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (SL/TP): {e}", exc_info=True)
            return None
    
    def cancel_order(self, symbol: str, order_id: int) -> bool:
        """
        Belirli bir emri iptal eder.
        
        Args:
            symbol: İşlem çifti
            order_id: İptal edilecek emir ID
        
        Returns:
            bool: Başarılıysa True
        """
        try:
            logger.info(f"🗑️ {symbol} emir iptal ediliyor: {order_id}")
            
            response = self.client.futures_cancel_order(
                symbol=symbol,
                orderId=order_id
            )
            
            logger.info(f"✅ {symbol} emir iptal edildi: {order_id}")
            return True
            
        except BinanceAPIException as e:
            logger.error(f"❌ {symbol} emir iptal edilemedi: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (emir iptali): {e}", exc_info=True)
            return False
    
    def cancel_all_orders(self, symbol: str) -> bool:
        """
        Sembolün tüm açık emirlerini iptal eder.
        
        Args:
            symbol: İşlem çifti
        
        Returns:
            bool: Başarılıysa True
        """
        try:
            logger.info(f"🗑️ {symbol} TÜM emirler iptal ediliyor...")
            
            response = self.client.futures_cancel_all_open_orders(symbol=symbol)
            
            logger.info(f"✅ {symbol} tüm emirler iptal edildi")
            return True
            
        except BinanceAPIException as e:
            logger.error(f"❌ {symbol} emirler iptal edilemedi: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (toplu iptal): {e}", exc_info=True)
            return False
    
    def close_position_market(self, symbol: str, quantity_units: Optional[float] = None) -> Optional[Dict]:
        """
        Pozisyonu piyasa fiyatından kapatır.
        
        Args:
            symbol: İşlem çifti
            quantity_units: Kapatılacak miktar (None ise tüm pozisyon)
        
        Returns:
            Dict: Emir bilgileri veya None
        """
        try:
            # Mevcut pozisyonu al
            position = self.get_position_info(symbol)
            
            if not position or position['position_amount'] == 0:
                logger.warning(f"⚠️ {symbol} için açık pozisyon yok")
                return None
            
            pos_amt = position['position_amount']
            close_qty = abs(quantity_units) if quantity_units else abs(pos_amt)
            close_qty = self.round_quantity(symbol, close_qty)
            
            # Pozisyon LONG ise SELL, SHORT ise BUY
            close_side = 'SELL' if pos_amt > 0 else 'BUY'
            
            logger.warning(f"⚠️ {symbol} POZİSYON KAPATILIYOR: {close_side} {close_qty} (MARKET)")
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='MARKET',
                quantity=close_qty,
                reduceOnly=True
            )
            
            logger.info(f"✅ {symbol} pozisyon KAPATILDI:")
            logger.info(f"   Order ID: {order['orderId']}")
            logger.info(f"   Quantity: {order['executedQty']}")
            logger.info(f"   Avg Price: {order.get('avgPrice', 'N/A')}")
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"❌ {symbol} pozisyon kapatılamadı: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (pozisyon kapatma): {e}", exc_info=True)
            return None
    
    def transfer_futures_to_spot(self, amount: float) -> bool:
        """
        Futures cüzdanından Spot cüzdana USDT transfer eder.
        
        Args:
            amount: Transfer edilecek USDT miktarı
        
        Returns:
            bool: Başarılıysa True
        """
        try:
            logger.info(f"💸 Futures → Spot transfer başlatılıyor: ${amount:.2f} USDT")
            
            # Transfer yap
            response = self.client.futures_account_transfer(
                asset='USDT',
                amount=amount,
                type=2  # 1=Spot→Futures, 2=Futures→Spot
            )
            
            logger.info(f"✅ Transfer başarılı: ${amount:.2f} USDT Spot cüzdana aktarıldı")
            logger.info(f"   Transaction ID: {response.get('tranId', 'N/A')}")
            
            return True
            
        except BinanceAPIException as e:
            logger.error(f"❌ Transfer başarısız: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Beklenmeyen hata (transfer): {e}", exc_info=True)
            return False


# --- Singleton Instance Oluşturma Yardımcı Fonksiyonu ---
_executor_instance: Optional[BinanceFuturesExecutor] = None

def initialize_executor(config_module) -> BinanceFuturesExecutor:
    """
    Executor'ı config modülünden ayarlarla başlatır.
    
    Args:
        config_module: src.config modülü
    
    Returns:
        BinanceFuturesExecutor: Başlatılmış executor instance
    """
    global _executor_instance
    
    if _executor_instance is not None:
        logger.debug("Executor zaten başlatılmış, mevcut instance döndürülüyor")
        return _executor_instance
    
    api_key = getattr(config_module, 'BINANCE_API_KEY', None)
    api_secret = getattr(config_module, 'BINANCE_SECRET_KEY', None)
    testnet = getattr(config_module, 'BINANCE_TESTNET', False)
    
    if not api_key or api_key == "YOUR_BINANCE_API_KEY_PLACEHOLDER":
        raise ValueError("❌ Binance API Key eksik! .env dosyasını kontrol edin.")
    
    if not api_secret or api_secret == "YOUR_BINANCE_SECRET_KEY_PLACEHOLDER":
        raise ValueError("❌ Binance API Secret eksik! .env dosyasını kontrol edin.")
    
    logger.info("🔧 Binance Futures Executor başlatılıyor...")
    _executor_instance = BinanceFuturesExecutor(api_key, api_secret, testnet)
    
    return _executor_instance


def get_executor() -> Optional[BinanceFuturesExecutor]:
    """
    Mevcut executor instance'ını döndürür.
    
    Returns:
        BinanceFuturesExecutor veya None
    """
    return _executor_instance


# --- Test Bloğu ---
if __name__ == '__main__':
    import sys
    import os
    
    # Config'i import et
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, project_root)
    
    from src import config
    
    # Loglama ayarla
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s'
    )
    
    print("=" * 60)
    print("BINANCE FUTURES EXECUTOR TEST (Sadece Okuma)")
    print("=" * 60)
    
    try:
        # Executor'ı başlat
        executor = initialize_executor(config)
        
        # Test 1: Bakiye
        print("\n1️⃣ Bakiye Kontrolü:")
        balance = executor.get_futures_account_balance()
        print(f"   Toplam Bakiye: {balance} USDT")
        
        # Test 2: Açık Pozisyonlar
        print("\n2️⃣ Açık Pozisyonlar:")
        positions = executor.get_open_positions_from_binance()
        if positions:
            for pos in positions:
                print(f"   - {pos['symbol']}: {pos['positionAmt']} @ {pos['entryPrice']}")
        else:
            print("   Açık pozisyon yok")
        
        # Test 3: Sembol Bilgisi (BTC)
        print("\n3️⃣ BTCUSDT Sembol Bilgisi:")
        symbol_info = executor.get_symbol_info('BTCUSDT')
        if symbol_info:
            print(f"   Min Qty: {symbol_info['min_qty']}")
            print(f"   Step Size: {symbol_info['step_size']}")
            print(f"   Min Notional: {symbol_info['min_notional']}")
        
        print("\n" + "=" * 60)
        print("✅ TÜM TESTLER BAŞARILI!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST HATASI: {e}")
        import traceback
        traceback.print_exc()


# =============================================================================
# YENİ: Binance Position Risk ve Account Data Functions (7 Kasım 2025)
# Tüm PnL, margin, tasfiye hesaplamalarını Binance'den alıyoruz
# =============================================================================

def get_position_risk(self, symbol: Optional[str] = None) -> List[Dict]:
    """
    Binance'den pozisyon risk bilgilerini çeker (GERÇEK HESAPLAMALAR).
    
    Bu fonksiyon Binance'in kendi hesapladığı:
    - Gerçekleşmemiş kar/zarar (unrealizedProfit)
    - Tasfiye fiyatı (liquidationPrice)
    - Kullanılan margin (isolatedMargin)
    - Notional değer (notional)
    - Kaldıraç (leverage)
    
    Args:
        symbol: Belirli bir sembol (opsiyonel). None ise tüm pozisyonlar.
    
    Returns:
        List[Dict]: Açık pozisyonların detaylı bilgileri
        
    Örnek return:
        [{
            'symbol': 'BTCUSDT',
            'positionAmt': '0.001',           # Pozisyon boyutu (+ LONG, - SHORT)
            'entryPrice': '35000.00',         # Giriş fiyatı
            'markPrice': '35500.00',          # Anlık mark price
            'unRealizedProfit': '0.50',       # Gerçekleşmemiş PnL (USD)
            'liquidationPrice': '23333.33',   # Tasfiye fiyatı
            'leverage': '3',                  # Kaldıraç
            'isolatedMargin': '11.67',        # Kullanılan margin (isolated)
            'notional': '35.50',              # Pozisyon değeri
            'marginType': 'isolated',
            'isAutoAddMargin': 'false',
            'positionSide': 'BOTH',
            'updateTime': 1699373000000
        }]
    """
    try:
        logger.debug(f"📊 Binance'den position risk bilgisi çekiliyor... (symbol={symbol or 'ALL'})")
        
        # Binance Account API çağrısı (leverage bilgisi burada!)
        account = self.client.futures_account()
        positions = account.get('positions', [])
        
        # Sembol filtresi uygula (eğer belirtildiyse)
        if symbol:
            positions = [p for p in positions if p.get('symbol') == symbol]
        
        # Sadece açık pozisyonları filtrele
        open_positions = [
            pos for pos in positions 
            if float(pos.get('positionAmt', 0)) != 0
        ]
        
        # Mark price bilgilerini alalım (account'ta yok)
        mark_prices = {}
        try:
            all_mark_prices = self.client.futures_mark_price()
            mark_prices = {p['symbol']: float(p['markPrice']) for p in all_mark_prices}
        except Exception as e:
            logger.warning(f"⚠️ Mark price alınamadı: {e}")
        
        # Pozisyonlara mark price ekle + key düzeltmeleri
        for pos in open_positions:
            sym = pos['symbol']
            pos['markPrice'] = mark_prices.get(sym, float(pos.get('entryPrice', 0)))
            
            # Key isimlerini standardize et
            if 'unrealizedProfit' in pos:
                pos['unRealizedProfit'] = pos['unrealizedProfit']
            if 'isolatedWallet' in pos:
                pos['isolatedMargin'] = pos['isolatedWallet']
            if 'liquidationPrice' not in pos:
                # Basit tasfiye fiyat hesaplaması (gerçek değil ama yaklaşık)
                leverage = int(pos.get('leverage', 1))
                entry = float(pos.get('entryPrice', 0))
                if float(pos.get('positionAmt', 0)) > 0:  # LONG
                    pos['liquidationPrice'] = entry * (1 - 0.9 / leverage)
                else:  # SHORT
                    pos['liquidationPrice'] = entry * (1 + 0.9 / leverage)
        
        logger.info(f"✅ Binance'den {len(open_positions)} açık pozisyon alındı")
        
        # Debug: Her pozisyonu logla
        for pos in open_positions:
            leverage = pos.get('leverage', 'N/A')
            unrealized_pnl = float(pos.get('unRealizedProfit', 0))
            isolated_margin = float(pos.get('isolatedMargin', 0))
            
            logger.debug(f"   {pos['symbol']}: PnL=${unrealized_pnl:.2f}, "
                        f"Margin=${isolated_margin:.2f}, "
                        f"Leverage={leverage}x")
        
        return open_positions
        
    except BinanceAPIException as e:
        logger.error(f"❌ Binance Position Risk API hatası: {e}")
        return []
    except BinanceRequestException as e:
        logger.error(f"❌ Binance bağlantı hatası: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Position risk alınırken beklenmeyen hata: {e}", exc_info=True)
        return []


def get_account_data(self) -> Dict:
    """
    Binance Futures hesap bilgilerini çeker (GERÇEK BAKIYE VE MARGIN).
    
    Bu fonksiyon Binance'in hesapladığı:
    - Toplam bakiye (totalWalletBalance)
    - Kullanılabilir bakiye (availableBalance)
    - Toplam gerçekleşmemiş kar (totalUnrealizedProfit)
    - Toplam kullanılan margin (totalPositionInitialMargin)
    - Tüm pozisyonların detayları
    
    Returns:
        Dict: Hesap bilgileri
        
    Örnek return:
        {
            'total_balance': 200.00,          # Toplam bakiye
            'available_balance': 181.50,      # Kullanılabilir bakiye
            'total_unrealized_pnl': 1.50,     # Toplam gerçekleşmemiş kar
            'total_margin_used': 18.50,       # Toplam kullanılan margin
            'total_wallet_balance': 201.50,   # Wallet bakiye (balance + PnL)
            'max_withdraw': 181.50,           # Çekilebilir maksimum
            'positions': [...]                # Tüm pozisyonlar
        }
    """
    try:
        logger.debug("📊 Binance'den account data çekiliyor...")
        
        # Binance API çağrısı
        account = self.client.futures_account()
        
        # İhtiyacımız olan verileri parse et
        account_data = {
            'total_balance': float(account.get('totalWalletBalance', 0)),
            'available_balance': float(account.get('availableBalance', 0)),
            'total_unrealized_pnl': float(account.get('totalUnrealizedProfit', 0)),
            'total_margin_used': float(account.get('totalPositionInitialMargin', 0)),
            'total_wallet_balance': float(account.get('totalMarginBalance', 0)),
            'total_open_order_margin': float(account.get('totalOpenOrderInitialMargin', 0)),
            'max_withdraw': float(account.get('maxWithdrawAmount', 0)),
            'update_time': account.get('updateTime', 0),
            'positions': account.get('positions', [])
        }
        
        logger.info(f"✅ Hesap verisi alındı: Bakiye=${account_data['total_balance']:.2f}, "
                   f"Margin=${account_data['total_margin_used']:.2f}, "
                   f"PnL=${account_data['total_unrealized_pnl']:.2f}")
        
        return account_data
        
    except BinanceAPIException as e:
        logger.error(f"❌ Binance Account API hatası: {e}")
        return {}
    except BinanceRequestException as e:
        logger.error(f"❌ Binance bağlantı hatası: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Account data alınırken beklenmeyen hata: {e}", exc_info=True)
        return {}


# Method'ları sınıfa ekle
BinanceFuturesExecutor.get_position_risk = get_position_risk
BinanceFuturesExecutor.get_account_data = get_account_data
