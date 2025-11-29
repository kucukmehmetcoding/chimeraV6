"""
Momentum Scalping Strategy - DeepSeek Tarafından Tasarlandı
============================================================

Hızlı momentum yakalama stratejisi:
- EMA 9/21 cross ile giriş
- RSI 50 seviyesi ile momentum teyidi
- Volume confirmation
- ATR volatilite filtresi
- Spread filtresi
- Trend filtresi (EMA50 > EMA200)

TP: 1.5%
SL: 0.8%
RR: ~1.87

Timeframe: 1m veya 5m (scalping için)
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Strategy Parameters
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 50
EMA_MACRO = 200
RSI_PERIOD = 14
RSI_LONG_THRESHOLD = 50
RSI_SHORT_THRESHOLD = 50
VOLUME_MA_PERIOD = 20
ATR_PERIOD = 14

# Risk Management
TP_PERCENT = 1.5  # 1.5% take profit
SL_PERCENT = 0.8  # 0.8% stop loss

# Filters
MIN_ATR_PERCENT = 0.5  # Minimum 0.5% volatility
MAX_SPREAD_PERCENT = 0.05  # Maximum 0.05% spread
ENABLE_TRADING_HOURS = False  # Set True for stock market hours only


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Momentum scalping için gerekli göstergeleri hesaplar.
    
    Args:
        df: OHLCV DataFrame
        
    Returns:
        Göstergeler eklenmiş DataFrame
    """
    try:
        if df.empty or len(df) < max(EMA_MACRO, VOLUME_MA_PERIOD, RSI_PERIOD):
            logger.warning("Yetersiz veri - en az 200 bar gerekli")
            return df
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].astype(np.float64).values  # Ensure float64 for talib
        
        # EMAs
        df['ema9'] = talib.EMA(close, timeperiod=EMA_FAST)
        df['ema21'] = talib.EMA(close, timeperiod=EMA_SLOW)
        df['ema50'] = talib.EMA(close, timeperiod=EMA_TREND)
        df['ema200'] = talib.EMA(close, timeperiod=EMA_MACRO)
        
        # RSI
        df['rsi14'] = talib.RSI(close, timeperiod=RSI_PERIOD)
        
        # Volume MA
        df['volume_ma'] = talib.SMA(volume, timeperiod=VOLUME_MA_PERIOD)
        
        # ATR (volatility)
        df['atr14'] = talib.ATR(high, low, close, timeperiod=ATR_PERIOD)
        df['atr_percent'] = (df['atr14'] / df['close']) * 100
        
        # EMA Cross Detection
        df['ema_diff'] = df['ema9'] - df['ema21']
        df['ema_cross_up'] = (df['ema_diff'] > 0) & (df['ema_diff'].shift(1) <= 0)
        df['ema_cross_down'] = (df['ema_diff'] < 0) & (df['ema_diff'].shift(1) >= 0)
        
        # Trend Detection
        df['uptrend'] = df['ema50'] > df['ema200']
        df['downtrend'] = df['ema50'] < df['ema200']
        
        logger.debug(f"Göstergeler hesaplandı - son EMA9: {df['ema9'].iloc[-1]:.2f}, "
                    f"EMA21: {df['ema21'].iloc[-1]:.2f}, RSI: {df['rsi14'].iloc[-1]:.2f}")
        
        return df
        
    except Exception as e:
        logger.error(f"Gösterge hesaplama hatası: {e}", exc_info=True)
        return df


def check_trading_hours() -> bool:
    """
    Trading saatleri kontrolü (opsiyonel).
    Kripto için genelde 24/7, hisse senetleri için kullanılabilir.
    
    Returns:
        True if trading hours are active
    """
    if not ENABLE_TRADING_HOURS:
        return True
    
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    
    # Örnek: 09:00 - 16:00 arası (yerel saat)
    return 9 <= hour < 16


def calculate_spread(row: pd.Series) -> float:
    """
    Spread hesaplar (high-low range).
    
    Args:
        row: DataFrame row with high/low/close
        
    Returns:
        Spread percentage
    """
    spread = ((row['high'] - row['low']) / row['close']) * 100
    return spread


