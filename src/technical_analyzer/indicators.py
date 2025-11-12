# src/technical_analyzer/indicators.py

import pandas as pd
import talib
import logging
import numpy as np

# Loglamayı ayarla
logger = logging.getLogger(__name__)

# TA-Lib kontrolü
try:
    talib_version = talib.__version__
    # logger.info(f"✅ TA-Lib kütüphanesi yüklendi (Versiyon: {talib_version}).")
except AttributeError:
    logger.critical("❌ TA-Lib kütüphanesi düzgün yüklenmemiş!")
    raise ImportError("TA-Lib yüklenemedi.")


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verilen DataFrame'e tüm gerekli teknik göstergeleri hesaplar ve ekler.
    GÜNCELLENDİ: EMA8 ve EMA21 eklendi (Gelişmiş Scalp Stratejisi için).
    """
    if df.empty:
        logger.warning("Gösterge hesaplaması için boş DataFrame alındı.")
        return df
        
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    if not all(col in df.columns for col in required_cols):
        logger.error(f"Gösterge hesaplaması için gerekli sütunlar eksik: {required_cols}")
        return df

    for col in required_cols:
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        except Exception as e:
             logger.error(f"'{col}' sütunu sayısal tipe dönüştürülemedi: {e}")
             return df

    try:
        logger.debug(f"⏳ {len(df)} mum için teknik göstergeler hesaplanıyor...")

        # --- Strateji 1: MOMENTUM_SCALP (Eski) ---
        df['ema5'] = talib.EMA(df['close'], timeperiod=5)
        df['ema20'] = talib.EMA(df['close'], timeperiod=20)

        # --- YENİ EKLENDİ: Strateji 2: ADVANCED_SCALP ---
        df['ema8'] = talib.EMA(df['close'], timeperiod=8)
        df['ema21'] = talib.EMA(df['close'], timeperiod=21)
        # ---------------------------------------------

        # --- Strateji 3: PULLBACK (Trend) ---
        df['ema50'] = talib.EMA(df['close'], timeperiod=50)
        df['sma200'] = talib.SMA(df['close'], timeperiod=200)

        # --- Ortak Göstergeler ---
        df['rsi14'] = talib.RSI(df['close'], timeperiod=14)
        macd, macdsignal, macdhist = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['macd'] = macd
        df['macd_signal'] = macdsignal
        df['macd_hist'] = macdhist
        upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        df['bbw'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'].replace(0, np.nan)
        df['adx14'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        df['atr14'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        if df['volume'].dtype in ['float64', 'int64']:
             df['volume_sma20'] = talib.SMA(df['volume'].astype(float), timeperiod=20)
        else:
             df['volume_sma20'] = np.nan

        # --- Gelişmiş TA-Lib Göstergeleri (Aşama 2) ---
        try:
            k, d = talib.STOCHRSI(df['close'], timeperiod=14, fastk_period=14, fastd_period=3, fastd_matype=0)
            df['stoch_rsi_k'] = k
            df['stoch_rsi_d'] = d
        except Exception: df['stoch_rsi_k'] = np.nan; df['stoch_rsi_d'] = np.nan
        
        try: df['roc5'] = talib.ROC(df['close'], timeperiod=5)
        except Exception: df['roc5'] = np.nan
        
        try: df['willr14'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=14)
        except Exception: df['willr14'] = np.nan
        
        try: df['mfi14'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
        except Exception: df['mfi14'] = np.nan

        # --- YENİ EKLENDİ: v4.0 Gelişmiş Göstergeler ---
        try:
            df = calculate_vwap(df)
        except Exception as e:
            logger.error(f"VWAP hesaplama hatası: {e}")
            df['vwap'] = np.nan
        
        try:
            df = calculate_supertrend(df, period=10, multiplier=3.0)
        except Exception as e:
            logger.error(f"Supertrend hesaplama hatası: {e}")
            df['supertrend'] = np.nan
            df['supertrend_direction'] = np.nan
        
        try:
            df = enhance_stochastic_rsi(df)
        except Exception as e:
            logger.error(f"Stochastic RSI enhancement hatası: {e}")
        # ----------------------------------------------

        # --- DEBUG: Final column check (CRITICAL LEVEL for visibility) ---
        critical_indicators = ['rsi14', 'macd_hist', 'atr14', 'volume_sma20', 'vwap', 'supertrend_direction']
        missing_cols = [col for col in critical_indicators if col not in df.columns]
        if missing_cols:
            logger.error(f"❌ CRITICAL-IND: Missing columns after calculation: {missing_cols}")
            logger.error(f"   Available columns: {list(df.columns)}")
        else:
            logger.info(f"✅ CRITICAL-IND: All {len(critical_indicators)} indicators present in df")
        
        # Check last row for NaN in critical indicators
        if not df.empty:
            last_row = df.iloc[-1]
            nan_indicators = [col for col in critical_indicators if col in df.columns and pd.isna(last_row[col])]
            if nan_indicators:
                logger.warning(f"⚠️ CRITICAL-IND: Last row has NaN in: {nan_indicators}")
            else:
                logger.info(f"✅ CRITICAL-IND: Last row has NO NaN in critical indicators")
        # ----------------------------------------

        logger.debug("✅ Teknik göstergeler başarıyla hesaplandı.")
        
    except Exception as e:
        logger.error(f"❌ TA-Lib göstergeleri hesaplanırken hata oluştu: {e}", exc_info=True)
        return df

    return df


# --- YENİ EKLENDİ: Gelişmiş Göstergeler (v4.0 Enhancement) ---

def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    VWAP (Volume Weighted Average Price) hesaplar.
    Intraday işlemler için kritik - hacim ağırlıklı ortalama fiyat.
    
    VWAP = Σ(Price × Volume) / Σ(Volume)
    
    NOT: VWAP genellikle günlük reset edilir, ancak burada kümülatif hesaplıyoruz.
    """
    try:
        if df.empty or len(df) < 2:
            logger.warning("VWAP hesaplaması için yetersiz veri")
            df['vwap'] = np.nan
            return df
        
        # Tipik fiyat (High + Low + Close) / 3
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Kümülatif (Tipik Fiyat × Hacim)
        df['tp_volume'] = df['typical_price'] * df['volume']
        
        # Kümülatif toplam
        df['cumulative_tp_volume'] = df['tp_volume'].cumsum()
        df['cumulative_volume'] = df['volume'].cumsum()
        
        # VWAP = Kümülatif (TP×Vol) / Kümülatif Vol
        df['vwap'] = df['cumulative_tp_volume'] / df['cumulative_volume'].replace(0, np.nan)
        
        # Geçici sütunları temizle
        df.drop(['typical_price', 'tp_volume', 'cumulative_tp_volume', 'cumulative_volume'], 
                axis=1, inplace=True, errors='ignore')
        
        logger.debug("✅ VWAP başarıyla hesaplandı")
        return df
        
    except Exception as e:
        logger.error(f"VWAP hesaplanırken hata: {e}", exc_info=True)
        df['vwap'] = np.nan
        return df


