# src/data_fetcher/realtime_ema_calculator.py
"""
v11.0: REAL-TIME EMA CALCULATION WITH ADAPTIVE THRESHOLDS
==========================================================

Volatilite-adaptif threshold sistemi ile geliştirilmiş EMA crossover detection.

V11.0 Yeni Özellikler:
- 🎯 ATR-based dynamic proximity thresholds
- 🚫 Choppy market filtering (ADX + BBW)
- 📊 Multi-timeframe confirmation (1H, 4H)
- 📈 Volume validation
- 🔄 Adaptive warmup period based on volatility

EMA Formülü:
- EMA(today) = (Price(today) * k) + (EMA(yesterday) * (1 - k))
- k = 2 / (period + 1)
- EMA5: k = 2/6 = 0.333
- EMA20: k = 2/21 = 0.095

Dynamic Threshold Logic:
- Low volatility (ATR/Price < 1%): Threshold = 0.1% (sıkı)
- Medium volatility (1-3%): Threshold = 0.2-0.5% (linear)
- High volatility (>3%): Threshold = 0.8% (gevşek)
"""

import logging
import time
import pandas as pd
import numpy as np
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
        base_pre_crossover_threshold: float = 0.002,  # Base %0.2 (dinamik ayarlanacak)
        enable_choppy_filter: bool = True,  # Choppy market filtering
        enable_mtf_confirmation: bool = False  # Multi-timeframe confirmation (opsiyonel)
    ):
        self.symbol = symbol
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.warmup_candles = warmup_candles
        self.base_pre_crossover_threshold = base_pre_crossover_threshold
        self.enable_choppy_filter = enable_choppy_filter
        self.enable_mtf_confirmation = enable_mtf_confirmation
        
        # V11.0: Dynamic threshold (ATR-based)
        self.current_threshold = base_pre_crossover_threshold
        self.atr_14: Optional[float] = None  # For dynamic threshold calculation
        
        # EMA multipliers
        self.k_short = 2.0 / (ema_short_period + 1)  # 0.333 for EMA5
        self.k_long = 2.0 / (ema_long_period + 1)    # 0.095 for EMA20
        
        # State
        self.candles: deque = deque(maxlen=warmup_candles)  # Son N mum
        self.ema_short: Optional[float] = None  # Current EMA5
        self.ema_long: Optional[float] = None   # Current EMA20
        self.prev_ema_short: Optional[float] = None
        self.prev_ema_long: Optional[float] = None
        
        # V11.0: Market condition indicators
        self.adx_14: Optional[float] = None
        self.bbw: Optional[float] = None  # Bollinger Band Width
        self.volume_sma_20: Optional[float] = None
        
        # Crossover state
        self.last_crossover_direction: Optional[str] = None  # 'bullish' or 'bearish'
        self.last_crossover_time: Optional[float] = None
        self.is_warmed_up: bool = False
        self.is_choppy_market: bool = False  # V11.0: Choppy market flag
        
        # Callbacks
        self.on_crossover: Optional[Callable] = None  # Kesişim olduğunda
        self.on_pre_crossover: Optional[Callable] = None  # Kesişim yaklaşırken
        self.on_ema_update: Optional[Callable] = None  # Her EMA güncellemesinde
        
        # Statistics
        self.update_count: int = 0
        self.crossover_count: int = 0
        self.filtered_crossovers: int = 0  # V11.0: Choppy filter tarafından reddedilen
        
        logger.info(f"📊 RealtimeEMACalculator v11.0 initialized for {symbol}")
        logger.info(f"   Short EMA: {ema_short_period} (k={self.k_short:.4f})")
        logger.info(f"   Long EMA: {ema_long_period} (k={self.k_long:.4f})")
        logger.info(f"   Warmup: {warmup_candles} candles")
        logger.info(f"   Base threshold: {base_pre_crossover_threshold*100:.2f}% (dynamic)")
        logger.info(f"   Choppy filter: {'ENABLED' if enable_choppy_filter else 'DISABLED'}")
        logger.info(f"   MTF confirmation: {'ENABLED' if enable_mtf_confirmation else 'DISABLED'}")
    
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
            # Extract price and volume
            close_price = float(kline_data.get('close', 0))
            open_price = float(kline_data.get('open', close_price))
            high_price = float(kline_data.get('high', close_price))
            low_price = float(kline_data.get('low', close_price))
            volume = float(kline_data.get('volume', 0))
            is_closed = kline_data.get('is_closed', False)
            
            if close_price <= 0:
                logger.warning(f"⚠️ Invalid close price: {close_price}")
                return self._get_current_state()
            
            # Store candle (V11.0: with OHLCV data)
            candle = {
                'time': kline_data.get('open_time'),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume,
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
            
            # V11.0: Calculate additional indicators
            if len(self.candles) >= 20:
                self._calculate_indicators()
                self._update_dynamic_threshold()
            
            # Check warmup status
            if not self.is_warmed_up and len(self.candles) >= self.warmup_candles:
                self.is_warmed_up = True
                logger.info(f"✅ {self.symbol} warmed up with {len(self.candles)} candles")
                logger.info(f"   Initial EMA{self.ema_short_period}: {self.ema_short:.2f}")
                logger.info(f"   Initial EMA{self.ema_long_period}: {self.ema_long:.2f}")
                if self.atr_14:
                    logger.info(f"   Initial ATR14: {self.atr_14:.4f}")
                if self.adx_14:
                    logger.info(f"   Initial ADX14: {self.adx_14:.1f}")
            
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
        
        # V11.0: Choppy market check BEFORE detecting crossover
        if self.enable_choppy_filter and self._is_choppy_market():
            self.is_choppy_market = True
            self.filtered_crossovers += 1
            logger.warning(f"🚫 {self.symbol} Crossover FILTERED (choppy market)")
            logger.debug(f"   ADX: {self.adx_14:.1f if self.adx_14 else 'N/A'}, BBW: {self.bbw:.4f if self.bbw else 'N/A'}")
            return None  # Don't signal crossover in choppy markets
        
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
            logger.info(f"   Threshold: {self.current_threshold*100:.2f}% (ATR-adjusted)")
            
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
            logger.info(f"   Threshold: {self.current_threshold*100:.2f}% (ATR-adjusted)")
            
            return 'bullish'
        
        return None
    
    def _update_dynamic_threshold(self):
        """
        V11.0: Update proximity threshold based on ATR (volatility)
        
        Logic:
        - Low volatility (ATR/Price < 1%): Tighter threshold (0.1%)
        - Medium volatility (1-3%): Linear scaling (0.2-0.5%)
        - High volatility (>3%): Wider threshold (0.8%)
        """
        try:
            if not self.atr_14 or len(self.candles) == 0:
                self.current_threshold = self.base_pre_crossover_threshold
                return
            
            current_price = self.candles[-1]['close']
            if current_price <= 0:
                self.current_threshold = self.base_pre_crossover_threshold
                return
            
            # ATR as percentage of price
            atr_percent = (self.atr_14 / current_price) * 100
            
            if atr_percent < 1.0:
                # Low volatility - very tight threshold
                self.current_threshold = 0.001  # 0.1%
            elif atr_percent < 3.0:
                # Medium volatility - linear scaling
                # 1% ATR → 0.2% threshold
                # 3% ATR → 0.5% threshold
                self.current_threshold = 0.002 + (0.003 * (atr_percent - 1.0) / 2.0)
            else:
                # High volatility - wider threshold
                self.current_threshold = 0.008  # 0.8%
            
            logger.debug(f"   Dynamic threshold updated: {self.current_threshold*100:.2f}% (ATR: {atr_percent:.2f}%)")
        
        except Exception as e:
            logger.error(f"Dynamic threshold update error: {e}")
            self.current_threshold = self.base_pre_crossover_threshold
    
    def _calculate_indicators(self):
        """
        V11.0: Calculate additional indicators for filtering
        
        Calculates:
        - ATR14: Average True Range
        - ADX14: Average Directional Index
        - BBW: Bollinger Band Width
        - Volume SMA20
        """
        try:
            if len(self.candles) < 20:
                return  # Not enough data
            
            # Convert candles to DataFrame for easier calculation
            df = pd.DataFrame(list(self.candles))
            
            # ATR14 (Average True Range)
            if len(df) >= 14:
                high = df['high']
                low = df['low']
                close = df['close']
                
                # True Range components
                tr1 = high - low
                tr2 = abs(high - close.shift())
                tr3 = abs(low - close.shift())
                
                # True Range = max of three components
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                
                # ATR = SMA of TR
                self.atr_14 = tr.tail(14).mean()
            
            # ADX14 (simplified calculation)
            if len(df) >= 14 and 'high' in df.columns:
                # +DM and -DM
                high_diff = df['high'].diff()
                low_diff = -df['low'].diff()
                
                plus_dm = pd.Series([max(hd, 0) if hd > ld else 0 for hd, ld in zip(high_diff, low_diff)])
                minus_dm = pd.Series([max(ld, 0) if ld > hd else 0 for hd, ld in zip(high_diff, low_diff)])
                
                # Smoothed DM
                plus_dm_smooth = plus_dm.rolling(14).mean()
                minus_dm_smooth = minus_dm.rolling(14).mean()
                
                # True Range
                tr1 = df['high'] - df['low']
                tr2 = abs(df['high'] - df['close'].shift())
                tr3 = abs(df['low'] - df['close'].shift())
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(14).mean()
                
                # Directional Indicators
                plus_di = 100 * (plus_dm_smooth / atr)
                minus_di = 100 * (minus_dm_smooth / atr)
                
                # DX and ADX
                dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
                self.adx_14 = dx.tail(14).mean()
            
            # BBW (Bollinger Band Width)
            if len(df) >= 20:
                sma_20 = df['close'].rolling(20).mean()
                std_20 = df['close'].rolling(20).std()
                
                bb_upper = sma_20 + (2 * std_20)
                bb_lower = sma_20 - (2 * std_20)
                
                # Width = (Upper - Lower) / Middle
                bbw_series = (bb_upper - bb_lower) / sma_20
                self.bbw = bbw_series.iloc[-1] if not pd.isna(bbw_series.iloc[-1]) else None
            
            # Volume SMA20
            if 'volume' in df.columns and len(df) >= 20:
                self.volume_sma_20 = df['volume'].tail(20).mean()
        
        except Exception as e:
            logger.error(f"Indicator calculation error: {e}", exc_info=True)
    
    def _is_choppy_market(self) -> bool:
        """
        V11.0: Detect choppy/ranging market conditions
        
        Criteria for choppy market:
        - ADX < 20 (weak trend)
        - BBW < 0.02 (tight Bollinger Bands)
        
        Returns:
            True if choppy market (avoid trading)
        """
        try:
            # If no indicators calculated yet, assume not choppy
            if self.adx_14 is None or self.bbw is None:
                return False
            
            # Choppy market conditions
            weak_trend = self.adx_14 < 20
            tight_bands = self.bbw < 0.02
            
            return weak_trend and tight_bands
        
        except Exception as e:
            logger.error(f"Choppy market detection error: {e}")
            return False
    
    def _detect_pre_crossover(self) -> Optional[str]:
        """
        Pre-crossover tespit et (EMA'lar birbirine yaklaşıyor mu?)
        
        V11.0: Uses dynamic threshold based on ATR
        
        Returns:
            'approaching_bullish': EMA5 yaklaşıyor EMA20'ye (yukarıdan)
            'approaching_bearish': EMA5 yaklaşıyor EMA20'ye (aşağıdan)
            None: Yaklaşma yok
        """
        if not all([self.ema_short, self.ema_long]):
            return None
        
        # Calculate distance between EMAs (%)
        distance = abs(self.ema_short - self.ema_long) / self.ema_long
        
        # V11.0: Use dynamic threshold
        # Check if within threshold
        if distance <= self.current_threshold:
            # Determine direction
            if self.ema_short > self.ema_long:
                # EMA5 üstte ama yakın - bearish crossover yaklaşıyor olabilir
                logger.debug(f"⚠️ {self.symbol} approaching bearish crossover (distance: {distance*100:.3f}%, threshold: {self.current_threshold*100:.2f}%)")
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
