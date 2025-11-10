# src/risk_manager/calculator.py

import logging
import pandas as pd
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def find_recent_swing_levels(df: pd.DataFrame, lookback_period: int = 50) -> Optional[Dict[str, float]]:
    """
    (ARTIK KULLANILMIYOR - ATR TABANLI SİSTEME GEÇİLDİ)
    Verilen DataFrame'in son 'lookback_period' mumu içindeki
    en yüksek ve en düşük fiyatları (Destek/Direnç) bulur.
    """
    logger.debug(f"(Eski Metot) Son {lookback_period} mum için yapısal seviyeler aranıyor...")
    if df is None or df.empty or len(df) < lookback_period:
        logger.warning(f"Yapısal seviyeler için yeterli veri yok (Gereken: {lookback_period}, Mevcut: {len(df)})")
        return None
    
    recent_data = df.iloc[-lookback_period:]
    support = recent_data['low'].min()
    resistance = recent_data['high'].max()
    
    if support and resistance:
        logger.info(f"   Yapısal Seviyeler (Son {lookback_period} mum): Destek={support:.2f}, Direnç={resistance:.2f}")
        return {'support': support, 'resistance': resistance}
    else:
        logger.warning(f"Destek/Direnç seviyeleri hesaplanamadı (Veri: {recent_data}).")
        return None


def calculate_structural_sl_tp(direction: str, entry_price: float, levels: dict,
                               sl_buffer_percent: float, tp_buffer_percent: float) -> Optional[Dict[str, float]]:
    """
    (ARTIK KULLANILMIYOR - ATR TABANLI SİSTEME GEÇİLDİ)
    Yapısal seviyelere göre SL/TP hesaplar.
    """
    try:
        support = levels['support']
        resistance = levels['resistance']
        
        sl_price = 0.0
        tp_price = 0.0

        if direction == 'LONG':
            sl_price = support * (1 - (sl_buffer_percent / 100)) # Desteğin %x altı
            tp_price = resistance * (1 - (tp_buffer_percent / 100)) # Direncin %x altı
        elif direction == 'SHORT':
            sl_price = resistance * (1 + (sl_buffer_percent / 100)) # Direncin %x üstü
            tp_price = support * (1 + (tp_buffer_percent / 100)) # Desteğin %x üstü
        
        if sl_price <= 0 or tp_price <= 0:
             logger.warning(f"Hesaplanan SL/TP geçersiz (<= 0). SL: {sl_price}, TP: {tp_price}")
             return None

        logger.info(f"   SL/TP ({direction}): Giriş={entry_price:.2f}, SL={sl_price:.2f}, TP={tp_price:.2f}")
        return {'sl_price': sl_price, 'tp_price': tp_price}
        
    except Exception as e:
        logger.error(f"Yapısal SL/TP hesaplanırken hata: {e}", exc_info=True)
        return None

# --- YENİ EKLENDİ v6.0: Yüzde Tabanlı SL/TP Hesaplayıcı (7 Kasım 2025) ---