def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    Supertrend göstergesini hesaplar.
    Trend takibi için kullanılır - basit ve etkili.
    
    Mantık:
    - ATR bazlı dinamik bantlar
    - Fiyat üst bantın üstündeyse: UPTREND (yeşil)
    - Fiyat alt bantın altındaysa: DOWNTREND (kırmızı)
    
    Parametreler:
        period: ATR periyodu (default: 10)
        multiplier: ATR çarpanı (default: 3.0)
    """
    try:
        if df.empty or len(df) < period + 1:
            logger.warning(f"Supertrend için yetersiz veri (gerekli: {period+1}, mevcut: {len(df)})")
            df['supertrend'] = np.nan
            df['supertrend_direction'] = np.nan
            return df
        
        # ATR hesapla (eğer yoksa)
        if 'atr14' not in df.columns:
            df['atr_temp'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
        else:
            df['atr_temp'] = df['atr14']  # Mevcut ATR'yi kullan
        
        # Temel bantlar
        hl_avg = (df['high'] + df['low']) / 2
        df['basic_upper_band'] = hl_avg + (multiplier * df['atr_temp'])
        df['basic_lower_band'] = hl_avg - (multiplier * df['atr_temp'])
        
        # Final bantlar (önceki değerlerle karşılaştırma)
        df['final_upper_band'] = df['basic_upper_band']
        df['final_lower_band'] = df['basic_lower_band']
        
        for i in range(period, len(df)):
            # Üst bant: Mevcut < Önceki VE Close[i-1] > Üst Bant[i-1] ise öncekini kullan
            if df['basic_upper_band'].iloc[i] < df['final_upper_band'].iloc[i-1] or \
               df['close'].iloc[i-1] > df['final_upper_band'].iloc[i-1]:
                df.loc[df.index[i], 'final_upper_band'] = df['basic_upper_band'].iloc[i]
            else:
                df.loc[df.index[i], 'final_upper_band'] = df['final_upper_band'].iloc[i-1]
            
            # Alt bant: Mevcut > Önceki VE Close[i-1] < Alt Bant[i-1] ise öncekini kullan
            if df['basic_lower_band'].iloc[i] > df['final_lower_band'].iloc[i-1] or \
               df['close'].iloc[i-1] < df['final_lower_band'].iloc[i-1]:
                df.loc[df.index[i], 'final_lower_band'] = df['basic_lower_band'].iloc[i]
            else:
                df.loc[df.index[i], 'final_lower_band'] = df['final_lower_band'].iloc[i-1]
        
        # Supertrend değeri ve yönü
        df['supertrend'] = np.nan
        df['supertrend_direction'] = np.nan  # 1: UPTREND, -1: DOWNTREND
        
        for i in range(period, len(df)):
            # Önceki trend (başlangıç için varsayılan UP)
            prev_direction = 1 if i == period else df['supertrend_direction'].iloc[i-1]
            
            if prev_direction == 1:  # Önceki UPTREND
                if df['close'].iloc[i] <= df['final_lower_band'].iloc[i]:
                    df.loc[df.index[i], 'supertrend'] = df['final_upper_band'].iloc[i]
                    df.loc[df.index[i], 'supertrend_direction'] = -1
                else:
                    df.loc[df.index[i], 'supertrend'] = df['final_lower_band'].iloc[i]
                    df.loc[df.index[i], 'supertrend_direction'] = 1
            else:  # Önceki DOWNTREND
                if df['close'].iloc[i] >= df['final_upper_band'].iloc[i]:
                    df.loc[df.index[i], 'supertrend'] = df['final_lower_band'].iloc[i]
                    df.loc[df.index[i], 'supertrend_direction'] = 1
                else:
                    df.loc[df.index[i], 'supertrend'] = df['final_upper_band'].iloc[i]
                    df.loc[df.index[i], 'supertrend_direction'] = -1
        
        # Geçici sütunları temizle
        df.drop(['atr_temp', 'basic_upper_band', 'basic_lower_band', 
                 'final_upper_band', 'final_lower_band'], 
                axis=1, inplace=True, errors='ignore')
        
        logger.debug(f"✅ Supertrend hesaplandı (period={period}, multiplier={multiplier})")
        return df
        
    except Exception as e:
        logger.error(f"Supertrend hesaplanırken hata: {e}", exc_info=True)
        df['supertrend'] = np.nan
        df['supertrend_direction'] = np.nan
        return df


def enhance_stochastic_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mevcut Stochastic RSI hesaplamasını iyileştirir ve ek bilgiler ekler.
    
    Stochastic RSI:
    - RSI'ın stokastik versiyonu
    - 0-100 arasında normalize edilmiş
    - %K (fast line) ve %D (slow line - %K'nın SMA'sı)
    - 20 altı: Aşırı Satım
    - 80 üstü: Aşırı Alım
    """
    try:
        if 'stoch_rsi_k' in df.columns and 'stoch_rsi_d' in df.columns:
            # Zaten hesaplanmış, sadece sinyal ekle
            df['stoch_rsi_signal'] = np.where(
                (df['stoch_rsi_k'] > df['stoch_rsi_d']) & 
                (df['stoch_rsi_k'].shift(1) <= df['stoch_rsi_d'].shift(1)), 
                'BUY',  # Golden cross
                np.where(
                    (df['stoch_rsi_k'] < df['stoch_rsi_d']) & 
                    (df['stoch_rsi_k'].shift(1) >= df['stoch_rsi_d'].shift(1)), 
                    'SELL',  # Death cross
                    'HOLD'
                )
            )
            
            # Aşırı bölgeler
            df['stoch_rsi_oversold'] = df['stoch_rsi_k'] < 20
            df['stoch_rsi_overbought'] = df['stoch_rsi_k'] > 80
            
            logger.debug("✅ Stochastic RSI sinyalleri eklendi")
        else:
            logger.warning("Stochastic RSI hesaplanmamış, enhance_stochastic_rsi atlandı")
        
        return df
        
    except Exception as e:
        logger.error(f"Stochastic RSI geliştirme hatası: {e}", exc_info=True)
        return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate Average True Range (ATR) for volatility-based TP/SL
    
    Args:
        df: DataFrame with OHLC data
        period: ATR period (default: 14)
    
    Returns:
        float: ATR value (latest)
    """
    try:
        if df.empty or len(df) < period:
            logger.warning(f"Insufficient data for ATR calculation (need {period}, got {len(df)})")
            return 0.0
        
        # Ensure numeric types
        high = pd.to_numeric(df['high'], errors='coerce')
        low = pd.to_numeric(df['low'], errors='coerce')
        close = pd.to_numeric(df['close'], errors='coerce')
        
        # Calculate True Range components
        tr1 = high - low  # High - Low
        tr2 = abs(high - close.shift())  # |High - Previous Close|
        tr3 = abs(low - close.shift())   # |Low - Previous Close|
        
        # True Range = max of the three
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR = Simple Moving Average of TR
        atr = tr.rolling(window=period).mean()
        
        # Return latest ATR value
        latest_atr = atr.iloc[-1]
        
        if pd.isna(latest_atr) or latest_atr <= 0:
            logger.warning(f"Invalid ATR value: {latest_atr}, returning 0")
            return 0.0
        
        logger.debug(f"✅ ATR({period}) calculated: {latest_atr:.8f}")
        return float(latest_atr)
        
    except Exception as e:
        logger.error(f"ATR calculation error: {e}", exc_info=True)
        return 0.0


# ═══════════════════════════════════════════════════════════════════════
# v11.0: HTF-LTF Strategy Helper Functions
# ═══════════════════════════════════════════════════════════════════════

def add_htf_indicators(df: pd.DataFrame, timeframe: str = '1h') -> pd.DataFrame:
    """
    HTF (1H) için gerekli indicator'ları ekle
    
    Required indicators for HTF filter:
    - EMA50
    - RSI14
    - MACD Histogram
    
    Args:
        df: OHLCV DataFrame
        timeframe: Timeframe string (for logging)
    
    Returns:
        DataFrame with HTF indicators
    """
    if df is None or df.empty:
        logger.warning(f"HTF indicators: Empty DataFrame for {timeframe}")
        return df
    
    try:
        logger.debug(f"⏳ Adding HTF indicators for {timeframe}...")
        
        # EMA50
        df['ema50'] = talib.EMA(df['close'], timeperiod=50)
        
        # RSI14
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        
        # MACD
        macd, macd_signal, macd_hist = talib.MACD(
            df['close'], 
            fastperiod=12, 
            slowperiod=26, 
            signalperiod=9
        )
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist
        
        logger.debug(f"✅ HTF indicators added for {timeframe}")
        return df
        
    except Exception as e:
        logger.error(f"HTF indicator calculation error: {e}", exc_info=True)
        return df


def add_ltf_indicators(df: pd.DataFrame, timeframe: str = '15m') -> pd.DataFrame:
    """
    LTF (15M) için gerekli indicator'ları ekle
    
    Required indicators for LTF trigger:
    - EMA5, EMA20
    - RSI14
    - MACD Histogram
    - ATR14
    - Volume SMA20
    
    Args:
        df: OHLCV DataFrame
        timeframe: Timeframe string (for logging)
    
    Returns:
        DataFrame with LTF indicators
    """
    if df is None or df.empty:
        logger.warning(f"LTF indicators: Empty DataFrame for {timeframe}")
        return df
    
    try:
        logger.debug(f"⏳ Adding LTF indicators for {timeframe}...")
        
        # EMA5 ve EMA20
        df['ema5'] = talib.EMA(df['close'], timeperiod=5)
        df['ema20'] = talib.EMA(df['close'], timeperiod=20)
        
        # RSI14
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        
        # MACD
        macd, macd_signal, macd_hist = talib.MACD(
            df['close'], 
            fastperiod=12, 
            slowperiod=26, 
            signalperiod=9
        )
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist
        
        # ATR14
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        
        # Volume SMA20
        if df['volume'].dtype in ['float64', 'int64']:
            df['volume_sma20'] = talib.SMA(df['volume'].astype(float), timeperiod=20)
        else:
            df['volume_sma20'] = np.nan
        
        logger.debug(f"✅ LTF indicators added for {timeframe}")
        return df
        
    except Exception as e:
        logger.error(f"LTF indicator calculation error: {e}", exc_info=True)
        return df