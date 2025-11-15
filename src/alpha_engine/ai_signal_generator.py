"""
🤖 AI SIGNAL GENERATOR
=======================

DeepSeek (Primary) + Gemini (Fallback) kullanarak 
multi-timeframe teknik analiz verilerinden trading sinyalleri üretir.

Flow:
1. Market scanner'dan 1H + 15M teknik analiz verilerini al
2. DeepSeek'e profesyonel trading prompt ile gönder
3. Confidence >= 70 ise → sinyal kullan
4. Confidence < 70 ise → Gemini'ye double-check
5. İki AI anlaşıyorsa → confidence boost
6. Çelişki varsa → HOLD (güvenli seçenek)

Author: ChimeraBot Team
Version: 1.0.0
"""

import logging
import os
import json
from typing import Dict, Optional, Tuple
from datetime import datetime
import pandas as pd

# AI Clients
from openai import OpenAI  # DeepSeek
try:
    import google.generativeai as genai  # Gemini
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Gemini SDK bulunamadı - fallback devre dışı")

logger = logging.getLogger(__name__)


class AISignalGenerator:
    """
    AI-powered trading signal generator
    
    Uses DeepSeek as primary AI (free, unlimited)
    Falls back to Gemini for low-confidence signals (paid, limited)
    """
    
    def __init__(self, config):
        """
        Initialize AI clients
        
        Args:
            config: ChimeraBot config module
        """
        self.config = config
        
        # DeepSeek (Primary - Ücretsiz)
        self.deepseek_client = self._init_deepseek()
        self.deepseek_model = getattr(config, 'DEEPSEEK_MODEL', 'deepseek-chat')
        
        # Gemini (Fallback - Ücretli)
        self.gemini_client = None
        self.gemini_model = None
        self.gemini_enabled = False  # 🔴 DEVRE DIŞI BIRAKILDI
        self.gemini_daily_calls = 0
        self.max_daily_gemini_calls = getattr(config, 'MAX_DAILY_GEMINI_CALLS', 30)
        
        # Gemini başlatma devre dışı
        # if self.gemini_enabled and GEMINI_AVAILABLE:
        #     self.gemini_client = self._init_gemini()
        #     self.gemini_model = getattr(config, 'GEMINI_MODEL', 'gemini-1.5-flash')
        
        # Thresholds
        self.min_confidence = getattr(config, 'MIN_AI_CONFIDENCE_SCORE', 70)
        self.fallback_threshold = 60  # Bu değerin altında Gemini'ye sor
        
        logger.info(f"✅ AISignalGenerator initialized")
        logger.info(f"   Primary: DeepSeek ({self.deepseek_model})")
        logger.info(f"   Fallback: {'Gemini (' + self.gemini_model + ')' if self.gemini_enabled else 'Disabled'}")
        logger.info(f"   Min confidence: {self.min_confidence}")
    
    def _init_deepseek(self) -> Optional[OpenAI]:
        """Initialize DeepSeek API client"""
        try:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                logger.error("❌ DEEPSEEK_API_KEY bulunamadı!")
                return None
            
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            logger.info("✅ DeepSeek client initialized")
            return client
            
        except Exception as e:
            logger.error(f"❌ DeepSeek init hatası: {e}")
            return None
    
    def _init_gemini(self) -> Optional[object]:
        """Initialize Gemini API client"""
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("⚠️ GEMINI_API_KEY bulunamadı - fallback devre dışı")
                return None
            
            genai.configure(api_key=api_key)
            logger.info("✅ Gemini client initialized")
            return genai
            
        except Exception as e:
            logger.error(f"❌ Gemini init hatası: {e}")
            return None
    
    def generate_signal(
        self, 
        symbol: str, 
        df_1h: pd.DataFrame, 
        df_15m: pd.DataFrame,
        df_1d: Optional[pd.DataFrame] = None,  # 🆕 NEW: Macro trend
        df_4h: Optional[pd.DataFrame] = None,  # 🆕 NEW: Swing levels
        additional_context: Optional[Dict] = None
    ) -> Dict:
        """
        🆕 ENHANCED: Multi-timeframe teknik verilerden AI trading sinyali üret (v12.2)
        
        Args:
            symbol: Trading pair (örn: 'BTCUSDT')
            df_1h: 1 saatlik OHLCV + indicators DataFrame
            df_15m: 15 dakikalık OHLCV + indicators DataFrame
            df_1d: 🆕 1 günlük OHLCV + indicators DataFrame (macro trend için)
            df_4h: 🆕 4 saatlik OHLCV + indicators DataFrame (swing levels için)
            additional_context: Opsiyonel ek bilgiler (F&G Index, news sentiment vb.)
        
        Returns:
            {
                'direction': 'LONG' | 'SHORT' | 'HOLD',
                'confidence': 0-100,
                'entry_price': float,
                'stop_loss': float,
                'take_profit': float,
                'reasoning': str,
                'ai_source': 'deepseek' | 'gemini' | 'consensus',
                'risk_reward_ratio': float
            }
        """
        if not self.deepseek_client:
            logger.error("❌ DeepSeek client yok - AI sinyal üretilemedi")
            return self._get_hold_signal(symbol, "AI client unavailable")
        
        try:
            # 1. 🆕 ENHANCED: Teknik veriyi hazırla (1D + 4H eklendi)
            technical_data = self._prepare_technical_data(symbol, df_1h, df_15m, df_1d, df_4h, additional_context)
            
            # 2. Primary: DeepSeek analizi
            logger.info(f"🤖 {symbol}: PRIMARY → DeepSeek analizi başlatılıyor...")
            deepseek_signal = None
            deepseek_connection_error = False
            
            try:
                deepseek_signal = self._analyze_with_deepseek(technical_data)
            except Exception as e:
                deepseek_connection_error = True
                error_msg = str(e)
                if "Connection" in error_msg or "nodename" in error_msg or "DNS" in error_msg:
                    logger.warning(f"⚠️ {symbol}: DeepSeek bağlantı hatası → Gemini FALLBACK devreye giriyor")
                else:
                    logger.warning(f"⚠️ {symbol}: DeepSeek hatası: {error_msg[:100]}")
            
            if deepseek_signal is None and deepseek_connection_error:
                # Bağlantı hatası - direkt Gemini'ye geç
                logger.info(f"🔄 {symbol}: FALLBACK → Gemini analizi başlatılıyor...")
                if self.gemini_enabled and self.gemini_client:
                    try:
                        gemini_signal = self._analyze_with_gemini(technical_data)
                        if gemini_signal and gemini_signal['confidence'] >= self.min_confidence:
                            gemini_signal['ai_source'] = 'gemini_connection_fallback'
                            self.gemini_daily_calls += 1
                            logger.info(f"✅ {symbol}: Gemini FALLBACK başarılı (confidence: {gemini_signal['confidence']})")
                            return gemini_signal
                        elif gemini_signal:
                            logger.warning(f"⚠️ {symbol}: Gemini confidence düşük ({gemini_signal.get('confidence', 0)})")
                    except Exception as e:
                        logger.error(f"❌ {symbol}: Gemini FALLBACK de başarısız: {str(e)[:100]}")
                
                return self._get_hold_signal(symbol, "Both AI services failed (connection error)")
            
            elif deepseek_signal is None:
                # DeepSeek analiz yapamadı (bağlantı dışı sebep)
                return self._get_hold_signal(symbol, "DeepSeek analysis failed")
            
            logger.info(f"   ✅ DeepSeek: {deepseek_signal['direction']} (confidence: {deepseek_signal['confidence']})")
            
            # 3. Confidence yeterli mi?
            if deepseek_signal['confidence'] >= self.min_confidence:
                logger.info(f"✅ {symbol}: DeepSeek PRIMARY sinyal KABUL (confidence: {deepseek_signal['confidence']} >= {self.min_confidence})")
                deepseek_signal['ai_source'] = 'deepseek'
                return deepseek_signal
            
            # 4. Confidence düşük - Gemini fallback gerekli mi?
            if (deepseek_signal['confidence'] < self.fallback_threshold and 
                self.gemini_enabled and 
                self.gemini_client and
                self.gemini_daily_calls < self.max_daily_gemini_calls):
                
                logger.info(f"⚠️ {symbol}: DeepSeek confidence DÜŞÜK ({deepseek_signal['confidence']} < {self.fallback_threshold}) → Gemini QUALITY CHECK")
                
                # Gemini'ye sor (quality check için)
                try:
                    gemini_signal = self._analyze_with_gemini(technical_data)
                    self.gemini_daily_calls += 1
                    
                    if gemini_signal is None:
                        logger.warning(f"⚠️ {symbol}: Gemini analizi başarısız → DeepSeek sinyali kullanılıyor")
                        deepseek_signal['ai_source'] = 'deepseek_only'
                        return deepseek_signal
                    
                    logger.info(f"   ✅ Gemini: {gemini_signal['direction']} (confidence: {gemini_signal['confidence']})")
                    
                    # 5. Consensus check
                    return self._consensus_signal(deepseek_signal, gemini_signal, symbol)
                    
                except Exception as e:
                    logger.warning(f"⚠️ {symbol}: Gemini hatası, DeepSeek kullanılıyor: {str(e)[:100]}")
                    deepseek_signal['ai_source'] = 'deepseek_only'
                    return deepseek_signal
            
            # 6. Gemini fallback yok ama confidence threshold altında
            if deepseek_signal['confidence'] < self.min_confidence:
                logger.warning(f"⚠️ {symbol}: Confidence threshold altında ({deepseek_signal['confidence']} < {self.min_confidence}) → HOLD")
                return self._get_hold_signal(symbol, f"Low confidence ({deepseek_signal['confidence']})")
            
            # 7. Default: DeepSeek sinyali
            deepseek_signal['ai_source'] = 'deepseek'
            return deepseek_signal
            
        except Exception as e:
            logger.error(f"❌ {symbol}: AI sinyal üretimi hatası - {e}", exc_info=True)
            return self._get_hold_signal(symbol, f"Error: {str(e)}")
    
    # ═══════════════════════════════════════════════════════════════
    # 🆕 HELPER FUNCTIONS FOR ENHANCED DATA
    # ═══════════════════════════════════════════════════════════════
    
    def _calculate_support_resistance(self, df: pd.DataFrame, current_price: float) -> Dict:
        """Son 50 mumdan destek ve direnç seviyelerini hesapla"""
        try:
            lookback = min(50, len(df))
            recent_data = df.iloc[-lookback:]
            
            # Swing lows (support) ve swing highs (resistance) bul
            highs = []
            lows = []
            
            for i in range(2, len(recent_data) - 2):
                # Swing high: orta > sol 2 ve sağ 2
                if (recent_data.iloc[i]['high'] > recent_data.iloc[i-1]['high'] and
                    recent_data.iloc[i]['high'] > recent_data.iloc[i-2]['high'] and
                    recent_data.iloc[i]['high'] > recent_data.iloc[i+1]['high'] and
                    recent_data.iloc[i]['high'] > recent_data.iloc[i+2]['high']):
                    highs.append(float(recent_data.iloc[i]['high']))
                
                # Swing low: orta < sol 2 ve sağ 2  
                if (recent_data.iloc[i]['low'] < recent_data.iloc[i-1]['low'] and
                    recent_data.iloc[i]['low'] < recent_data.iloc[i-2]['low'] and
                    recent_data.iloc[i]['low'] < recent_data.iloc[i+1]['low'] and
                    recent_data.iloc[i]['low'] < recent_data.iloc[i+2]['low']):
                    lows.append(float(recent_data.iloc[i]['low']))
            
            # En yakın 3 seviyeyi al
            supports = sorted([l for l in lows if l < current_price], reverse=True)[:3]
            resistances = sorted([h for h in highs if h > current_price])[:3]
            
            # Eğer yeterli seviye yoksa min/max kullan
            if not supports:
                supports = [float(recent_data['low'].min())]
            if not resistances:
                resistances = [float(recent_data['high'].max())]
            
            # Fiyatın S/R arası konumu (%)
            nearest_support = supports[0] if supports else current_price * 0.95
            nearest_resistance = resistances[0] if resistances else current_price * 1.05
            
            if nearest_resistance > nearest_support:
                position_pct = ((current_price - nearest_support) / (nearest_resistance - nearest_support)) * 100
            else:
                position_pct = 50.0
            
            return {
                'supports': supports,
                'resistances': resistances,
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance,
                'position_in_range_pct': round(position_pct, 1),
                'distance_to_support_pct': round(((current_price - nearest_support) / current_price) * 100, 2),
                'distance_to_resistance_pct': round(((nearest_resistance - current_price) / current_price) * 100, 2),
            }
        except Exception as e:
            logger.error(f"S/R hesaplama hatası: {e}")
            return {}
    
    def _calculate_volume_analysis(self, df_1h: pd.DataFrame, df_15m: pd.DataFrame) -> Dict:
        """🆕 ENHANCED: Gelişmiş hacim analizi (spike, divergence, CVD)"""
        try:
            # Volume SMA(20)
            vol_sma_1h = df_1h['volume'].rolling(20).mean().iloc[-1]
            vol_sma_15m = df_15m['volume'].rolling(20).mean().iloc[-1]
            
            current_vol_1h = df_1h.iloc[-1]['volume']
            current_vol_15m = df_15m.iloc[-1]['volume']
            
            # Volume ratio
            vol_ratio_1h = (current_vol_1h / vol_sma_1h) if vol_sma_1h > 0 else 1.0
            vol_ratio_15m = (current_vol_15m / vol_sma_15m) if vol_sma_15m > 0 else 1.0
            
            # 🆕 SPIKE DETECTION (son 4 mumda 2x artış var mı?)
            recent_vols_1h = df_1h['volume'].iloc[-4:].tolist()
            avg_recent_1h = sum(recent_vols_1h[:-1]) / 3  # Son 3 mumun ortalaması
            spike_detected = current_vol_1h > avg_recent_1h * 2.0
            
            # 🆕 VOLUME TREND (son 5 mum hacim artıyor/azalıyor mu?)
            vol_trend_1h = df_1h['volume'].iloc[-5:]
            vol_increasing = vol_trend_1h.iloc[-1] > vol_trend_1h.iloc[0]
            
            # 🆕 VOLUME DIVERGENCE (fiyat yükselirken hacim düşüyor mu? - bearish)
            price_trend_1h = df_1h['close'].iloc[-5:]
            price_increasing = price_trend_1h.iloc[-1] > price_trend_1h.iloc[0]
            
            divergence = None
            if price_increasing and not vol_increasing:
                divergence = "BEARISH_DIVERGENCE"  # Fiyat yükseliyor, hacim düşüyor → zayıf
            elif not price_increasing and vol_increasing:
                divergence = "BULLISH_DIVERGENCE"  # Fiyat düşüyor, hacim artıyor → güçlü satış (reversal fırsatı)
            
            # 🆕 CUMULATIVE VOLUME DELTA (CVD) - Alıcı/Satıcı Gücü
            # Yeşil mumlar = alıcı, kırmızı mumlar = satıcı
            last_10_1h = df_1h.iloc[-10:]
            buyer_volume = sum(
                row['volume'] for _, row in last_10_1h.iterrows() 
                if row['close'] > row['open']
            )
            seller_volume = sum(
                row['volume'] for _, row in last_10_1h.iterrows() 
                if row['close'] <= row['open']
            )
            
            total_volume = buyer_volume + seller_volume
            cvd_ratio = (buyer_volume / total_volume) if total_volume > 0 else 0.5
            
            if cvd_ratio > 0.65:
                cvd_interpretation = "BUYER_DOMINANT (Alıcılar güçlü)"
            elif cvd_ratio < 0.35:
                cvd_interpretation = "SELLER_DOMINANT (Satıcılar güçlü)"
            else:
                cvd_interpretation = "BALANCED (Dengeli)"
            
            return {
                'vol_sma_1h': float(vol_sma_1h),
                'vol_ratio_1h': round(vol_ratio_1h, 2),
                'vol_spike_1h': spike_detected,
                'vol_sma_15m': float(vol_sma_15m),
                'vol_ratio_15m': round(vol_ratio_15m, 2),
                'vol_spike_15m': vol_ratio_15m > 1.5,
                # 🆕 Advanced metrics
                'volume_trend': 'INCREASING' if vol_increasing else 'DECREASING',
                'divergence': divergence,
                'cvd_ratio': round(cvd_ratio, 3),
                'cvd_interpretation': cvd_interpretation,
                'buyer_volume_pct': round(cvd_ratio * 100, 1),
                'seller_volume_pct': round((1 - cvd_ratio) * 100, 1),
                'interpretation': self._interpret_volume_advanced(vol_ratio_1h, vol_ratio_15m, spike_detected, divergence, cvd_ratio)
            }
        except Exception as e:
            logger.error(f"Volume analizi hatası: {e}")
            return {}
    
    def _interpret_volume_advanced(self, ratio_1h: float, ratio_15m: float, spike: bool, divergence: str, cvd: float) -> str:
        """🆕 Gelişmiş hacim yorumu"""
        parts = []
        
        if spike:
            parts.append("🔥 GÜÇLÜ HACIM SPIKE")
        elif ratio_15m > 1.5:
            parts.append("Güçlü hacim artışı")
        elif ratio_15m > 1.2:
            parts.append("Orta hacim artışı")
        elif ratio_15m < 0.5:
            parts.append("⚠️ Düşük hacim - zayıf hareket")
        else:
            parts.append("Normal hacim")
        
        if divergence == "BEARISH_DIVERGENCE":
            parts.append("| ⚠️ Bearish divergence (fiyat↑ hacim↓)")
        elif divergence == "BULLISH_DIVERGENCE":
            parts.append("| ✅ Bullish divergence (fiyat↓ hacim↑)")
        
        if cvd > 0.65:
            parts.append("| 💪 Alıcılar dominant")
        elif cvd < 0.35:
            parts.append("| 🔻 Satıcılar dominant")
        
        return " ".join(parts)
    
    def _analyze_price_patterns(self, df_1h: pd.DataFrame, df_15m: pd.DataFrame) -> Dict:
        """Price action patterns analizi"""
        try:
            # Son 3 mum 1H
            last_3_1h = df_1h.iloc[-3:]
            bullish_count_1h = sum(1 for _, c in last_3_1h.iterrows() if c['close'] > c['open'])
            bearish_count_1h = 3 - bullish_count_1h
            
            # Son 3 mum 15M
            last_3_15m = df_15m.iloc[-3:]
            bullish_count_15m = sum(1 for _, c in last_3_15m.iterrows() if c['close'] > c['open'])
            bearish_count_15m = 3 - bullish_count_15m
            
            # Pattern tespiti
            pattern_1h = "neutral"
            if bullish_count_1h == 3:
                pattern_1h = "3_bullish_candles"
            elif bearish_count_1h == 3:
                pattern_1h = "3_bearish_candles"
            elif bullish_count_1h == 2:
                pattern_1h = "bullish_momentum"
            elif bearish_count_1h == 2:
                pattern_1h = "bearish_momentum"
            
            pattern_15m = "neutral"
            if bullish_count_15m == 3:
                pattern_15m = "3_bullish_candles"
            elif bearish_count_15m == 3:
                pattern_15m = "3_bearish_candles"
            
            # Doji detection (son mum)
            last_1h = df_1h.iloc[-1]
            body_1h = abs(last_1h['close'] - last_1h['open'])
            range_1h = last_1h['high'] - last_1h['low']
            is_doji_1h = (body_1h / range_1h < 0.1) if range_1h > 0 else False
            
            return {
                'pattern_1h': pattern_1h,
                'pattern_15m': pattern_15m,
                'bullish_count_1h': bullish_count_1h,
                'bearish_count_1h': bearish_count_1h,
                'is_doji_1h': is_doji_1h,
                'interpretation': self._interpret_pattern(pattern_1h, pattern_15m)
            }
        except Exception as e:
            logger.error(f"Price pattern analizi hatası: {e}")
            return {}
    
    def _interpret_pattern(self, pattern_1h: str, pattern_15m: str) -> str:
        """Pattern yorumla"""
        if "3_bullish" in pattern_1h:
            return "Güçlü yükseliş trendi - momentum pozitif"
        elif "3_bearish" in pattern_1h:
            return "Güçlü düşüş trendi - momentum negatif"
        elif "bullish_momentum" in pattern_1h:
            return "Yükseliş eğilimi - orta momentum"
        elif "bearish_momentum" in pattern_1h:
            return "Düşüş eğilimi - orta momentum"
        else:
            return "Kararsız fiyat hareketi"
    
    def _calculate_momentum_indicators(self, last_1h: pd.Series, last_15m: pd.Series) -> Dict:
        """Gelişmiş momentum göstergeleri"""
        try:
            return {
                'stoch_rsi_1h': {
                    'k': float(last_1h.get('stoch_rsi_k', 50)),
                    'd': float(last_1h.get('stoch_rsi_d', 50)),
                },
                'stoch_rsi_15m': {
                    'k': float(last_15m.get('stoch_rsi_k', 50)),
                    'd': float(last_15m.get('stoch_rsi_d', 50)),
                },
                'mfi_1h': float(last_1h.get('mfi', 50)),
                'roc_1h': float(last_1h.get('roc', 0)),
            }
        except Exception as e:
            logger.error(f"Momentum göstergeler hatası: {e}")
            return {}
    
    def _analyze_trend_strength(self, df: pd.DataFrame, last_row: pd.Series) -> Dict:
        """Trend gücü analizi"""
        try:
            adx = float(last_row.get('adx14', 0))
            
            # ADX yorumu
            if adx > 25:
                adx_strength = "strong_trend"
            elif adx > 20:
                adx_strength = "moderate_trend"
            else:
                adx_strength = "weak_trend"
            
            # EMA alignment (kaç EMA yukarı sıralı)
            ema5 = float(last_row.get('ema5', 0))
            ema20 = float(last_row.get('ema20', 0))
            ema50 = float(last_row.get('ema50', 0))
            sma200 = float(last_row.get('sma200', 0))
            
            bullish_alignment = 0
            if ema5 > ema20: bullish_alignment += 1
            if ema20 > ema50: bullish_alignment += 1
            if ema50 > sma200: bullish_alignment += 1
            
            alignment_score = bullish_alignment  # 0-3
            
            # SuperTrend
            supertrend_direction = last_row.get('supertrend_direction', 0)
            
            return {
                'adx': adx,
                'adx_strength': adx_strength,
                'ema_alignment_score': alignment_score,
                'supertrend_bullish': bool(supertrend_direction > 0) if supertrend_direction else None,
                'interpretation': f"ADX {adx:.1f} ({adx_strength}), EMA alignment {alignment_score}/3"
            }
        except Exception as e:
            logger.error(f"Trend strength analizi hatası: {e}")
            return {}
    
    def _get_btc_correlation(self) -> Dict:
        """BTC korelasyon verisi (eğer coin BTC değilse)"""
        try:
            from src.data_fetcher.binance_fetcher import get_binance_klines
            
            # BTC 1H data
            df_btc = get_binance_klines('BTCUSDT', '1h', limit=24)
            
            if df_btc is None or df_btc.empty:
                return {}
            
            btc_current = float(df_btc.iloc[-1]['close'])
            btc_24h_ago = float(df_btc.iloc[0]['close'])
            btc_change_24h = ((btc_current - btc_24h_ago) / btc_24h_ago) * 100
            
            # BTC trend (son 4 mum)
            last_4 = df_btc.iloc[-4:]
            bullish_btc = sum(1 for _, c in last_4.iterrows() if c['close'] > c['open'])
            btc_trend = "bullish" if bullish_btc >= 3 else ("bearish" if bullish_btc <= 1 else "neutral")
            
            # 🆕 ENHANCED MARKET REGIME CLASSIFICATION
            market_regime = self._classify_market_regime(df_btc, btc_change_24h)
            
            return {
                'btc_price': btc_current,
                'btc_change_24h': round(btc_change_24h, 2),
                'btc_trend': btc_trend,
                'market_regime': market_regime['regime'],
                'volatility': market_regime['volatility'],
                'regime_description': market_regime['description'],
                'trading_recommendation': market_regime['recommendation'],
                'warning': "BTC düşüşte - altcoin riski" if btc_change_24h < -3 else None
            }
        except Exception as e:
            logger.error(f"BTC korelasyon hatası: {e}")
            return {}
    
    def _classify_market_regime(self, df_btc: pd.DataFrame, change_24h: float) -> Dict:
        """🆕 Detaylı market regime sınıflandırması"""
        try:
            # ATR bazlı volatilite
            if 'atr14' in df_btc.columns:
                current_price = float(df_btc.iloc[-1]['close'])
                atr = float(df_btc.iloc[-1]['atr14'])
                volatility_pct = (atr / current_price) * 100
                
                if volatility_pct > 5.0:
                    volatility = "VERY_HIGH"
                elif volatility_pct > 3.0:
                    volatility = "HIGH"
                elif volatility_pct > 1.5:
                    volatility = "MEDIUM"
                else:
                    volatility = "LOW"
            else:
                volatility = "UNKNOWN"
            
            # Regime classification
            if change_24h > 5.0:
                regime = "STRONG_BULL"
                description = "Güçlü yükseliş - momentum çok yüksek"
                recommendation = "LONG bias, aggressive TP targets, tighter SL"
            elif change_24h > 2.0:
                regime = "WEAK_BULL"
                description = "Zayıf yükseliş - dikkatli iyimser"
                recommendation = "LONG bias, normal TP targets, standard SL"
            elif change_24h > -2.0:
                regime = "RANGE"
                description = "Yatay hareket - yön belirsiz"
                recommendation = "Mean reversion setups, tight TP/SL, very selective"
            elif change_24h > -5.0:
                regime = "WEAK_BEAR"
                description = "Zayıf düşüş - dikkatli kötümser"
                recommendation = "SHORT bias, quick TP targets, wider SL for volatility"
            else:
                regime = "STRONG_BEAR"
                description = "Güçlü düşüş - momentum çok düşük"
                recommendation = "SHORT bias, aggressive TP targets, avoid LONG"
            
            return {
                'regime': regime,
                'volatility': volatility,
                'description': description,
                'recommendation': recommendation
            }
        except Exception as e:
            logger.error(f"Market regime classification error: {e}")
            return {
                'regime': 'UNKNOWN',
                'volatility': 'UNKNOWN',
                'description': 'N/A',
                'recommendation': 'N/A'
            }
    
    def _calculate_fibonacci_levels(self, df: pd.DataFrame) -> Dict:
        """Fibonacci retracement ve extension seviyeleri"""
        try:
            lookback = min(50, len(df))
            recent_data = df.iloc[-lookback:]
            
            swing_high = float(recent_data['high'].max())
            swing_low = float(recent_data['low'].min())
            diff = swing_high - swing_low
            
            # Retracement levels (swing high'dan aşağı)
            fib_retracements = {
                '0.236': swing_high - (diff * 0.236),
                '0.382': swing_high - (diff * 0.382),
                '0.5': swing_high - (diff * 0.5),
                '0.618': swing_high - (diff * 0.618),
                '0.786': swing_high - (diff * 0.786),
            }
            
            # Extension levels (swing high'dan yukarı)
            fib_extensions = {
                '1.272': swing_high + (diff * 0.272),
                '1.618': swing_high + (diff * 0.618),
            }
            
            return {
                'swing_high': swing_high,
                'swing_low': swing_low,
                'retracements': fib_retracements,
                'extensions': fib_extensions
            }
        except Exception as e:
            logger.error(f"Fibonacci hesaplama hatası: {e}")
            return {}
    
    # ═══════════════════════════════════════════════════════════════
    
    def _prepare_technical_data(
        self, 
        symbol: str, 
        df_1h: pd.DataFrame, 
        df_15m: pd.DataFrame,
        df_1d: Optional[pd.DataFrame],  # 🆕 NEW
        df_4h: Optional[pd.DataFrame],  # 🆕 NEW
        additional_context: Optional[Dict]
    ) -> Dict:
        """🚀 ENHANCED: Teknik analiz verilerini AI için formatla (v12.2 - Multi-Timeframe)"""
        
        # Son mumlar
        last_1h = df_1h.iloc[-1]
        last_15m = df_15m.iloc[-1]
        prev_1h = df_1h.iloc[-2]
        prev_15m = df_15m.iloc[-2]
        
        current_price = float(last_1h['close'])
        
        # ═══════════════════════════════════════════════════════
        # 🆕 0. MACRO TREND ANALYSIS (1D + 4H)
        # ═══════════════════════════════════════════════════════
        macro_trend = {}
        swing_levels = {}
        
        if df_1d is not None and not df_1d.empty:
            last_1d = df_1d.iloc[-1]
            prev_1d = df_1d.iloc[-2]
            
            macro_trend = {
                'price': float(last_1d['close']),
                'ema20': float(last_1d.get('ema20', 0)),
                'ema50': float(last_1d.get('ema50', 0)),
                'sma200': float(last_1d.get('sma200', 0)),
                'rsi14': float(last_1d.get('rsi14', 50)),
                'adx14': float(last_1d.get('adx14', 0)),
                'trend_direction': 'BULLISH' if last_1d.get('ema20', 0) > last_1d.get('sma200', 0) else 'BEARISH',
                'price_change_pct': ((last_1d['close'] - prev_1d['close']) / prev_1d['close']) * 100,
                'trend_strength': 'STRONG' if last_1d.get('adx14', 0) > 25 else 'WEAK',
            }
        
        if df_4h is not None and not df_4h.empty:
            last_4h = df_4h.iloc[-1]
            prev_4h = df_4h.iloc[-2]
            
            # 4H swing high/low levels (son 20 mum)
            recent_4h = df_4h.iloc[-20:]
            swing_high = float(recent_4h['high'].max())
            swing_low = float(recent_4h['low'].min())
            
            swing_levels = {
                'price': float(last_4h['close']),
                'swing_high': swing_high,
                'swing_low': swing_low,
                'distance_to_high_pct': ((swing_high - current_price) / current_price) * 100,
                'distance_to_low_pct': ((current_price - swing_low) / current_price) * 100,
                'ema20': float(last_4h.get('ema20', 0)),
                'ema50': float(last_4h.get('ema50', 0)),
                'rsi14': float(last_4h.get('rsi14', 50)),
                'price_change_pct': ((last_4h['close'] - prev_4h['close']) / prev_4h['close']) * 100,
            }
        
        # ═══════════════════════════════════════════════════════
        # 🆕 1. SUPPORT/RESISTANCE LEVELS (Son 50 mum)
        # ═══════════════════════════════════════════════════════
        support_resistance = self._calculate_support_resistance(df_1h, current_price)
        
        # ═══════════════════════════════════════════════════════
        # 🆕 2. VOLUME ANALYSIS
        # ═══════════════════════════════════════════════════════
        volume_analysis = self._calculate_volume_analysis(df_1h, df_15m)
        
        # ═══════════════════════════════════════════════════════
        # 🆕 3. PRICE ACTION PATTERNS (Son 3 mum)
        # ═══════════════════════════════════════════════════════
        price_patterns = self._analyze_price_patterns(df_1h, df_15m)
        
        # ═══════════════════════════════════════════════════════
        # 🆕 4. ADVANCED MOMENTUM INDICATORS
        # ═══════════════════════════════════════════════════════
        momentum_indicators = self._calculate_momentum_indicators(last_1h, last_15m)
        
        # ═══════════════════════════════════════════════════════
        # 🆕 5. TREND STRENGTH ANALYSIS
        # ═══════════════════════════════════════════════════════
        trend_strength = self._analyze_trend_strength(df_1h, last_1h)
        
        # ═══════════════════════════════════════════════════════
        # 🆕 6. BTC CORRELATION (if not BTCUSDT)
        # ═══════════════════════════════════════════════════════
        btc_correlation = {}
        if symbol != 'BTCUSDT':
            btc_correlation = self._get_btc_correlation()
        
        # ═══════════════════════════════════════════════════════
        # 🆕 7. FIBONACCI LEVELS
        # ═══════════════════════════════════════════════════════
        fibonacci_levels = self._calculate_fibonacci_levels(df_1h)
        
        data = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            
            # 🆕 1D (Macro Trend) - EN ÜST SEVİYE
            '1d': macro_trend if macro_trend else None,
            
            # 🆕 4H (Swing Levels) - ORTA SEVİYE
            '4h': swing_levels if swing_levels else None,
            
            # 1H (Ana Trend)
            '1h': {
                'price': current_price,
                'volume': float(last_1h['volume']),
                'ema5': float(last_1h.get('ema5', 0)),
                'ema20': float(last_1h.get('ema20', 0)),
                'ema50': float(last_1h.get('ema50', 0)),
                'sma200': float(last_1h.get('sma200', 0)),
                'rsi14': float(last_1h.get('rsi14', 50)),
                'macd': float(last_1h.get('macd', 0)),
                'macd_signal': float(last_1h.get('macd_signal', 0)),
                'macd_hist': float(last_1h.get('macd_hist', 0)),
                'bb_upper': float(last_1h.get('bb_upper', 0)),
                'bb_middle': float(last_1h.get('bb_middle', 0)),
                'bb_lower': float(last_1h.get('bb_lower', 0)),
                'atr14': float(last_1h.get('atr14', 0)),
                'adx14': float(last_1h.get('adx14', 0)),
                'price_change_pct': ((last_1h['close'] - prev_1h['close']) / prev_1h['close']) * 100,
            },
            
            # 15M (Giriş Sinyali)
            '15m': {
                'price': float(last_15m['close']),
                'volume': float(last_15m['volume']),
                'ema5': float(last_15m.get('ema5', 0)),
                'ema20': float(last_15m.get('ema20', 0)),
                'ema50': float(last_15m.get('ema50', 0)),
                'sma200': float(last_15m.get('sma200', 0)),
                'rsi14': float(last_15m.get('rsi14', 50)),
                'macd': float(last_15m.get('macd', 0)),
                'macd_signal': float(last_15m.get('macd_signal', 0)),
                'macd_hist': float(last_15m.get('macd_hist', 0)),
                'bb_upper': float(last_15m.get('bb_upper', 0)),
                'bb_middle': float(last_15m.get('bb_middle', 0)),
                'bb_lower': float(last_15m.get('bb_lower', 0)),
                'atr14': float(last_15m.get('atr14', 0)),
                'price_change_pct': ((last_15m['close'] - prev_15m['close']) / prev_15m['close']) * 100,
            },
            
            # 🆕 ENHANCED CONTEXT
            'context': {
                **(additional_context or {}),
                'support_resistance': support_resistance,
                'volume_analysis': volume_analysis,
                'price_patterns': price_patterns,
                'momentum_indicators': momentum_indicators,
                'trend_strength': trend_strength,
                'btc_correlation': btc_correlation,
                'fibonacci_levels': fibonacci_levels,
            }
        }
        
        return data
    
    # ═══════════════════════════════════════════════════════════════
    # 🆕 PROMPT BUILDER HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def _build_support_resistance_section(self, sr: Dict) -> str:
        """S/R section"""
        if not sr:
            return ""
        
        supports_str = ", ".join([f"${s:.2f}" for s in sr.get('supports', [])[:3]])
        resistances_str = ", ".join([f"${r:.2f}" for r in sr.get('resistances', [])[:3]])
        
        return f"""
📍 DESTEK/DİRENÇ SEVİYELERİ (Son 50 Mum):
-----------------------------------
- Destek Seviyeleri: {supports_str}
- Direnç Seviyeleri: {resistances_str}
- En Yakın Destek: ${sr.get('nearest_support', 0):.2f} ({sr.get('distance_to_support_pct', 0):.2f}% uzakta)
- En Yakın Direnç: ${sr.get('nearest_resistance', 0):.2f} ({sr.get('distance_to_resistance_pct', 0):.2f}% uzakta)
- Fiyat Konumu: S/R arası %{sr.get('position_in_range_pct', 50):.1f}
"""
    
    def _build_volume_section(self, vol: Dict) -> str:
        """Volume section"""
        if not vol:
            return ""
        
        return f"""
📊 HACİM ANALİZİ:
-----------------------------------
- 1H Hacim / SMA(20): {vol.get('vol_ratio_1h', 1):.2f}x {('🔥 SPIKE!' if vol.get('vol_spike_1h') else '')}
- 15M Hacim / SMA(20): {vol.get('vol_ratio_15m', 1):.2f}x {('🔥 SPIKE!' if vol.get('vol_spike_15m') else '')}
- Yorum: {vol.get('interpretation', 'N/A')}
"""
    
    def _build_price_action_section(self, patterns: Dict) -> str:
        """Price action section"""
        if not patterns:
            return ""
        
        return f"""
🕯️ FİYAT AKSİYONU (Son 3 Mum):
-----------------------------------
- 1H Pattern: {patterns.get('pattern_1h', 'neutral')} ({patterns.get('bullish_count_1h', 0)} bullish)
- 15M Pattern: {patterns.get('pattern_15m', 'neutral')} ({patterns.get('bullish_count_15m', 0)} bullish)
- Son Mum Doji?: {'✅ Evet' if patterns.get('is_doji_1h') else '❌ Hayır'}
- Yorum: {patterns.get('interpretation', 'N/A')}
"""
    
    def _build_momentum_section(self, momentum: Dict) -> str:
        """Momentum section"""
        if not momentum:
            return ""
        
        stoch_1h = momentum.get('stoch_rsi_1h', {})
        
        return f"""
⚡ GELİŞMİŞ MOMENTUM:
-----------------------------------
- Stochastic RSI (1H): K={stoch_1h.get('k', 50):.1f}, D={stoch_1h.get('d', 50):.1f}
- MFI (Money Flow): {momentum.get('mfi_1h', 50):.1f}
- ROC (Rate of Change): {momentum.get('roc_1h', 0):.2f}
"""
    
    def _build_trend_strength_section(self, trend: Dict) -> str:
        """Trend strength section"""
        if not trend:
            return ""
        
        return f"""
📈 TREND GÜCÜ ANALİZİ:
-----------------------------------
- ADX: {trend.get('adx', 0):.1f} ({trend.get('adx_strength', 'unknown')})
- EMA Alignment Score: {trend.get('ema_alignment_score', 0)}/3
- SuperTrend: {'📗 Bullish' if trend.get('supertrend_bullish') else '📕 Bearish' if trend.get('supertrend_bullish') == False else 'N/A'}
- Yorum: {trend.get('interpretation', 'N/A')}
"""
    
    def _build_1d_section(self, data_1d: Dict) -> str:
        """🆕 NEW: 1D macro trend section"""
        if not data_1d:
            return ""
        
        return f"""
🌍 MACRO TREND (1D - ÜST SEVİYE):
═══════════════════════════════════
- Fiyat: ${data_1d.get('price', 0):,.4f}
- Trend: {data_1d.get('trend_direction', 'N/A')} ({data_1d.get('trend_strength', 'N/A')})
- EMA20: ${data_1d.get('ema20', 0):,.4f}
- EMA50: ${data_1d.get('ema50', 0):,.4f}
- SMA200: ${data_1d.get('sma200', 0):,.4f}
- RSI14: {data_1d.get('rsi14', 50):.1f}
- ADX14: {data_1d.get('adx14', 0):.1f}
- 1D Değişim: {data_1d.get('price_change_pct', 0):+.2f}%

💡 YORUM: 1D trend {data_1d.get('trend_direction', 'belirsiz')} - Bu üst seviye trend LONG/SHORT kararını etkiler.
"""
    
    def _build_4h_section(self, data_4h: Dict) -> str:
        """🆕 NEW: 4H swing levels section"""
        if not data_4h:
            return ""
        
        return f"""
📊 SWING LEVELS (4H - ORTA SEVİYE):
═══════════════════════════════════
- Fiyat: ${data_4h.get('price', 0):,.4f}
- Swing High: ${data_4h.get('swing_high', 0):,.4f} (+{data_4h.get('distance_to_high_pct', 0):.2f}% mesafe)
- Swing Low: ${data_4h.get('swing_low', 0):,.4f} (-{data_4h.get('distance_to_low_pct', 0):.2f}% mesafe)
- EMA20: ${data_4h.get('ema20', 0):,.4f}
- EMA50: ${data_4h.get('ema50', 0):,.4f}
- RSI14: {data_4h.get('rsi14', 50):.1f}
- 4H Değişim: {data_4h.get('price_change_pct', 0):+.2f}%

💡 YORUM: 4H swing levels TP/SL kararını optimize etmek için kullan.
"""
    
    def _build_btc_section(self, btc: Dict) -> str:
        """🆕 ENHANCED: BTC correlation + market regime section"""
        if not btc:
            return ""
        
        warning = f"\n⚠️ {btc.get('warning')}" if btc.get('warning') else ""
        
        regime_info = ""
        if btc.get('market_regime'):
            regime_info = f"""
- 🎯 MARKET REGIME: {btc.get('market_regime')} ({btc.get('volatility')} volatility)
- 📋 Açıklama: {btc.get('regime_description', 'N/A')}
- 💡 Öneri: {btc.get('trading_recommendation', 'N/A')}"""
        
        return f"""
₿ BTC KORELASYONU + MARKET REGIME:
-----------------------------------
- BTC Fiyat: ${btc.get('btc_price', 0):,.2f}
- BTC 24H Değişim: {btc.get('btc_change_24h', 0):+.2f}%
- BTC Trend: {btc.get('btc_trend', 'unknown')}{regime_info}{warning}
"""
    
    def _build_fibonacci_section(self, fib: Dict) -> str:
        """Fibonacci section"""
        if not fib or not fib.get('retracements'):
            return ""
        
        retracements = fib.get('retracements', {})
        
        return f"""
📐 FIBONACCI SEVİYELERİ (Son 50 Mum):
-----------------------------------
- Swing High: ${fib.get('swing_high', 0):.2f}
- Swing Low: ${fib.get('swing_low', 0):.2f}
- Fib 0.618 (Altın Oran): ${retracements.get('0.618', 0):.2f}
- Fib 0.5: ${retracements.get('0.5', 0):.2f}
- Fib 0.382: ${retracements.get('0.382', 0):.2f}
"""
    
    # ═══════════════════════════════════════════════════════════════
    
    def _build_trading_prompt(self, technical_data: Dict) -> str:
        """🆕 ENHANCED: Profesyonel trading prompt oluştur (v12.2 - Multi-Timeframe)"""
        
        symbol = technical_data['symbol']
        data_1d = technical_data.get('1d')  # 🆕 NEW
        data_4h = technical_data.get('4h')  # 🆕 NEW
        data_1h = technical_data['1h']
        data_15m = technical_data['15m']
        context = technical_data['context']
        
        # Fear & Greed Index
        fg_text = ""
        if 'fear_greed_index' in context:
            fg_value = context['fear_greed_index']
            fg_text = f"\n- Fear & Greed Index: {fg_value}/100"
        
        # 🆕 Build 1D and 4H sections (if available)
        macro_section = self._build_1d_section(data_1d) if data_1d else ""
        swing_section = self._build_4h_section(data_4h) if data_4h else ""
        
        prompt = f"""Sen 10 yıllık deneyimli bir cryptocurrency futures trader'ısın. 
Binance Futures'ta kaldıraçlı işlemler yapıyorsun ve risk yönetimi konusunda uzmansın.

GÖREV: Aşağıdaki multi-timeframe teknik analiz verilerine göre {symbol} için bir trading kararı ver.

⚠️ ÖNEMLİ: Verileri HİYERARŞİK olarak değerlendir:
1. 1D (MACRO TREND) → Genel yön için
2. 4H (SWING LEVELS) → TP/SL seviyeleri için
3. 1H (ANA TREND) → Trend teyidi için
4. 15M (GİRİŞ SİNYALİ) → Giriş zamanlaması için

═══════════════════════════════════════════════════════════════
📊 MULTI-TIMEFRAME TEKNİK ANALİZ VERİLERİ
═══════════════════════════════════════════════════════════════

{macro_section}
{swing_section}

🕐 1 SAATLİK ZAMAN DİLİMİ (ANA TREND):
-----------------------------------
- Mevcut Fiyat: ${data_1h['price']:.6f}
- EMA 5: ${data_1h['ema5']:.6f}
- EMA 20: ${data_1h['ema20']:.6f}
- EMA 50: ${data_1h['ema50']:.6f}
- SMA 200: ${data_1h['sma200']:.6f}
- RSI(14): {data_1h['rsi14']:.2f}
- MACD: {data_1h['macd']:.4f}
- MACD Signal: {data_1h['macd_signal']:.4f}
- MACD Histogram: {data_1h['macd_hist']:.4f}
- Bollinger Üst: ${data_1h['bb_upper']:.6f}
- Bollinger Orta: ${data_1h['bb_middle']:.6f}
- Bollinger Alt: ${data_1h['bb_lower']:.6f}
- ATR(14): {data_1h['atr14']:.6f}
- ADX(14): {data_1h['adx14']:.2f}
- Son 1H Değişim: {data_1h['price_change_pct']:.2f}%
- Hacim: {data_1h['volume']:.0f}

🕐 15 DAKİKALIK ZAMAN DİLİMİ (GİRİŞ SİNYALİ):
-----------------------------------
- Mevcut Fiyat: ${data_15m['price']:.6f}
- EMA 5: ${data_15m['ema5']:.6f}
- EMA 20: ${data_15m['ema20']:.6f}
- EMA 50: ${data_15m['ema50']:.6f}
- SMA 200: ${data_15m['sma200']:.6f}
- RSI(14): {data_15m['rsi14']:.2f}
- MACD: {data_15m['macd']:.4f}
- MACD Signal: {data_15m['macd_signal']:.4f}
- MACD Histogram: {data_15m['macd_hist']:.4f}
- Bollinger Üst: ${data_15m['bb_upper']:.6f}
- Bollinger Orta: ${data_15m['bb_middle']:.6f}
- Bollinger Alt: ${data_15m['bb_lower']:.6f}
- ATR(14): {data_15m['atr14']:.6f}
- Son 15M Değişim: {data_15m['price_change_pct']:.2f}%
- Hacim: {data_15m['volume']:.0f}

🌍 PİYASA KOŞULLARI:
-----------------------------------{fg_text}
- Timestamp: {technical_data['timestamp']}

{self._build_support_resistance_section(context.get('support_resistance', {}))}
{self._build_volume_section(context.get('volume_analysis', {}))}
{self._build_price_action_section(context.get('price_patterns', {}))}
{self._build_momentum_section(context.get('momentum_indicators', {}))}
{self._build_trend_strength_section(context.get('trend_strength', {}))}
{self._build_btc_section(context.get('btc_correlation', {}))}
{self._build_fibonacci_section(context.get('fibonacci_levels', {}))}

═══════════════════════════════════════════════════════════════
📋 KARAR VER
═══════════════════════════════════════════════════════════════

Aşağıdaki kriterlere göre analiz yap:

1️⃣ TREND ANALİZİ:
   - 1H trend yönü nedir? (EMA 5/20/50/200 hizalaması)
   - 15M trend 1H ile uyumlu mu?
   - Golden Cross / Death Cross var mı?

2️⃣ MOMENTUM:
   - RSI overbought/oversold mu? (1H ve 15M)
   - MACD histogram büyüyor/küçülüyor mu?
   - Momentum yönü nedir?

3️⃣ VOLATILITE:
   - Bollinger Bands genişlemesi/daralması
   - ATR seviyesi (volatilite)
   - ADX trend gücü (>25 güçlü trend)

4️⃣ ENTRY TİMİNG:
   - 15M'de giriş fırsatı var mı?
   - Volume confirmation yeterli mi?
   - Pullback/retest oluştu mu?

5️⃣ RISK YÖNETİMİ:
   - Stop Loss nerede olmalı? (ATR bazlı veya swing low/high)
   - Take Profit hedefi nedir? (risk/reward en az 1.5:1 olmalı)
   - Position sizing için confidence level'ın ne?

🆕 6️⃣ DESTEK/DİRENÇ POZİSYONU:
   - Fiyat destek/direnç seviyelerine yakın mı?
   - S/R kırılımı bekleniyor mu?
   - Fibonacci seviyeleri ile uyumlu mu?

🆕 7️⃣ HACİM VE FİYAT AKSİYONU:
   - Hacim confirmation var mı? (spike)
   - Son 3 mumun pattern'i trend ile uyumlu mu?
   - Doji/indecision var mı?

🆕 8️⃣ BTC KORELASYONU (Altcoinler için):
   - BTC trend yönü ne?
   - BTC düşüşte ise altcoin riski var
   - BTC yükselişte ise altcoin fırsatı

═══════════════════════════════════════════════════════════════
✅ GELİŞMİŞ CEVAP FORMATI (JSON)
═══════════════════════════════════════════════════════════════

{{
    "direction": "LONG" veya "SHORT" veya "HOLD",
    "confidence": 0-100 arası sayı (100 = çok emin, 0 = hiç emin değil),
    "entry_price": giriş fiyatı (current price kullanabilirsin),
    "stop_loss": stop loss fiyatı,
    "take_profit": take profit fiyatı,
    "risk_reward_ratio": RR oranı (örn: 2.5 = 1:2.5),
    "reasoning": "Kararının detaylı açıklaması (Türkçe, 2-3 cümle)",
    
    "quality_scores": {{
        "trend_strength": 0-10 arası (ADX, EMA alignment),
        "volume_confirmation": 0-10 arası (hacim spike, ratio),
        "momentum_quality": 0-10 arası (RSI, MACD, Stoch),
        "support_resistance_position": 0-10 arası (S/R'a uzaklık)
    }},
    
    "warnings": [
        "Liste halinde riskler (örn: 'RSI overbought', 'BTC düşüşte', 'Düşük hacim')"
    ],
    
    "strengths": [
        "Liste halinde güçlü yönler (örn: 'Güçlü volume spike', 'EMA alignment 3/3', 'Destek seviyesinden rebound')"
    ],
    
    "key_levels": {{
        "next_support": nearest support fiyatı,
        "next_resistance": nearest resistance fiyatı,
        "invalidation_level": sinyalin geçersiz olacağı seviye
    }}
}}

ÖNEMLİ KURALLAR:
- SADECE JSON formatında cevap ver, başka metin yazma
- LONG için: stop_loss < entry_price < take_profit
- SHORT için: take_profit < entry_price < stop_loss
- Risk/Reward oranı minimum 1.5 olmalı
- Confidence < 60 ise direction = "HOLD" olmalı
- Çelişkili sinyaller varsa (1H yükseliş, 15M düşüş) → HOLD veya düşük confidence ver
- quality_scores toplamı yüksekse (>30/40) confidence yüksek olmalı
- warnings listesi uzunsa (<3 risk) confidence düşük tutulmalı
"""
        
        return prompt
    
    def _analyze_with_deepseek(self, technical_data: Dict) -> Optional[Dict]:
        """DeepSeek ile analiz yap"""
        
        try:
            prompt = self._build_trading_prompt(technical_data)
            
            response = self.deepseek_client.chat.completions.create(
                model=self.deepseek_model,
                messages=[
                    {"role": "system", "content": "Sen profesyonel bir cryptocurrency futures trader'ısın. Teknik analiz verilerine göre LONG/SHORT/HOLD kararı veriyorsun. Cevaplarını sadece JSON formatında veriyorsun."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Düşük = daha deterministik
                max_tokens=500
            )
            
            # Response'u parse et
            content = response.choices[0].message.content.strip()
            
            # JSON extract (bazen markdown code block içinde gelir)
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            signal = json.loads(content)
            
            # Validation
            if not self._validate_ai_signal(signal, technical_data):
                logger.error(f"❌ DeepSeek sinyali validation'dan geçemedi: {signal}")
                return None
            
            return signal
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ DeepSeek JSON parse hatası: {e}\nResponse: {content}")
            return None
        except Exception as e:
            logger.warning(f"⚠️ DeepSeek analiz hatası: {e}")
            # Bağlantı hatası ise direkt None dön, fallback'e geç
            return None
    
    def _analyze_with_gemini(self, technical_data: Dict) -> Optional[Dict]:
        """Gemini ile analiz yap (fallback)"""
        
        if not self.gemini_client:
            return None
        
        try:
            prompt = self._build_trading_prompt(technical_data)
            
            model = self.gemini_client.GenerativeModel(self.gemini_model)
            response = model.generate_content(prompt)
            
            content = response.text.strip()
            
            # JSON extract
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            signal = json.loads(content)
            
            # Validation
            if not self._validate_ai_signal(signal, technical_data):
                logger.error(f"❌ Gemini sinyali validation'dan geçemedi: {signal}")
                return None
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Gemini analiz hatası: {e}", exc_info=True)
            return None
    
    def _validate_ai_signal(self, signal: Dict, technical_data: Dict) -> bool:
        """AI sinyalini validate et"""
        
        required_fields = ['direction', 'confidence', 'entry_price', 'stop_loss', 'take_profit', 'reasoning']
        
        # 1. Required fields kontrolü
        if not all(field in signal for field in required_fields):
            logger.error(f"❌ Eksik field: {[f for f in required_fields if f not in signal]}")
            return False
        
        # 2. Direction kontrolü
        if signal['direction'] not in ['LONG', 'SHORT', 'HOLD']:
            logger.error(f"❌ Geçersiz direction: {signal['direction']}")
            return False
        
        # 3. Confidence range
        if not (0 <= signal['confidence'] <= 100):
            logger.error(f"❌ Geçersiz confidence: {signal['confidence']}")
            return False
        
        # HOLD için detaylı kontrol gereksiz
        if signal['direction'] == 'HOLD':
            return True
        
        # 4. Price validations
        entry = signal['entry_price']
        sl = signal['stop_loss']
        tp = signal['take_profit']
        current_price = technical_data['15m']['price']
        
        # Entry price reasonable mı? (current price ±5% içinde olmalı)
        if abs(entry - current_price) / current_price > 0.05:
            logger.error(f"❌ Entry price çok uzak: entry={entry}, current={current_price}")
            return False
        
        # 5. LONG logic kontrolü
        if signal['direction'] == 'LONG':
            if not (sl < entry < tp):
                logger.error(f"❌ LONG logic hatası: SL({sl}) < Entry({entry}) < TP({tp}) olmalı")
                return False
        
        # 6. SHORT logic kontrolü
        if signal['direction'] == 'SHORT':
            if not (tp < entry < sl):
                logger.error(f"❌ SHORT logic hatası: TP({tp}) < Entry({entry}) < SL({sl}) olmalı")
                return False
        
        # 7. Risk/Reward kontrolü
        rr = signal.get('risk_reward_ratio', 0)
        if rr < 1.0:
            logger.warning(f"⚠️ Düşük R:R oranı: {rr}")
        
        return True
    
    def _consensus_signal(self, deepseek_signal: Dict, gemini_signal: Dict, symbol: str) -> Dict:
        """İki AI sinyalini karşılaştır ve consensus oluştur"""
        
        # İki AI de aynı yönde mi?
        if deepseek_signal['direction'] == gemini_signal['direction']:
            logger.info(f"✅ {symbol}: AI consensus - {deepseek_signal['direction']}")
            
            # Consensus boost: confidence artır
            avg_confidence = (deepseek_signal['confidence'] + gemini_signal['confidence']) / 2
            boosted_confidence = min(95, avg_confidence + 15)  # Max 95
            
            # DeepSeek sinyalini base al, confidence'ı boost et
            consensus = deepseek_signal.copy()
            consensus['confidence'] = boosted_confidence
            consensus['ai_source'] = 'consensus'
            consensus['reasoning'] = f"DeepSeek & Gemini consensus: {deepseek_signal['reasoning']}"
            
            return consensus
        
        # Çelişki var
        logger.warning(f"⚠️ {symbol}: AI disagreement - DeepSeek: {deepseek_signal['direction']}, Gemini: {gemini_signal['direction']}")
        
        # Hangisi daha confident?
        if deepseek_signal['confidence'] > gemini_signal['confidence'] + 20:
            logger.info(f"   → DeepSeek daha confident ({deepseek_signal['confidence']} vs {gemini_signal['confidence']})")
            deepseek_signal['ai_source'] = 'deepseek_preferred'
            return deepseek_signal
        elif gemini_signal['confidence'] > deepseek_signal['confidence'] + 20:
            logger.info(f"   → Gemini daha confident ({gemini_signal['confidence']} vs {deepseek_signal['confidence']})")
            gemini_signal['ai_source'] = 'gemini_preferred'
            return gemini_signal
        else:
            # Çok yakın confidence seviyeleri - güvenli tarafta kal
            logger.info(f"   → Çelişki + yakın confidence → HOLD")
            return self._get_hold_signal(symbol, f"AI disagreement (DeepSeek: {deepseek_signal['direction']}, Gemini: {gemini_signal['direction']})")
    
    def _get_hold_signal(self, symbol: str, reason: str) -> Dict:
        """HOLD sinyali döndür"""
        return {
            'direction': 'HOLD',
            'confidence': 0,
            'entry_price': 0,
            'stop_loss': 0,
            'take_profit': 0,
            'reasoning': reason,
            'ai_source': 'none',
            'risk_reward_ratio': 0
        }


# ============================================================================
# TEST
# ============================================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/Users/macbook/Desktop/ChimeraBot')
    
    from src import config
    from src.data_fetcher.binance_fetcher import get_binance_klines
    from src.technical_analyzer.indicators import calculate_indicators
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s'
    )
    
    print("\n" + "="*70)
    print("🤖 AI SIGNAL GENERATOR TEST")
    print("="*70)
    
    # Initialize
    ai_gen = AISignalGenerator(config)
    
    # Test symbol
    test_symbol = 'BTCUSDT'
    
    print(f"\n📊 {test_symbol} için veri çekiliyor...")
    
    # Fetch data
    df_1h = get_binance_klines(test_symbol, '1h', limit=200)
    df_15m = get_binance_klines(test_symbol, '15m', limit=200)
    
    if df_1h is None or df_15m is None:
        print("❌ Veri çekilemedi")
        sys.exit(1)
    
    # Calculate indicators
    df_1h = calculate_indicators(df_1h)
    df_15m = calculate_indicators(df_15m)
    
    print("✅ Veriler hazır\n")
    
    # Generate signal
    print("🤖 AI analizi başlatılıyor...\n")
    
    signal = ai_gen.generate_signal(
        symbol=test_symbol,
        df_1h=df_1h,
        df_15m=df_15m,
        additional_context={'fear_greed_index': 15}
    )
    
    print("\n" + "="*70)
    print("📊 AI SİNYAL SONUCU")
    print("="*70)
    print(f"Yön:          {signal['direction']}")
    print(f"Confidence:   {signal['confidence']}")
    print(f"Entry:        ${signal['entry_price']:.2f}")
    print(f"Stop Loss:    ${signal['stop_loss']:.2f}")
    print(f"Take Profit:  ${signal['take_profit']:.2f}")
    print(f"Risk/Reward:  1:{signal['risk_reward_ratio']:.2f}")
    print(f"AI Source:    {signal['ai_source']}")
    print(f"\nAçıklama:\n{signal['reasoning']}")
    print("="*70 + "\n")