def calculate_percentage_sl_tp(entry_price: float, direction: str, config: object) -> Optional[Dict[str, float]]:
    """
    Giriş fiyatına göre kaldıraçlı yüzde tabanlı SL/TP hesaplar.
    
    v9.2 GÜNCELEME: Partial TP kapalıysa tek TP kullanır.
    
    Sistem (v7.0 DÜZELTME - Kaldıraç dikkate alınıyor):
    - SL: Pozisyon değerinin %10 zararı = Spot fiyatın (10% / kaldıraç) mesafesi
    
    Partial TP AÇIK ise:
    - TP_1: Pozisyon değerinin %20 karı = Spot fiyatın (20% / kaldıraç) mesafesi
    - TP_2: Pozisyon değerinin %40 karı = Spot fiyatın (40% / kaldıraç) mesafesi
    
    Partial TP KAPALI ise (v9.2):
    - TP: Pozisyon değerinin %30 karı = Spot fiyatın (30% / kaldıraç) mesafesi (3.0 R:R)
    
    Örnek (8x kaldıraç, Partial TP kapalı):
    - SL: %10 pozisyon zararı = %1.25 spot fiyat hareketi
    - TP: %30 pozisyon karı = %3.75 spot fiyat hareketi (R:R = 3.0)
    """
    try:
        # Partial TP ayarlarını kontrol et
        partial_tp_enabled = getattr(config, 'PARTIAL_TP_ENABLED', True)
        
        # Pozisyon bazlı yüzde değerleri
        position_sl_percent = getattr(config, 'SL_PERCENT', 10.0)
        
        if partial_tp_enabled:
            # ESKİ SİSTEM: Partial TP aktif
            position_tp1_percent = getattr(config, 'PARTIAL_TP_1_PROFIT_PERCENT', 20.0)
            position_tp2_percent = getattr(config, 'PARTIAL_TP_2_PROFIT_PERCENT', 40.0)
        else:
            # YENİ SİSTEM: Tek TP (v9.2)
            position_tp_percent = getattr(config, 'TP_PROFIT_PERCENT', 30.0)
            position_tp1_percent = None  # Kullanılmayacak
            position_tp2_percent = position_tp_percent  # Ana TP
        
        # Kaldıraç değeri
        leverage = getattr(config, 'FUTURES_LEVERAGE', 8)
        
        # SPOT fiyat hareketi = Pozisyon hareketi / Kaldıraç
        spot_sl_percent = position_sl_percent / leverage
        
        if partial_tp_enabled:
            spot_tp1_percent = position_tp1_percent / leverage
            spot_tp2_percent = position_tp2_percent / leverage
        else:
            spot_tp_percent = position_tp2_percent / leverage  # Tek TP
        
        sl_price = 0.0
        tp1_price = None
        tp2_price = 0.0

        if direction.upper() == 'LONG':
            # LONG: SL aşağıda, TP yukarıda
            sl_price = entry_price * (1 - (spot_sl_percent / 100.0))
            if partial_tp_enabled:
                tp1_price = entry_price * (1 + (spot_tp1_percent / 100.0))
                tp2_price = entry_price * (1 + (spot_tp2_percent / 100.0))
            else:
                tp2_price = entry_price * (1 + (spot_tp_percent / 100.0))
        elif direction.upper() == 'SHORT':
            # SHORT: SL yukarıda, TP aşağıda
            sl_price = entry_price * (1 + (spot_sl_percent / 100.0))
            if partial_tp_enabled:
                tp1_price = entry_price * (1 - (spot_tp1_percent / 100.0))
                tp2_price = entry_price * (1 - (spot_tp2_percent / 100.0))
            else:
                tp2_price = entry_price * (1 - (spot_tp_percent / 100.0))
        else:
            logger.error(f"Geçersiz yön: {direction}")
            return None

        if sl_price <= 0 or tp2_price <= 0:
            logger.warning(f"Hesaplanan SL/TP geçersiz (<= 0). SL: {sl_price}, TP: {tp2_price}")
            return None

        # R:R hesaplama
        if direction.upper() == 'LONG':
            risk_distance = entry_price - sl_price
            reward_distance = tp2_price - entry_price
            if partial_tp_enabled and tp1_price:
                reward1_distance = tp1_price - entry_price
        else:
            risk_distance = sl_price - entry_price
            reward_distance = entry_price - tp2_price
            if partial_tp_enabled and tp1_price:
                reward1_distance = entry_price - tp1_price
        
        rr = reward_distance / risk_distance if risk_distance > 0 else 0

        logger.info(f"   Kaldıraçlı SL/TP ({direction}, {leverage}x): Giriş={entry_price:.4f}")
        logger.info(f"   SL={sl_price:.4f} (-{spot_sl_percent:.2f}% spot = -{position_sl_percent}% pozisyon)")
        
        if partial_tp_enabled and tp1_price:
            rr1 = reward1_distance / risk_distance if risk_distance > 0 else 0
            logger.info(f"   TP1={tp1_price:.4f} (+{spot_tp1_percent:.2f}% spot = +{position_tp1_percent}% pozisyon, R:R={rr1:.2f})")
            logger.info(f"   TP2={tp2_price:.4f} (+{spot_tp2_percent:.2f}% spot = +{position_tp2_percent}% pozisyon, R:R={rr:.2f})")
        else:
            logger.info(f"   TP={tp2_price:.4f} (+{spot_tp_percent:.2f}% spot = +{position_tp2_percent}% pozisyon, R:R={rr:.2f}) 🎯")
        
        result = {
            'sl_price': sl_price, 
            'tp_price': tp2_price  # Ana TP
        }
        
        if partial_tp_enabled and tp1_price:
            result['partial_tp_1_price'] = tp1_price  # İlk kısmi TP
        
        return result
        
    except Exception as e:
        logger.error(f"Yüzde tabanlı SL/TP hesaplanırken hata: {e}", exc_info=True)
        return None

