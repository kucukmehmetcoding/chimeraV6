# src/data_fetcher/realtime_manager.py

import logging
import threading
import time
from typing import Dict, List, Set, Optional
from binance import AsyncClient, BinanceSocketManager # WebSocket için gerekli
import asyncio
import json

# Proje kökünü path'e ekle (config'i bulabilmek için)
import sys, os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path: sys.path.append(project_root)

# Loglamayı ayarla
logger = logging.getLogger(__name__)

# Gerekli modülleri import et
try:
    from src.database.models import db_session, OpenPosition
    from src import config
except ImportError:
    logger.critical("realtime_manager: Gerekli veritabanı veya config modülleri import edilemedi!")
    raise

class RealTimeDataManager:
    """
    Ayrı bir thread'de çalışan, Binance WebSocket'e bağlanan,
    açık pozisyonları dinamik olarak takip eden (DB'den okuyarak)
    ve anlık fiyatları bir cache'de tutan sınıf.
    """
    def __init__(self, stop_event: threading.Event, config_obj: object):
        self.client = None # AsyncClient olarak başlatılacak
        self.bsm = None # BinanceSocketManager
        self.stop_event = stop_event
        self.config = config_obj
        
        self.price_cache: Dict[str, float] = {} # Anlık fiyatların tutulduğu yer
        self.price_cache_lock = threading.Lock() # Cache'e yazarken/okurken kilitle
        
        self.subscribed_symbols: Set[str] = set() # Şu anda hangi coinleri dinliyoruz
        self.subscription_check_interval = 60 # Her 60 saniyede bir DB'yi kontrol et
        
        self.thread = threading.Thread(target=self.run, daemon=True, name="RealTimeManagerThread")

    def add_symbol(self, symbol: str):
        """
        Yeni bir sembolü izleme listesine ekler.
        Not: Bu metod sadece compatibility için var, gerçek abonelik DB'den otomatik yapılır.
        """
        logger.info(f"[WS] {symbol} sembolü izleme listesine eklendi (DB'den otomatik sync olacak)")
        # subscribed_symbols set'i run() döngüsünde otomatik güncellenir

    def start(self) -> threading.Thread:
        """WebSocket manager thread'ini başlatır."""
        logger.info("RealTimeDataManager thread'i başlatılıyor...")
        self.thread.start()
        return self.thread

    def _process_message(self, msg: Dict):
        """
        WebSocket'ten gelen her mesajı işler.
        
        GÜNCELLENDİ (6 Kasım 2025): Futures mark price stream desteği eklendi
        """
        try:
            # msg artık JSON string veya dict olabilir
            if isinstance(msg, str):
                msg = json.loads(msg)
                
            # Futures Mark Price Stream (ÖNERİLEN - Funding rate dahil)
            if msg.get('e') == 'markPriceUpdate':
                symbol = msg['s']
                price = float(msg['p'])  # Mark price
                # İsteğe bağlı: funding rate ve index price
                # funding_rate = float(msg.get('r', 0))
                # index_price = float(msg.get('i', 0))
                
                with self.price_cache_lock:
                    self.price_cache[symbol] = price
                logger.debug(f"[WS] Futures Mark Price Güncellemesi: {symbol} = {price}")
                
            # Futures Aggregated Trade Stream (Alternatif)
            elif msg.get('e') == 'aggTrade':
                symbol = msg['s']
                price = float(msg['p'])
                with self.price_cache_lock:
                    self.price_cache[symbol] = price
                logger.debug(f"[WS] Futures AggTrade Güncellemesi: {symbol} = {price}")
                
            # Hata mesajı
            elif msg.get('e') == 'error':
                logger.error(f"[WS] WebSocket Hatası: {msg.get('m')}")
                 
        except Exception as e:
            logger.error(f"[WS] Mesaj işleme hatası: {e} - Mesaj: {msg}")

    async def _subscription_loop(self):
        """
        Asenkron olarak abonelikleri yönetir ve mesajları dinler.
        
        GÜNCELLENDİ (6 Kasım 2025): Futures mark price stream'e geçildi
        """
        # AsyncClient'ı başlat
        self.client = await AsyncClient.create(config.BINANCE_API_KEY, config.BINANCE_SECRET_KEY)
        self.bsm = BinanceSocketManager(self.client)
        
        last_check_time = 0
        current_socket = None
        current_task = None
        
        # GÜNCELLENDİ: Futures Mark Price Stream kullanıyoruz (funding rate dahil)
        # Alternatif: '@aggTrade' (daha sık güncelleme ama funding rate yok)
        stream_type = '@markPrice'  # Futures mark price stream 
        
        while not self.stop_event.is_set():
            now = time.time()
            
            # --- Abonelikleri Güncelle (DB Kontrolü) ---
            if (now - last_check_time) > self.subscription_check_interval:
                last_check_time = now
                logger.info("[WS] Açık pozisyonlar için abonelikler kontrol ediliyor...")
                db = db_session()
                try:
                    # DB'den mevcut açık pozisyonların sembollerini al
                    open_symbols_db = db.query(OpenPosition.symbol).distinct().all()
                    required_symbols = {sym[0] for sym in open_symbols_db if sym[0]}
                except Exception as e_db:
                    logger.error(f"[WS] Abonelik kontrolü için DB okunurken hata: {e_db}")
                    required_symbols = self.subscribed_symbols
                finally:
                    db_session.remove()

                # Karşılaştır
                new_symbols = required_symbols - self.subscribed_symbols
                dead_symbols = self.subscribed_symbols - required_symbols

                # Yeni bağlantı gerekiyorsa
                if new_symbols or dead_symbols:
                    logger.info(f"[WS] Abonelikler güncelleniyor. Yeni: {new_symbols}, Kapatılan: {dead_symbols}")
                    self.subscribed_symbols = required_symbols
                    
                    # Eski task'i iptal et
                    if current_task and not current_task.done():
                        current_task.cancel()
                        try:
                            await current_task
                        except asyncio.CancelledError:
                            pass
                    
                    # Eski socket'i kapat
                    if current_socket:
                        try:
                            await current_socket.__aexit__(None, None, None)
                        except:
                            pass
                        current_socket = None
                        
                    if not self.subscribed_symbols:
                        logger.info("[WS] İzlenecek sembol kalmadı, stream durduruldu.")
                        with self.price_cache_lock: 
                            self.price_cache.clear()
                    else:
                        # Yeni multiplex stream başlat
                        streams = [f"{s.lower()}{stream_type}" for s in self.subscribed_symbols]
                        
                        try:
                            # Yeni API: async context manager kullan
                            current_socket = self.bsm.multiplex_socket(streams)
                            await current_socket.__aenter__()
                            logger.info(f"✅ [WS] {len(streams)} adet streame abone olundu (örn: {streams[0]})")
                            
                            # Async generator'dan mesajları al
                            async def listen_socket():
                                try:
                                    # ReconnectingWebsocket objesi recv_messages() ile async iterator sağlıyor
                                    async for msg in current_socket.recv_messages():
                                        self._process_message(msg)
                                        if self.stop_event.is_set():
                                            break
                                except AttributeError:
                                    # Eski API compatibility: Direkt iterate et
                                    try:
                                        async for msg in current_socket:
                                            self._process_message(msg)
                                            if self.stop_event.is_set():
                                                break
                                    except TypeError as te:
                                        logger.error(f"[WS] WebSocket async iterasyon hatası: {te}")
                                except asyncio.CancelledError:
                                    logger.info("[WS] Socket listener task iptal edildi")
                                except Exception as e:
                                    logger.error(f"[WS] Socket dinleme hatası: {e}")
                            
                            # Background task olarak başlat
                            current_task = asyncio.create_task(listen_socket())
                            
                        except Exception as e:
                            logger.error(f"❌ [WS] Socket başlatma hatası: {e}", exc_info=True)
                            current_socket = None
            
            await asyncio.sleep(1)
            
        # Cleanup
        logger.info("[WS] Stop event alındı, kaynaklar temizleniyor...")
        
        if current_task and not current_task.done():
            current_task.cancel()
            try:
                await current_task
            except asyncio.CancelledError:
                pass
        
        if current_socket:
            try:
                await current_socket.__aexit__(None, None, None)
            except:
                pass
        
        if self.client:
            await self.client.close_connection()
            
        logger.info("✅ [WS] Abonelik döngüsü temiz bir şekilde durduruldu.")


    def run(self):
        """Thread'in ana çalışma fonksiyonu."""
        logger.info("[WS] RealTimeDataManager thread'i `run` metodunu başlattı.")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._subscription_loop())
        except Exception as e:
            logger.critical(f"❌ RealTimeDataManager thread'i çöktü: {e}", exc_info=True)
        finally:
            logger.info("RealTimeDataManager thread'i sonlanıyor.")

    def get_price(self, symbol: str) -> Optional[float]:
        """Trade Manager'ın fiyat okumak için çağıracağı fonksiyon."""
        with self.price_cache_lock:
            return self.price_cache.get(symbol) # Sembol cache'de yoksa None döner