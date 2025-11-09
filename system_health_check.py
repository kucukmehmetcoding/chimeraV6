#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistem Sağlık Kontrolü
Tüm bileşenleri test eder ve problemleri tespit eder
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def comprehensive_health_check():
    """Tüm sistem bileşenlerini kontrol et"""
    
    print("="*80)
    print("🏥 ChimeraBot - Kapsamlı Sistem Sağlık Kontrolü")
    print("="*80)
    
    issues = []
    warnings = []
    passed = []
    
    # ==================== 1. CONFIG KONTROLÜ ====================
    print("\n📋 1. CONFIG KONTROLÜ")
    print("-"*80)
    try:
        from src import config
        
        # Trading mode
        if config.BINANCE_TESTNET:
            print(f"   ⚠️  TESTNET MODE aktif")
            warnings.append("TESTNET mode - gerçek para kullanılmıyor")
        else:
            print(f"   ✅ LIVE MODE aktif")
            passed.append("Live trading mode enabled")
        
        # API keys
        if "PLACEHOLDER" in config.BINANCE_API_KEY:
            print(f"   ❌ API Key placeholder değerde!")
            issues.append("CRITICAL: Binance API key tanımlanmamış")
        else:
            print(f"   ✅ API Key tanımlı: {config.BINANCE_API_KEY[:10]}...")
            passed.append("API credentials configured")
        
        # Telegram
        if "PLACEHOLDER" in config.TELEGRAM_BOT_TOKEN:
            print(f"   ⚠️  Telegram bot token placeholder!")
            warnings.append("Telegram bildirimleri çalışmayabilir")
        else:
            print(f"   ✅ Telegram token tanımlı")
            passed.append("Telegram configured")
        
        # Risk parametreleri
        print(f"\n   📊 Risk Parametreleri:")
        print(f"      - Kaldıraç: {config.FUTURES_LEVERAGE}x")
        print(f"      - Base Risk: {getattr(config, 'BASE_RISK_PERCENT', 'TANIMLI DEĞİL')}%")
        print(f"      - Max Pozisyon: {getattr(config, 'MAX_OPEN_POSITIONS', 'TANIMLI DEĞİL')}")
        print(f"      - Grup Risk Limiti: {getattr(config, 'MAX_RISK_PER_GROUP', 'TANIMLI DEĞİL')}%")
        
        # v7.0 parametreleri
        print(f"\n   🆕 v7.0 Özellikleri:")
        corr_threshold = getattr(config, 'BTC_CORRELATION_THRESHOLD', None)
        if corr_threshold:
            print(f"      ✅ BTC_CORRELATION_THRESHOLD: {corr_threshold}")
            passed.append("Correlation-based regime enabled")
        else:
            print(f"      ⚠️  BTC_CORRELATION_THRESHOLD tanımlı değil")
            warnings.append("Korelasyon bazlı rejim seçimi pasif olabilir")
        
        use_kelly = getattr(config, 'USE_KELLY_ADJUSTMENT', False)
        print(f"      ℹ️  USE_KELLY_ADJUSTMENT: {use_kelly}")
        
    except Exception as e:
        print(f"   ❌ Config hatası: {e}")
        issues.append(f"Config yüklenemedi: {e}")
    
    # ==================== 2. DATABASE KONTROLÜ ====================
    print("\n💾 2. DATABASE KONTROLÜ")
    print("-"*80)
    try:
        from src.database.models import get_db_session, OpenPosition, TradeHistory, AlphaCache
        
        with get_db_session() as db:
            open_count = db.query(OpenPosition).count()
            history_count = db.query(TradeHistory).count()
            cache_count = db.query(AlphaCache).count()
            
            print(f"   ✅ Database bağlantısı başarılı")
            print(f"   📊 Açık Pozisyonlar: {open_count}")
            print(f"   📜 Trade History: {history_count}")
            print(f"   🗄️  Alpha Cache: {cache_count}")
            
            # Korelasyon matrisi kontrolü
            corr_cache = db.query(AlphaCache).filter(AlphaCache.key == 'correlation_matrix').first()
            if corr_cache and corr_cache.value:
                btc_data = corr_cache.value.get('BTCUSDT', {})
                print(f"   ✅ Korelasyon Matrisi: {len(btc_data)} coin")
                passed.append(f"Correlation matrix: {len(btc_data)} coins")
            else:
                print(f"   ⚠️  Korelasyon Matrisi yok (ilk scan'de hesaplanacak)")
                warnings.append("Correlation matrix not yet calculated")
            
            # v7.0 kolonları
            print(f"\n   🔍 v7.0 Kolonları:")
            test_pos = db.query(OpenPosition).first()
            if test_pos:
                v7_fields = ['volatility_score', 'kelly_percent', 'kelly_confidence']
                for field in v7_fields:
                    if hasattr(test_pos, field):
                        print(f"      ✅ {field}")
                    else:
                        print(f"      ❌ {field} eksik!")
                        issues.append(f"Database kolonu eksik: {field}")
            else:
                print(f"      ℹ️  Pozisyon yok, kolon kontrolü yapılamadı")
            
            passed.append("Database connection healthy")
    
    except Exception as e:
        print(f"   ❌ Database hatası: {e}")
        issues.append(f"Database problemi: {e}")
    
    # ==================== 3. BINANCE API KONTROLÜ ====================
    print("\n🌐 3. BINANCE API KONTROLÜ")
    print("-"*80)
    try:
        from src.data_fetcher import binance_fetcher
        
        # Test data fetch
        test_df = binance_fetcher.get_binance_klines('BTCUSDT', '1d', 5)
        
        if test_df is not None and not test_df.empty:
            print(f"   ✅ API bağlantısı çalışıyor")
            print(f"   ✅ Test verisi alındı: {len(test_df)} mum")
            print(f"   📊 Son BTC fiyatı: ${test_df.iloc[-1]['close']:.2f}")
            passed.append("Binance API connection working")
        else:
            print(f"   ❌ API'den veri alınamadı!")
            issues.append("Binance API veri dönmüyor")
        
        # Balance kontrolü
        try:
            from src.trade_manager import executor
            if executor and hasattr(executor, 'get_futures_account_balance'):
                balance = executor.get_futures_account_balance()
                if balance > 0:
                    print(f"   💰 Bakiye: ${balance:.2f} USDT")
                    passed.append(f"Account balance: ${balance:.2f}")
                else:
                    print(f"   ⚠️  Bakiye alınamadı veya 0")
                    warnings.append("Balance check failed")
        except Exception as bal_err:
            print(f"   ⚠️  Bakiye kontrolü yapılamadı: {bal_err}")
            warnings.append("Balance API not accessible")
    
    except Exception as e:
        print(f"   ❌ Binance API hatası: {e}")
        issues.append(f"Binance API problemi: {e}")
    
    # ==================== 4. İNDİKATÖRLER KONTROLÜ ====================
    print("\n📈 4. İNDİKATÖRLER KONTROLÜ")
    print("-"*80)
    try:
        from src.technical_analyzer import indicators
        from src.data_fetcher import binance_fetcher
        import pandas as pd
        
        # BTC verisi al ve işle
        btc_df = binance_fetcher.get_binance_klines('BTCUSDT', '1d', 200)
        
        if btc_df is None or btc_df.empty:
            print(f"   ❌ BTC verisi alınamadı!")
            issues.append("BTC data fetch failed")
        else:
            print(f"   ✅ BTC verisi alındı: {len(btc_df)} mum")
            
            # İndikatörleri hesapla
            btc_with_ind = indicators.calculate_indicators(btc_df.copy())
            
            # Kritik indikatörler
            critical_indicators = ['ema5', 'ema20', 'ema50', 'sma200', 'rsi14', 'macd_hist', 'adx14', 'bbw', 'atr14']
            
            print(f"\n   🔍 Kritik İndikatörler:")
            all_present = True
            for ind in critical_indicators:
                if ind in btc_with_ind.columns:
                    last_val = btc_with_ind[ind].iloc[-1]
                    if pd.isna(last_val):
                        print(f"      ⚠️  {ind}: NaN!")
                        warnings.append(f"Indicator {ind} is NaN")
                        all_present = False
                    else:
                        print(f"      ✅ {ind}: {last_val:.4f}")
                else:
                    print(f"      ❌ {ind}: EKSIK!")
                    issues.append(f"Indicator {ind} missing")
                    all_present = False
            
            if all_present:
                passed.append("All indicators calculated correctly")
            
            # Son bar kontrolü
            last_row = btc_with_ind.iloc[-1]
            nan_count = last_row[critical_indicators].isna().sum()
            
            if nan_count == 0:
                print(f"\n   ✅ Son bar'da NaN yok (tüm indikatörler sağlıklı)")
                passed.append("No NaN values in latest bar")
            else:
                print(f"\n   ⚠️  Son bar'da {nan_count} NaN değer var!")
                warnings.append(f"{nan_count} NaN values in indicators")
    
    except Exception as e:
        print(f"   ❌ İndikatör hatası: {e}")
        issues.append(f"Indicator calculation failed: {e}")
    
    # ==================== 5. STRATEJİ KONTROLÜ ====================
    print("\n🎯 5. STRATEJİ KONTROLÜ")
    print("-"*80)
    try:
        from src.technical_analyzer import strategies
        from src.data_fetcher import binance_fetcher
        from src.technical_analyzer import indicators
        
        # BTC rejim testi
        btc_1d = binance_fetcher.get_binance_klines('BTCUSDT', '1d', 200)
        btc_4h = binance_fetcher.get_binance_klines('BTCUSDT', '4h', 200)
        
        if btc_1d is not None and btc_4h is not None:
            btc_1d_ind = indicators.calculate_indicators(btc_1d.copy())
            btc_4h_ind = indicators.calculate_indicators(btc_4h.copy())
            
            regime = strategies.determine_regime(btc_1d_ind, btc_4h_ind)
            
            print(f"   ✅ BTC Rejimi: {regime}")
            
            if 'adx14' in btc_1d_ind.columns and 'bbw' in btc_1d_ind.columns:
                adx = btc_1d_ind['adx14'].iloc[-1]
                bbw = btc_1d_ind['bbw'].iloc[-1]
                print(f"   📊 ADX: {adx:.2f}, BBW: {bbw:.4f}")
                
                if regime == 'STOP':
                    print(f"   ⚠️  STOP rejimi - sınırlı sinyal beklenir")
                    warnings.append("BTC in STOP regime - fewer signals expected")
                else:
                    print(f"   ✅ Aktif rejim - sinyaller üretilebilir")
                    passed.append(f"Active regime: {regime}")
            
            # Test coin stratejisi
            eth_1d = binance_fetcher.get_binance_klines('ETHUSDT', '1d', 200)
            eth_4h = binance_fetcher.get_binance_klines('ETHUSDT', '4h', 200)
            eth_1h = binance_fetcher.get_binance_klines('ETHUSDT', '1h', 200)
            
            if eth_1d is not None and eth_4h is not None and eth_1h is not None:
                eth_1d_ind = indicators.calculate_indicators(eth_1d.copy())
                eth_4h_ind = indicators.calculate_indicators(eth_4h.copy())
                eth_1h_ind = indicators.calculate_indicators(eth_1h.copy())
                
                # PULLBACK testi
                pullback_signal = strategies.strategy_pullback(eth_1d_ind, eth_4h_ind, eth_1h_ind, {})
                
                if pullback_signal:
                    print(f"   ✅ ETHUSDT Pullback: {pullback_signal.get('direction', 'N/A')}")
                    passed.append("Strategy execution working")
                else:
                    print(f"   ℹ️  ETHUSDT'de pullback yok (normal)")
        else:
            print(f"   ❌ BTC verisi alınamadı!")
            issues.append("Strategy test failed - data unavailable")
    
    except Exception as e:
        print(f"   ❌ Strateji hatası: {e}")
        issues.append(f"Strategy execution error: {e}")
    
    # ==================== 6. RİSK YÖNETİMİ KONTROLÜ ====================
    print("\n🛡️  6. RİSK YÖNETİMİ KONTROLÜ")
    print("-"*80)
    try:
        from src.risk_manager import calculator
        from src import config
        
        # Test position sizing
        test_sizing = calculator.calculate_position_size_with_volatility(
            entry_price=100.0,
            sl_price=95.0,
            portfolio_usd=1000.0,
            planned_risk_percent=1.0,
            atr=2.0,
            config=config
        )
        
        if test_sizing and 'position_size_units' in test_sizing:
            print(f"   ✅ Position Sizing çalışıyor")
            print(f"      - Pozisyon: {test_sizing['position_size_units']:.4f} units")
            print(f"      - Volatilite Skoru: {test_sizing.get('volatility_score', 'N/A')}")
            print(f"      - Volatilite Multiplier: {test_sizing.get('volatility_multiplier', 'N/A')}")
            passed.append("Position sizing calculator working")
        else:
            print(f"   ❌ Position sizing başarısız!")
            issues.append("Position sizing failed")
        
        # SL/TP hesaplama
        test_sl_tp = calculator.calculate_percentage_sl_tp(100.0, 'LONG', config)
        
        if test_sl_tp:
            print(f"   ✅ SL/TP Hesaplama çalışıyor")
            print(f"      - SL: {test_sl_tp['sl_price']:.2f}")
            print(f"      - TP: {test_sl_tp['tp_price']:.2f}")
            passed.append("SL/TP calculation working")
        else:
            print(f"   ❌ SL/TP hesaplama başarısız!")
            issues.append("SL/TP calculation failed")
        
        # Kelly calculator (opsiyonel)
        try:
            from src.risk_manager.kelly_calculator import KellyPositionSizer
            from src.database.models import get_db_session
            
            with get_db_session() as db:
                kelly_sizer = KellyPositionSizer(config, db)
                kelly_result = kelly_sizer.calculate_kelly_size(
                    win_rate=0.60,
                    avg_win_loss_ratio=2.5,
                    rr_ratio=2.5,
                    max_position_value=1000.0
                )
                
                if kelly_result and kelly_result.get('recommended_size', 0) > 0:
                    print(f"   ✅ Kelly Criterion çalışıyor: ${kelly_result['recommended_size']:.2f}")
                    passed.append("Kelly criterion working")
        except Exception as kelly_err:
            print(f"   ⚠️  Kelly calculator kullanılamıyor: {kelly_err}")
            warnings.append("Kelly calculator not available")
    
    except Exception as e:
        print(f"   ❌ Risk yönetimi hatası: {e}")
        issues.append(f"Risk management error: {e}")
    
    # ==================== 7. ALFA ENGINE KONTROLÜ ====================
    print("\n🧠 7. ALFA ENGINE KONTROLÜ")
    print("-"*80)
    try:
        from src.alpha_engine import sentiment_analyzer, analyzer
        from src import config
        
        # Sentiment test
        sentiment = sentiment_analyzer.get_sentiment_scores('BTCUSDT', config)
        
        if sentiment:
            print(f"   ✅ Sentiment Analyzer çalışıyor")
            print(f"      - F&G Index: {sentiment.get('fng_index', 'N/A')}")
            print(f"      - News Sentiment: {sentiment.get('news_sentiment', 'N/A')}")
            print(f"      - Reddit Sentiment: {sentiment.get('reddit_sentiment', 'N/A')}")
            passed.append("Sentiment analysis working")
        else:
            print(f"   ⚠️  Sentiment verisi alınamadı")
            warnings.append("Sentiment data unavailable")
        
        # Quality grade test
        grade = analyzer.calculate_quality_grade('BTCUSDT', config, 'LONG')
        print(f"   ✅ Quality Grading çalışıyor: {grade}")
        passed.append("Quality grading working")
    
    except Exception as e:
        print(f"   ❌ Alfa engine hatası: {e}")
        issues.append(f"Alpha engine error: {e}")
    
    # ==================== 8. TELEGRAM KONTROLÜ ====================
    print("\n📱 8. TELEGRAM KONTROLÜ")
    print("-"*80)
    try:
        from src.notifications import telegram
        
        if "PLACEHOLDER" not in config.TELEGRAM_BOT_TOKEN:
            print(f"   ✅ Telegram bot yapılandırılmış")
            print(f"   ℹ️  Test mesajı gönderilmedi (spam önleme)")
            passed.append("Telegram configured")
        else:
            print(f"   ⚠️  Telegram token placeholder!")
            warnings.append("Telegram not configured")
    
    except Exception as e:
        print(f"   ❌ Telegram hatası: {e}")
        issues.append(f"Telegram error: {e}")
    
    # ==================== ÖZET ====================
    print("\n" + "="*80)
    print("📊 SAĞLIK KONTROLÜ ÖZETİ")
    print("="*80)
    
    total = len(passed) + len(warnings) + len(issues)
    
    print(f"\n✅ Başarılı: {len(passed)}")
    for p in passed[:5]:  # İlk 5'i göster
        print(f"   • {p}")
    if len(passed) > 5:
        print(f"   ... ve {len(passed) - 5} diğer")
    
    if warnings:
        print(f"\n⚠️  Uyarılar: {len(warnings)}")
        for w in warnings:
            print(f"   • {w}")
    
    if issues:
        print(f"\n❌ Kritik Sorunlar: {len(issues)}")
        for i in issues:
            print(f"   • {i}")
    
    # Sağlık skoru
    health_score = (len(passed) / total * 100) if total > 0 else 0
    
    print(f"\n🏥 Sistem Sağlık Skoru: {health_score:.1f}%")
    print("="*80)
    
    if health_score >= 90:
        print("🎉 SİSTEM MÜKEMMEL DURUMDA!")
        print("✅ Tüm bileşenler tam kapasite çalışıyor")
    elif health_score >= 75:
        print("✅ SİSTEM İYİ DURUMDA")
        print("⚠️  Bazı uyarılar var ama çalışabilir")
    elif health_score >= 50:
        print("⚠️  SİSTEM ORTA DURUMDA")
        print("🔧 Bazı sorunlar giderilmeli")
    else:
        print("❌ SİSTEM SORUNLU")
        print("🚨 Kritik problemler var, çalışmayabilir!")
    
    print("="*80)
    
    return len(issues) == 0

if __name__ == "__main__":
    success = comprehensive_health_check()
    sys.exit(0 if success else 1)