# --- YENİ EKLENDİ: Dinamik (ATR Tabanlı) SL/TP Hesaplayıcı ---

def calculate_dynamic_sl_tp(entry_price: float, atr: float, direction: str, config: object, strategy: str = None) -> Optional[Dict[str, float]]:
    """
    Giriş fiyatı ve güncel ATR değerine göre dinamik Stop-Loss ve Take-Profit hesaplar.
    Stratejiye ve volatiliteye göre adaptif çarpanlar kullanır (v4.0 Enhancement).
    """
    try:
        # Config'den base ATR çarpanlarını al
        sl_multiplier = getattr(config, 'SL_ATR_MULTIPLIER', 2.0)
        tp_multiplier = getattr(config, 'TP_ATR_MULTIPLIER', 3.5)
        
        # YENİ: Stratejiye göre adaptif çarpanlar (v4.0)
        if strategy:
            if strategy == 'MOMENTUM_SCALP' or strategy == 'ADVANCED_SCALP':
                # Scalping için daha sıkı SL/TP
                sl_multiplier = 1.5  # Config'den de alınabilir
                tp_multiplier = 2.5
                logger.debug(f"   Scalping stratejisi için özel ATR çarpanları: SL={sl_multiplier}, TP={tp_multiplier}")
            elif strategy == 'BREAKOUT':
                # Breakout için daha geniş SL (false breakout'a karşı)
                sl_multiplier = 2.5
                tp_multiplier = 4.0
                logger.debug(f"   Breakout stratejisi için özel ATR çarpanları: SL={sl_multiplier}, TP={tp_multiplier}")
            elif strategy == 'MEAN_REVERSION':
                # Mean reversion için orta sıkılıkta
                sl_multiplier = 1.8
                tp_multiplier = 3.0
                logger.debug(f"   Mean Reversion stratejisi için özel ATR çarpanları: SL={sl_multiplier}, TP={tp_multiplier}")
        
        # Volatilite bazlı ek ayarlama (isteğe bağlı)
        volatility_ratio = atr / entry_price
        if volatility_ratio > 0.15:  # Yüksek volatilite (%15+)
            sl_multiplier *= 1.3
            logger.debug(f"   Yüksek volatilite tespit edildi ({volatility_ratio:.3f}), SL çarpanı artırıldı: {sl_multiplier:.2f}")
        elif volatility_ratio < 0.05:  # Düşük volatilite (%5-)
            sl_multiplier *= 0.8
            logger.debug(f"   Düşük volatilite tespit edildi ({volatility_ratio:.3f}), SL çarpanı azaltıldı: {sl_multiplier:.2f}")

        if atr <= 0:
            logger.warning("ATR değeri geçersiz (<= 0), SL/TP hesaplanamıyor.")
            return None
            
        sl_price = 0.0
        tp_price = 0.0

        if direction.upper() == 'LONG':
            sl_distance = atr * sl_multiplier
            tp_distance = atr * tp_multiplier
            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
        elif direction.upper() == 'SHORT':
            sl_distance = atr * sl_multiplier
            tp_distance = atr * tp_multiplier
            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance
        else:
             logger.error(f"Geçersiz yön: {direction}")
             return None

        if sl_price <= 0 or tp_price <= 0:
             logger.warning(f"Hesaplanan SL/TP geçersiz (<= 0). SL: {sl_price}, TP: {tp_price}")
             return None

        logger.info(f"   Dinamik SL/TP ({direction}): Giriş={entry_price:.4f}, ATR={atr:.4f}")
        logger.info(f"   SL={sl_price:.4f} (Çarpan: {sl_multiplier}x), TP={tp_price:.4f} (Çarpan: {tp_multiplier}x)")
        return {'sl_price': sl_price, 'tp_price': tp_price}

    except Exception as e:
        logger.error(f"Dinamik SL/TP hesaplanırken hata: {e}", exc_info=True)
        return None