def analyze_momentum_scalping(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN"
) -> Optional[Dict]:
    """
    Momentum scalping stratejisi ana analiz fonksiyonu.
    
    Strategy Rules:
    LONG:
        - EMA9 > EMA21 (momentum up)
        - RSI > 50 (bullish momentum)
        - Volume > Volume MA (confirmation)
        - EMA50 > EMA200 (uptrend)
        - ATR > 0.5% (volatility check)
        - Spread < 0.05% (tight spread)
    
    SHORT:
        - EMA9 < EMA21 (momentum down)
        - RSI < 50 (bearish momentum)
        - Volume > Volume MA (confirmation)
        - EMA50 < EMA200 (downtrend)
        - ATR > 0.5%
        - Spread < 0.05%
    
    Args:
        df: OHLCV DataFrame with indicators
        symbol: Trading pair symbol
        
    Returns:
        Signal dictionary or None
    """
    try:
        if df.empty or len(df) < 2:
            logger.warning(f"{symbol}: DataFrame boş veya yetersiz")
            return None
        
        # Check required columns
        required_cols = ['ema9', 'ema21', 'ema50', 'ema200', 'rsi14', 
                        'volume_ma', 'atr_percent']
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"{symbol}: Gerekli göstergeler eksik")
            return None
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        # Check for NaN values
        if last_row[required_cols].isna().any():
            logger.warning(f"{symbol}: Son bar'da NaN değerler var")
            return None
        
        # Filter 1: Trading Hours (optional)
        if not check_trading_hours():
            logger.debug(f"{symbol}: Trading saatleri dışında")
            return None
        
        # Filter 2: Trend Filter
        uptrend = last_row['ema50'] > last_row['ema200']
        downtrend = last_row['ema50'] < last_row['ema200']
        
        if not uptrend and not downtrend:
            logger.debug(f"{symbol}: Neutral trend (EMA50 ≈ EMA200)")
            return None
        
        # Filter 3: Volatility Filter
        if last_row['atr_percent'] < MIN_ATR_PERCENT:
            logger.debug(f"{symbol}: Düşük volatilite - ATR: {last_row['atr_percent']:.2f}%")
            return None
        
        # Filter 4: Spread Filter
        spread = calculate_spread(last_row)
        if spread > MAX_SPREAD_PERCENT:
            logger.debug(f"{symbol}: Geniş spread - {spread:.3f}%")
            return None
        
        # Extract values
        ema9 = last_row['ema9']
        ema21 = last_row['ema21']
        rsi = last_row['rsi14']
        volume = last_row['volume']
        volume_ma = last_row['volume_ma']
        close = last_row['close']
        
        # Check if fresh cross (within last 2 bars)
        fresh_cross_up = last_row['ema_cross_up'] or prev_row['ema_cross_up']
        fresh_cross_down = last_row['ema_cross_down'] or prev_row['ema_cross_down']
        
        signal = None
        direction = None
        confidence = 0.75  # Base confidence
        
        # LONG Signal
        if (ema9 > ema21 and 
            rsi > RSI_LONG_THRESHOLD and 
            volume > volume_ma and
            uptrend):
            
            signal = "LONG"
            direction = 1
            
            # Boost confidence if fresh cross
            if fresh_cross_up:
                confidence = 0.90
                logger.info(f"{symbol}: 🚀 FRESH BULLISH CROSS detected!")
            
            logger.info(f"{symbol}: LONG signal - EMA9: {ema9:.2f} > EMA21: {ema21:.2f}, "
                       f"RSI: {rsi:.2f}, Volume: {volume:.0f} > MA: {volume_ma:.0f}")
        
        # SHORT Signal
        elif (ema9 < ema21 and 
              rsi < RSI_SHORT_THRESHOLD and 
              volume > volume_ma and
              downtrend):
            
            signal = "SHORT"
            direction = -1
            
            # Boost confidence if fresh cross
            if fresh_cross_down:
                confidence = 0.90
                logger.info(f"{symbol}: 🔻 FRESH BEARISH CROSS detected!")
            
            logger.info(f"{symbol}: SHORT signal - EMA9: {ema9:.2f} < EMA21: {ema21:.2f}, "
                       f"RSI: {rsi:.2f}, Volume: {volume:.0f} > MA: {volume_ma:.0f}")
        
        if signal is None:
            logger.debug(f"{symbol}: Sinyal yok - EMA9: {ema9:.2f}, EMA21: {ema21:.2f}, "
                        f"RSI: {rsi:.2f}, Trend: {'UP' if uptrend else 'DOWN'}")
            return None
        
        # Calculate Entry, TP, SL
        entry_price = close
        
        if direction == 1:  # LONG
            tp_price = entry_price * (1 + TP_PERCENT / 100)
            sl_price = entry_price * (1 - SL_PERCENT / 100)
        else:  # SHORT
            tp_price = entry_price * (1 - TP_PERCENT / 100)
            sl_price = entry_price * (1 + SL_PERCENT / 100)
        
        # Calculate RR ratio
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        result = {
            'signal': signal,
            'direction': direction,
            'entry_price': entry_price,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'rr_ratio': rr_ratio,
            'confidence': confidence,
            'timeframe': '1m',  # or extract from df if available
            'strategy': 'momentum_scalping',
            'indicators': {
                'ema9': ema9,
                'ema21': ema21,
                'ema50': last_row['ema50'],
                'ema200': last_row['ema200'],
                'rsi': rsi,
                'volume': volume,
                'volume_ma': volume_ma,
                'atr_percent': last_row['atr_percent'],
                'spread_percent': spread,
                'fresh_cross': fresh_cross_up or fresh_cross_down
            },
            'metadata': {
                'symbol': symbol,
                'timestamp': df.index[-1] if len(df.index) > 0 else pd.Timestamp.now(),
                'uptrend': uptrend,
                'downtrend': downtrend
            }
        }
        
        logger.info(f"{symbol}: ✅ {signal} signal generated - "
                   f"Entry: {entry_price:.4f}, TP: {tp_price:.4f}, SL: {sl_price:.4f}, "
                   f"RR: {rr_ratio:.2f}, Confidence: {confidence:.0%}")
        
        return result
        
    except Exception as e:
        logger.error(f"{symbol}: Momentum scalping analiz hatası: {e}", exc_info=True)
        return None


