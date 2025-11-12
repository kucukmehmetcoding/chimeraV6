# src/data_fetcher/realtime_ema_calculator.py
"""
v10.6: REAL-TIME EMA CALCULATION - Phase 2
===========================================

Bu modül, WebSocket'ten gelen 15m mum verilerinden gerçek zamanlı EMA hesaplar.
EMA5 x EMA20 kesişimlerini hem kapalı hem de açık mumlarda tespit eder.

Temel Özellikler:
- Streaming EMA hesaplama (incomplete candle için de çalışır)
- Crossover detection (bullish/bearish)
- Pre-crossover alerting (kesişim yaklaşırken uyarı)
- Historical data warming (başlangıçta yeterli veri biriktirme)
- Callback system (kesişim anında tetikleme)

EMA Formülü:
- EMA(today) = (Price(today) * k) + (EMA(yesterday) * (1 - k))
- k = 2 / (period + 1)
- EMA5: k = 2/6 = 0.333
- EMA20: k = 2/21 = 0.095
"""

import logging
import time
from typing import Dict, List, Optional, Callable
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class RealtimeEMACalculator:
    """
    Gerçek zamanlı EMA hesaplama ve kesişim tespiti
    
    WebSocket'ten gelen her yeni mum verisini kullanarak:
    1. EMA5 ve EMA20 değerlerini günceller
    2. Kesişim olup olmadığını kontrol eder
    3. Pre-crossover durumlarını tespit eder (fiyat EMA'ya yaklaşıyor)
    4. Callback'leri tetikler
    """
    
    def __init__(
        self,
        symbol: str,
        ema_short_period: int = 5,
        ema_long_period: int = 20,
        warmup_candles: int = 50,  # Başlangıçta kaç mum bekleyeceğiz
        pre_crossover_threshold: float = 0.002  # %0.2 - fiyat EMA'ya bu kadar yakınsa "yaklaşıyor" uyarısı
    ):
        self.symbol = symbol
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.warmup_candles = warmup_candles
        self.pre_crossover_threshold = pre_crossover_threshold
        
        # EMA multipliers
        self.k_short = 2.0 / (ema_short_period + 1)  # 0.333 for EMA5
        self.k_long = 2.0 / (ema_long_period + 1)    # 0.095 for EMA20
        
        # State
        self.candles: deque = deque(maxlen=warmup_candles)  # Son N mum
        self.ema_short: Optional[float] = None  # Current EMA5
        self.ema_long: Optional[float] = None   # Current EMA20
        self.prev_ema_short: Optional[float] = None
        self.prev_ema_long: Optional[float] = None
        
        # Crossover state
        self.last_crossover_direction: Optional[str] = None  # 'bullish' or 'bearish'
        self.last_crossover_time: Optional[float] = None
        self.is_warmed_up: bool = False
        
        # Callbacks
        self.on_crossover: Optional[Callable] = None  # Kesişim olduğunda
        self.on_pre_crossover: Optional[Callable] = None  # Kesişim yaklaşırken
        self.on_ema_update: Optional[Callable] = None  # Her EMA güncellemesinde
        
        # Statistics
        self.update_count: int = 0
        self.crossover_count: int = 0
        
        logger.info(f"📊 RealtimeEMACalculator initialized for {symbol}")
        logger.info(f"   Short EMA: {ema_short_period} (k={self.k_short:.4f})")
        logger.info(f"   Long EMA: {ema_long_period} (k={self.k_long:.4f})")
        logger.info(f"   Warmup: {warmup_candles} candles")
        logger.info(f"   Pre-crossover threshold: {pre_crossover_threshold*100:.2f}%")
    
    def set_crossover_callback(self, callback: Callable):
        """Kesişim callback'i ayarla"""
        self.on_crossover = callback
    
    def set_pre_crossover_callback(self, callback: Callable):
        """Pre-crossover callback'i ayarla"""
        self.on_pre_crossover = callback
    
    def set_ema_update_callback(self, callback: Callable):
        """EMA update callback'i ayarla"""
        self.on_ema_update = callback
    
    def process_kline(self, kline_data: Dict) -> Dict:
        """
        Yeni kline verisini işle ve EMA'ları güncelle
        
        Args:
            kline_data: WebSocket'ten gelen kline datası
                {
                    'symbol': 'BTCUSDT',
                    'close': 103562.08,
                    'is_closed': False,
                    'open_time': timestamp,
                    ...
                }
        
        Returns:
            Dict with current state:
                {
                    'symbol': 'BTCUSDT',
                    'ema_short': 103500.0,
                    'ema_long': 103450.0,
                    'is_warmed_up': True,
                    'crossover': None or 'bullish'/'bearish',
                    'pre_crossover': None or 'approaching_bullish'/'approaching_bearish',
                    'distance_to_cross': 0.0015  # EMA'lar arası mesafe (%)
                }
        """
        try:
            # Extract price
            close_price = float(kline_data.get('close', 0))
            is_closed = kline_data.get('is_closed', False)
            
            if close_price <= 0:
                logger.warning(f"⚠️ Invalid close price: {close_price}")
                return self._get_current_state()
            
            # Store candle
            candle = {
                'time': kline_data.get('open_time'),
                'close': close_price,
                'is_closed': is_closed
            }
            
            # Add to buffer
            if is_closed:
                # Kapalı mum - kesin veri
                self.candles.append(candle)
                logger.debug(f"🟢 Closed candle added: {close_price:.2f}")
            else:
                # Açık mum - son mumu güncelle veya ekle
                if len(self.candles) > 0 and not self.candles[-1]['is_closed']:
                    # Son mum hala açık, güncelle
                    self.candles[-1] = candle
                    logger.debug(f"⚪ Open candle updated: {close_price:.2f}")
                else:
                    # İlk açık mum, ekle
                    self.candles.append(candle)
                    logger.debug(f"⚪ Open candle added: {close_price:.2f}")
            
            # Calculate EMAs
            self._calculate_emas()
            
            # Check warmup status
            if not self.is_warmed_up and len(self.candles) >= self.warmup_candles:
                self.is_warmed_up = True
                logger.info(f"✅ {self.symbol} warmed up with {len(self.candles)} candles")
                logger.info(f"   Initial EMA{self.ema_short_period}: {self.ema_short:.2f}")
                logger.info(f"   Initial EMA{self.ema_long_period}: {self.ema_long:.2f}")
            
            # Detect crossover (only if warmed up)
            crossover = None
            pre_crossover = None
            
            if self.is_warmed_up:
                crossover = self._detect_crossover()
                pre_crossover = self._detect_pre_crossover()
            
            # Update counter
            self.update_count += 1
            
            # Get current state
            state = self._get_current_state()
            state['crossover'] = crossover
            state['pre_crossover'] = pre_crossover
            
            # Trigger callbacks
            if self.on_ema_update:
                self.on_ema_update(state)
            
            if crossover and self.on_crossover:
                self.on_crossover(state)
            
            if pre_crossover and self.on_pre_crossover:
                self.on_pre_crossover(state)
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Error processing kline for {self.symbol}: {e}", exc_info=True)
            return self._get_current_state()
    
    def _calculate_emas(self):
        """EMA'ları hesapla"""
        if len(self.candles) == 0:
            return
        
        # Save previous values
        self.prev_ema_short = self.ema_short
        self.prev_ema_long = self.ema_long
        
        # First time: Use SMA as starting point
        if self.ema_short is None:
            if len(self.candles) >= self.ema_short_period:
                prices = [c['close'] for c in list(self.candles)[-self.ema_short_period:]]
                self.ema_short = sum(prices) / len(prices)
        
        if self.ema_long is None:
            if len(self.candles) >= self.ema_long_period:
                prices = [c['close'] for c in list(self.candles)[-self.ema_long_period:]]
                self.ema_long = sum(prices) / len(prices)
        
        # Update EMAs with latest price
        current_price = self.candles[-1]['close']
        
        if self.ema_short is not None:
            # EMA = (Price * k) + (EMA_prev * (1 - k))
            self.ema_short = (current_price * self.k_short) + (self.ema_short * (1 - self.k_short))
        
        if self.ema_long is not None:
            self.ema_long = (current_price * self.k_long) + (self.ema_long * (1 - self.k_long))
    
    def _detect_crossover(self) -> Optional[str]:
        """
        Kesişim tespit et
        
        Returns:
            'bullish': EMA5 yukarı kesti EMA20'yi (LONG signal)
            'bearish': EMA5 aşağı kesti EMA20'yi (SHORT signal)
            None: Kesişim yok
        """
        if not all([self.ema_short, self.ema_long, self.prev_ema_short, self.prev_ema_long]):
            return None
        
        # Previous state
        was_above = self.prev_ema_short > self.prev_ema_long
        
        # Current state
        is_above = self.ema_short > self.ema_long
        
        # Detect crossover
        if was_above and not is_above:
            # Bearish crossover: EMA5 aşağı kesti
            self.last_crossover_direction = 'bearish'
            self.last_crossover_time = time.time()
            self.crossover_count += 1
            
            logger.info(f"📉 BEARISH CROSSOVER detected for {self.symbol}")
            logger.info(f"   EMA{self.ema_short_period}: {self.prev_ema_short:.2f} → {self.ema_short:.2f}")
            logger.info(f"   EMA{self.ema_long_period}: {self.prev_ema_long:.2f} → {self.ema_long:.2f}")
            logger.info(f"   Price: {self.candles[-1]['close']:.2f}")
            
            return 'bearish'
        
        elif not was_above and is_above:
            # Bullish crossover: EMA5 yukarı kesti
            self.last_crossover_direction = 'bullish'
            self.last_crossover_time = time.time()
            self.crossover_count += 1
            
            logger.info(f"📈 BULLISH CROSSOVER detected for {self.symbol}")
            logger.info(f"   EMA{self.ema_short_period}: {self.prev_ema_short:.2f} → {self.ema_short:.2f}")
            logger.info(f"   EMA{self.ema_long_period}: {self.prev_ema_long:.2f} → {self.ema_long:.2f}")
            logger.info(f"   Price: {self.candles[-1]['close']:.2f}")
            
            return 'bullish'
        
        return None
    
    def _detect_pre_crossover(self) -> Optional[str]:
        """
        Pre-crossover tespit et (EMA'lar birbirine yaklaşıyor mu?)
        
        Returns:
            'approaching_bullish': EMA5 yaklaşıyor EMA20'ye (yukarıdan)
            'approaching_bearish': EMA5 yaklaşıyor EMA20'ye (aşağıdan)
            None: Yaklaşma yok
        """
        if not all([self.ema_short, self.ema_long]):
            return None
        
        # Calculate distance between EMAs (%)
        distance = abs(self.ema_short - self.ema_long) / self.ema_long
        
        # Check if within threshold
        if distance <= self.pre_crossover_threshold:
            # Determine direction
            if self.ema_short > self.ema_long:
                # EMA5 üstte ama yakın - bearish crossover yaklaşıyor olabilir
                logger.debug(f"⚠️ {self.symbol} approaching bearish crossover (distance: {distance*100:.3f}%)")
                return 'approaching_bearish'
            else:
                # EMA5 altta ama yakın - bullish crossover yaklaşıyor olabilir
                logger.debug(f"⚠️ {self.symbol} approaching bullish crossover (distance: {distance*100:.3f}%)")
                return 'approaching_bullish'
        
        return None
    
    def _get_current_state(self) -> Dict:
        """Mevcut durumu döndür"""
        distance = None
        if self.ema_short and self.ema_long:
            distance = abs(self.ema_short - self.ema_long) / self.ema_long
        
        return {
            'symbol': self.symbol,
            'ema_short': self.ema_short,
            'ema_long': self.ema_long,
            'is_warmed_up': self.is_warmed_up,
            'candle_count': len(self.candles),
            'distance_to_cross': distance,
            'last_crossover_direction': self.last_crossover_direction,
            'last_crossover_time': self.last_crossover_time,
            'update_count': self.update_count,
            'crossover_count': self.crossover_count
        }
    
    def get_stats(self) -> Dict:
        """İstatistikleri döndür"""
        return self._get_current_state()
    
    def reset(self):
        """Reset calculator state"""
        self.candles.clear()
        self.ema_short = None
        self.ema_long = None
        self.prev_ema_short = None
        self.prev_ema_long = None
        self.last_crossover_direction = None
        self.last_crossover_time = None
        self.is_warmed_up = False
        self.update_count = 0
        self.crossover_count = 0
        
        logger.info(f"🔄 {self.symbol} calculator reset")