# --- Risk/Ödül Hesaplayıcı (Değişiklik Yok) ---

def calculate_rr(entry_price: float, sl_price: float, tp_price: float, direction: str) -> Optional[float]:
    """Hesaplanan SL/TP'ye göre Risk/Ödül oranını hesaplar."""
    try:
        risk_distance = 0.0
        reward_distance = 0.0

        if direction.upper() == 'LONG':
            risk_distance = entry_price - sl_price
            reward_distance = tp_price - entry_price
        elif direction.upper() == 'SHORT':
            risk_distance = sl_price - entry_price
            reward_distance = entry_price - tp_price
        
        if risk_distance <= 0: # Risk sıfır veya negatifse (hatalı SL)
            logger.warning(f"R:R hesaplanamadı: Risk mesafesi sıfır veya negatif ({risk_distance:.4f}). SL/Giriş fiyatları hatalı olabilir.")
            return None
        
        if reward_distance <= 0: # Ödül sıfır veya negatifse (hatalı TP)
             logger.warning(f"R:R hesaplanamadı: Ödül mesafesi sıfır veya negatif ({reward_distance:.4f}). TP/Giriş fiyatları hatalı olabilir.")
             return None

        rr_ratio = reward_distance / risk_distance
        
        logger.info(f"   R:R ({direction}): Risk Mesafesi={risk_distance:.4f}, Ödül Mesafesi={reward_distance:.4f}, R:R Oranı={rr_ratio:.2f}")
        return rr_ratio

    except Exception as e:
        logger.error(f"R:R hesaplanırken hata: {e}", exc_info=True)
        return None


# --- v4.0 Enhanced: Volatilite Bazlı Position Sizing ---

def calculate_volatility_score(atr: float, price: float) -> float:
    """
    ATR/Price oranına göre volatilite skoru hesaplar (0.0 - 1.0 arası).
    Düşük volatilite = 0.0, Yüksek volatilite = 1.0
    """
    if price <= 0 or atr < 0:
        return 0.5  # Varsayılan (orta seviye)
    
    volatility_ratio = atr / price
    
    # 0% - 5% arası düşük volatilite (skor: 0.0 - 0.33)
    # 5% - 15% arası normal volatilite (skor: 0.33 - 0.66)
    # 15%+ yüksek volatilite (skor: 0.66 - 1.0)
    if volatility_ratio < 0.05:
        score = volatility_ratio / 0.05 * 0.33
    elif volatility_ratio < 0.15:
        score = 0.33 + ((volatility_ratio - 0.05) / 0.10) * 0.33
    else:
        score = min(0.66 + ((volatility_ratio - 0.15) / 0.10) * 0.34, 1.0)
    
    return score