def get_strategy_info() -> Dict:
    """
    Strateji bilgilerini döndürür.
    
    Returns:
        Strategy information dictionary
    """
    return {
        'name': 'Momentum Scalping Strategy',
        'version': '1.0',
        'designer': 'DeepSeek AI',
        'timeframe': '1m or 5m',
        'type': 'scalping',
        'indicators': {
            'ema_fast': EMA_FAST,
            'ema_slow': EMA_SLOW,
            'ema_trend': EMA_TREND,
            'ema_macro': EMA_MACRO,
            'rsi_period': RSI_PERIOD,
            'volume_ma': VOLUME_MA_PERIOD,
            'atr_period': ATR_PERIOD
        },
        'risk_management': {
            'tp_percent': TP_PERCENT,
            'sl_percent': SL_PERCENT,
            'rr_target': TP_PERCENT / SL_PERCENT
        },
        'filters': {
            'min_atr_percent': MIN_ATR_PERCENT,
            'max_spread_percent': MAX_SPREAD_PERCENT,
            'trading_hours_enabled': ENABLE_TRADING_HOURS
        },
        'rules': {
            'long': [
                'EMA9 > EMA21',
                'RSI > 50',
                'Volume > Volume MA',
                'EMA50 > EMA200 (uptrend)',
                'ATR > 0.5%',
                'Spread < 0.05%'
            ],
            'short': [
                'EMA9 < EMA21',
                'RSI < 50',
                'Volume > Volume MA',
                'EMA50 < EMA200 (downtrend)',
                'ATR > 0.5%',
                'Spread < 0.05%'
            ]
        }
    }


# Test the strategy
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("Momentum Scalping Strategy - Test")
    print("=" * 60)
    
    # Print strategy info
    info = get_strategy_info()
    print(f"\nStrategy: {info['name']} v{info['version']}")
    print(f"Designer: {info['designer']}")
    print(f"Timeframe: {info['timeframe']}")
    print(f"Type: {info['type']}")
    print(f"\nRisk Management:")
    print(f"  TP: {info['risk_management']['tp_percent']}%")
    print(f"  SL: {info['risk_management']['sl_percent']}%")
    print(f"  Target RR: {info['risk_management']['rr_target']:.2f}")
    print(f"\nFilters:")
    print(f"  Min ATR: {info['filters']['min_atr_percent']}%")
    print(f"  Max Spread: {info['filters']['max_spread_percent']}%")
    print(f"  Trading Hours: {info['filters']['trading_hours_enabled']}")
    
    print("\n" + "=" * 60)
    print("Test with sample data...")
    print("=" * 60)
    
    # Create sample data
    dates = pd.date_range(start='2024-01-01', periods=300, freq='1min')
    np.random.seed(42)
    
    # Generate trending price data
    base_price = 50000
    trend = np.linspace(0, 1000, 300)
    noise = np.random.randn(300) * 100
    
    sample_data = pd.DataFrame({
        'timestamp': dates,
        'open': base_price + trend + noise,
        'high': base_price + trend + noise + np.abs(np.random.randn(300) * 50),
        'low': base_price + trend + noise - np.abs(np.random.randn(300) * 50),
        'close': base_price + trend + noise + np.random.randn(300) * 30,
        'volume': np.random.randint(100, 1000, 300)
    })
    
    # Calculate indicators
    sample_data = calculate_indicators(sample_data)
    
    # Analyze
    result = analyze_momentum_scalping(sample_data, symbol="BTCUSDT_TEST")
    
    if result:
        print(f"\n✅ Signal Found!")
        print(f"Signal: {result['signal']}")
        print(f"Entry: ${result['entry_price']:.2f}")
        print(f"TP: ${result['tp_price']:.2f}")
        print(f"SL: ${result['sl_price']:.2f}")
        print(f"RR Ratio: {result['rr_ratio']:.2f}")
        print(f"Confidence: {result['confidence']:.0%}")
        print(f"\nIndicators:")
        for key, value in result['indicators'].items():
            if isinstance(value, (int, float)):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
    else:
        print("\n❌ No signal generated")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