class RealtimeEMAManager:
    """
    Birden fazla sembol için EMA hesaplama yöneticisi
    
    WebSocket manager ile entegre çalışır:
    - Her sembol için ayrı RealtimeEMACalculator oluşturur
    - Kline callback'lerini yönlendirir
    - Crossover event'lerini toplar ve raporlar
    """
    
    def __init__(self, config):
        self.config = config
        self.calculators: Dict[str, RealtimeEMACalculator] = {}
        
        # Global callbacks
        self.on_any_crossover: Optional[Callable] = None
        
        logger.info("📊 RealtimeEMAManager initialized")
    
    def add_symbol(
        self,
        symbol: str,
        ema_short: int = 5,
        ema_long: int = 20,
        warmup: int = 50
    ) -> RealtimeEMACalculator:
        """Yeni sembol ekle"""
        if symbol in self.calculators:
            logger.warning(f"⚠️ {symbol} already exists in EMA manager")
            return self.calculators[symbol]
        
        calculator = RealtimeEMACalculator(
            symbol=symbol,
            ema_short_period=ema_short,
            ema_long_period=ema_long,
            warmup_candles=warmup
        )
        
        # Set crossover callback
        calculator.set_crossover_callback(self._on_crossover)
        
        self.calculators[symbol] = calculator
        logger.info(f"✅ Added {symbol} to EMA manager")
        
        return calculator
    
    def remove_symbol(self, symbol: str):
        """Sembol kaldır"""
        if symbol in self.calculators:
            del self.calculators[symbol]
            logger.info(f"🗑️ Removed {symbol} from EMA manager")
    
    def process_kline(self, kline_data: Dict) -> Optional[Dict]:
        """Kline verisini ilgili calculator'a yönlendir"""
        symbol = kline_data.get('symbol')
        
        if not symbol:
            logger.warning("⚠️ Kline data missing symbol")
            return None
        
        if symbol not in self.calculators:
            logger.debug(f"⚠️ No calculator for {symbol}, skipping")
            return None
        
        return self.calculators[symbol].process_kline(kline_data)
    
    def _on_crossover(self, state: Dict):
        """Internal crossover handler"""
        logger.info(f"🎯 Crossover event from {state['symbol']}: {state.get('crossover')}")
        
        # Trigger global callback
        if self.on_any_crossover:
            self.on_any_crossover(state)
    
    def set_crossover_callback(self, callback: Callable):
        """Global crossover callback ayarla"""
        self.on_any_crossover = callback
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Tüm sembollerin istatistiklerini al"""
        return {
            symbol: calc.get_stats()
            for symbol, calc in self.calculators.items()
        }
    
    def get_warmed_up_symbols(self) -> List[str]:
        """Warmed up olan sembolleri döndür"""
        return [
            symbol
            for symbol, calc in self.calculators.items()
            if calc.is_warmed_up
        ]


# Module-level singleton
_ema_manager_instance: Optional[RealtimeEMAManager] = None


def get_ema_manager(config) -> RealtimeEMAManager:
    """Get or create EMA manager instance (singleton)"""
    global _ema_manager_instance
    
    if _ema_manager_instance is None:
        _ema_manager_instance = RealtimeEMAManager(config)
    
    return _ema_manager_instance


def reset_ema_manager():
    """Reset singleton instance (for testing)"""
    global _ema_manager_instance
    _ema_manager_instance = None