def calculate_position_size_with_volatility(
    entry_price: float,
    sl_price: float,
    portfolio_usd: float,
    planned_risk_percent: float,
    atr: float,
    config: object
) -> Optional[Dict[str, float]]:
    """
    v6.0 FIXED RISK SYSTEM: Sabit risk bazlı pozisyon hesaplama
    
    YENİ SİSTEM:
    - Sabit risk: Her işlemde maksimum $5 kayıp (config'den)
    - Pozisyon boyutu: risk / (entry - sl)
    - Dinamik kaldıraç: SL mesafesine göre (dar SL → yüksek kaldıraç)
    - Güvenlik: Minimum %8 tasfiye-SL mesafesi
    
    ESKİ SİSTEM (USE_FIXED_RISK_USD=False):
    - Pozisyon değeri: portfolyo × %
    - Kaldıraç: Volatiliteye göre
    """
    try:
        # Config'den sabit risk modunu kontrol et
        use_fixed_risk = getattr(config, 'USE_FIXED_RISK_USD', True)
        
        if use_fixed_risk:
            # ═══════════════════════════════════════════════════════════
            # YENİ: SABİT RİSK SİSTEMİ (v9.2 MARGIN BAZLI)
            # ═══════════════════════════════════════════════════════════
            
            fixed_risk_usd = getattr(config, 'FIXED_RISK_USD', 5.0)
            
            # v9.2: MARGIN limitleri (position value DEĞİL!)
            min_margin_usd = getattr(config, 'MIN_MARGIN_USD', 150.0)
            max_margin_usd = getattr(config, 'MAX_MARGIN_USD', 300.0)
            
            min_safety_margin = getattr(config, 'MINIMUM_SAFETY_MARGIN', 0.08)
            
            # 1. SL mesafesi hesapla
            sl_distance_usd = abs(entry_price - sl_price)
            if sl_distance_usd <= 0:
                logger.warning("SL mesafesi geçersiz (<= 0)")
                return None
            
            sl_distance_percent = sl_distance_usd / entry_price
            
            # 2. Kaldıraç belirleme (Sabit veya Dinamik)
            dynamic_leverage_enabled = getattr(config, 'DYNAMIC_LEVERAGE_ENABLED', False)
            
            if dynamic_leverage_enabled:
                # DİNAMİK: SL mesafesine göre kaldıraç seç
                leverage_map = getattr(config, 'LEVERAGE_BY_SL_DISTANCE', {
                    0.02: 10, 0.05: 5, 0.10: 3, 0.15: 2
                })
                
                # En uygun kaldıracı bul
                leverage = 5  # default
                for sl_threshold, lev in sorted(leverage_map.items()):
                    if sl_distance_percent <= sl_threshold:
                        leverage = lev
                        break
                else:
                    # SL %15'ten büyükse en düşük kaldıraç
                    leverage = min(leverage_map.values())
                
                logger.debug(f"   🔧 Dinamik kaldıraç: SL {sl_distance_percent:.2%} → {leverage}x")
            else:
                # SABİT: Config'den al
                leverage = getattr(config, 'FUTURES_LEVERAGE', 5)
                logger.debug(f"   🔧 Sabit kaldıraç: {leverage}x")
            
            # 3. Pozisyon boyutu = Risk / SL mesafesi
            position_size_units = fixed_risk_usd / sl_distance_usd
            position_value_usd = position_size_units * entry_price
            initial_margin_usd = position_value_usd / leverage
            
            # 🆕 v9.2 FIX: MARGIN BAZLI KONTROL (position value DEĞİL!)
            # Kullanıcı: "Günde 1-2 pozisyon, kullanılan margin çok düşük (5 USD)"
            # Çözüm: Minimum margin = 150 USD
            
            if initial_margin_usd < min_margin_usd:
                logger.info(f"   � Kullanılan margin minimum altında: ${initial_margin_usd:.2f} < ${min_margin_usd:.2f}")
                logger.info(f"   🔧 Margin minimum değere ayarlanıyor: ${min_margin_usd:.2f}")
                
                # Margin'den position value hesapla
                position_value_usd = min_margin_usd * leverage
                position_size_units = position_value_usd / entry_price
                
                # Risk yeniden hesapla (daha yüksek olacak)
                actual_risk = position_size_units * sl_distance_usd
                actual_margin_usd = min_margin_usd
                
                logger.info(f"   💰 Pozisyon değeri: ${position_value_usd:.2f} ({leverage}x kaldıraç)")
                logger.info(f"   ⚠️ Risk artışı: ${fixed_risk_usd:.2f} → ${actual_risk:.2f}")
            
            # Maksimum margin kontrolü
            elif initial_margin_usd > max_margin_usd:
                logger.debug(f"   ⚠️ Margin limit aşımı: ${initial_margin_usd:.2f} > ${max_margin_usd:.2f}")
                
                position_value_usd = max_margin_usd * leverage
                position_size_units = position_value_usd / entry_price
                actual_risk = position_size_units * sl_distance_usd
                actual_margin_usd = max_margin_usd
                
                logger.debug(f"   � Margin limiti nedeniyle risk azaldı: ${fixed_risk_usd:.2f} → ${actual_risk:.2f}")
            else:
                actual_risk = fixed_risk_usd
                actual_margin_usd = initial_margin_usd
            
            # 4. Güvenlik marjı kontrolü (bilgilendirme amaçlı)
            liquidation_distance = 1.0 / leverage
            safety_margin = liquidation_distance - sl_distance_percent
            
            logger.debug(f"   ℹ️  Güvenlik Marjı: {safety_margin:.2%} (Tasfiye: {liquidation_distance:.2%}, SL: {sl_distance_percent:.2%})")
            if safety_margin < 0:
                logger.warning(f"   ⚠️ TEHLİKE! SL tasfiyeden SONRA ({abs(safety_margin):.2%}). Kaldıraç: {leverage}x")
            
            # 5. Volatilite skoru (bilgi amaçlı)
            volatility_score = calculate_volatility_score(atr, entry_price) if atr else 0.5
            
            logger.info(f"   💰 Pozisyon Boyutu: {position_size_units:.4f} units (Değer: ${position_value_usd:.2f})")
            logger.info(f"   🎯 Risk: ${actual_risk:.2f}, SL Mesafe: {sl_distance_percent:.2%}")
            logger.info(f"   🔧 Kaldıraç: {leverage}x, Kullanılan Margin: ${actual_margin_usd:.2f} 💵")
            logger.info(f"   ✅ Güvenlik Marjı: {safety_margin:.2%} (Tasfiye: {liquidation_distance:.2%}, SL: {sl_distance_percent:.2%})")
            
            return {
                'final_risk_usd': actual_risk,
                'position_size_units': position_size_units,
                'position_value_usd': position_value_usd,
                'volatility_multiplier': 1.0,
                'volatility_score': volatility_score,
                'leverage': leverage,
                'margin_usd': actual_margin_usd,
                'safety_margin': safety_margin,
                'sl_distance_percent': sl_distance_percent
            }
        
        else:
            # ═══════════════════════════════════════════════════════════
            # ESKİ: VOLATİLİTE BAZLI SİSTEM (Yedek)
            # ═══════════════════════════════════════════════════════════
            
            # v5.0: Dinamik kaldıraç hesaplama
            volatility_ratio = atr / entry_price if entry_price > 0 else 0
            
            dynamic_leverage_enabled = getattr(config, 'DYNAMIC_LEVERAGE_ENABLED', False)
            
            if dynamic_leverage_enabled:
                # Volatiliteye göre kaldıraç seç
                if volatility_ratio < 0.05:  # < %5
                    leverage = getattr(config, 'LEVERAGE_LOW_VOLATILITY', 5)
                    logger.debug(f"   📉 Düşük Volatilite ({volatility_ratio:.2%}) → Kaldıraç: {leverage}x")
                elif volatility_ratio < 0.15:  # 5% - 15%
                    leverage = getattr(config, 'LEVERAGE_MID_VOLATILITY', 3)
                    logger.debug(f"   📊 Orta Volatilite ({volatility_ratio:.2%}) → Kaldıraç: {leverage}x")
                else:  # > 15%
                    leverage = getattr(config, 'LEVERAGE_HIGH_VOLATILITY', 2)
                    logger.debug(f"   📈 Yüksek Volatilite ({volatility_ratio:.2%}) → Kaldıraç: {leverage}x (KORUMA)")
            else:
                # Statik kaldıraç
                leverage = getattr(config, 'FUTURES_LEVERAGE', 1)
                logger.debug(f"   🔧 Statik Kaldıraç: {leverage}x")
            
            # v5.2 YENİ MANTIK: Sabit pozisyon değeri (Binance Futures mantığı)
            # planned_risk_percent = pozisyon değerinin yüzdesi (kaldıraç DAHİL)
            # Örnek: $200 portföy, %10 risk = $20 pozisyon değeri
            position_value_usd = portfolio_usd * (planned_risk_percent / 100.0)  # $20
            
            # Pozisyon boyutunu hesapla (unit)
            position_size_units = position_value_usd / entry_price
            
            # Gerçek margin kullanımı (kaldıraç ile bölünür)
            actual_margin_usd = position_value_usd / leverage
            
            # Risk hesaplama (SL'ye göre)
            risk_per_unit = abs(entry_price - sl_price)
            if risk_per_unit <= 0:
                logger.warning("SL mesafesi geçersiz: risk_per_unit <= 0")
                return None
            
            actual_risk_at_sl = position_size_units * risk_per_unit
            
            logger.debug(f"   💰 Pozisyon Değeri: ${position_value_usd:.2f} (hedef)")
            logger.debug(f"   📊 Position Size: {position_size_units:.4f} units")
            logger.debug(f"   💵 Margin Kullanımı: ${actual_margin_usd:.2f} ({leverage}x leverage)")
            logger.debug(f"   ⚠️  Risk (SL'de): ${actual_risk_at_sl:.2f}")
            
            if leverage > 1:
                # Tasfiye mesafesi uyarısı
                liquidation_distance = 1.0 / leverage  # 3x → %33, 5x → %20, 2x → %50
                sl_distance_percent = abs((entry_price - sl_price) / entry_price)
                safety_margin = liquidation_distance - sl_distance_percent
                
                if safety_margin < 0.03:  # %3'ten az güvenlik marjı
                    logger.warning(f"   ⚠️ TAHLİKE! Tasfiye mesafesi çok yakın: {safety_margin:.2%} (SL: {sl_distance_percent:.2%}, Tasfiye: {liquidation_distance:.2%})")
                else:
                    logger.debug(f"   ✅ Güvenlik Marjı: {safety_margin:.2%} (SL'den sonra tasfiyeye mesafe)")
            
            # Volatilite ayarlaması aktif mi?
            if not getattr(config, 'VOLATILITY_ADJUSTMENT_ENABLED', False):
                return {
                    'final_risk_usd': actual_risk_at_sl,  # Gerçek risk (SL'de)
                    'position_size_units': position_size_units,
                    'volatility_multiplier': 1.0,
                    'volatility_score': 0.5,
                    'leverage': leverage  # YENİ: Aşama 2
                }
            
            
            # Volatilite skoru hesapla
            volatility_score = calculate_volatility_score(atr, entry_price)
            volatility_ratio = atr / entry_price
            
            # Config'den eşik ve çarpanları al
            low_threshold = getattr(config, 'VOLATILITY_LOW_THRESHOLD', 0.05)
            high_threshold = getattr(config, 'VOLATILITY_HIGH_THRESHOLD', 0.15)
            low_multiplier = getattr(config, 'VOLATILITY_LOW_MULTIPLIER', 1.2)
            high_multiplier = getattr(config, 'VOLATILITY_HIGH_MULTIPLIER', 0.7)
            
            # Volatilite çarpanını belirle
            if volatility_ratio < low_threshold:
                # Düşük volatilite: Pozisyon boyutunu artır
                volatility_multiplier = low_multiplier
                logger.debug(f"   📉 Düşük Volatilite (ATR/Price={volatility_ratio:.3f} < {low_threshold})")
                logger.debug(f"   Pozisyon boyutu {(low_multiplier-1)*100:.0f}% ARTTIRILDI")
            elif volatility_ratio > high_threshold:
                # Yüksek volatilite: Pozisyon boyutunu azalt
                volatility_multiplier = high_multiplier
                logger.debug(f"   📈 Yüksek Volatilite (ATR/Price={volatility_ratio:.3f} > {high_threshold})")
                logger.debug(f"   Pozisyon boyutu {(1-high_multiplier)*100:.0f}% AZALTILDI")
            else:
                # Normal volatilite: Değişiklik yok
                volatility_multiplier = 1.0
                logger.debug(f"   📊 Normal Volatilite (ATR/Price={volatility_ratio:.3f})")
            
            # Final pozisyon boyutu (volatilite ayarlamalı)
            adjusted_position_size = position_size_units * volatility_multiplier
            adjusted_risk_at_sl = adjusted_position_size * risk_per_unit
            
            logger.info(f"   💰 Pozisyon Boyutu: {position_size_units:.4f} → {adjusted_position_size:.4f} (x{volatility_multiplier:.2f})")
            logger.info(f"   Volatilite Skoru: {volatility_score:.2f}, Risk (SL'de): ${adjusted_risk_at_sl:.2f}")
            
            return {
                'final_risk_usd': adjusted_risk_at_sl,
                'position_size_units': adjusted_position_size,
                'volatility_multiplier': volatility_multiplier,
                'volatility_score': volatility_score,
                'leverage': leverage  # YENİ: Aşama 2
            }
    
    except Exception as e:
        logger.error(f"Volatilite bazlı pozisyon boyutu hesaplanırken hata: {e}", exc_info=True)
        return None