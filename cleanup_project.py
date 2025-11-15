#!/usr/bin/env python3
"""
🧹 PROJE TEMİZLİK ARACI
=======================

Kullanılmayan ve bozuk dosyaları tespit eder ve siler.
Range trading sistemi için gerekli olanları korur.
"""

import os
import sys

project_root = "/Users/macbook/Desktop/ChimeraBot"

# ✅ KORUNACAK DOSYALAR - Range Trading Sistemi
keep_files = {
    # Ana range trading dosyaları
    'range_main.py',
    'range_position_monitor.py',
    'start_range_bot.sh',
    
    # Database ve yapılandırma
    'create_database.py',
    '.env',
    '.env.example',
    'requirements.txt',
    
    # Utility scripts
    'emergency_close_all_positions.py',
    'clear_range_cache.py',
    'sync_historical_trades.py',
    
    # Test scripts (range trading için)
    'test_system_validation.py',
    'test_monitor_logic.py',
    'test_position_monitor.py',
    'check_all_binance_income.py',
    'check_tonight_trades.py',
    
    # Git ve Docker
    '.gitignore',
    '.dockerignore',
    'Dockerfile',
    'docker-compose.yaml',
    'docker-entrypoint.sh',
    
    # Temel dökümantasyon
    'README.md',
}

# ✅ KORUNACAK KLASÖRLER
keep_dirs = {
    'src',
    'data',
    'logs',
    'venv',
    '.git',
    '.github',
}

# ❌ SİLİNECEK DOSYALAR - Eski AI trading bot dosyaları
delete_files = {
    # Eski AI trading bot dosyaları
    'ai_backtest.py',
    'ai_position_monitor.py',
    'ai_trading_bot.py',
    'range_trading_bot.py',  # Eski versiyon
    
    # Eski Chimera bot dosyaları
    'live_monitor.py',
    'market_scanner.py',
    'ema_proximity_alert.py',
    
    # Eski test dosyaları (AI trading için)
    'test_ai_connection.py',
    'test_ai_enhanced.py',
    'test_ai_enhancements_v12.2.py',
    'test_binance_integration.py',
    'test_binance_position_check.py',
    'test_confluence_scorer.py',
    'test_confluence_tp_sl.py',
    'test_duplicate_logic.py',
    'test_dynamic_margin.py',
    'test_gemini_integration.py',
    'test_htf_ltf_strategy.py',
    'test_hybrid_scenarios.py',
    'test_hybrid_sl_tp.py',
    'test_margin_sl.py',
    'test_scanner.py',
    'test_sl_adjustment.py',
    
    # Eski fix scriptleri
    'check_binance_orders.py',
    'check_binance_sync.py',
    'cleanup_closed_position.py',
    'emergency_close_all.py',  # Yeni versiyon var
    'emergency_stop.sh',
    'fix_corrupted_tradehistory.py',
    'fix_database_schema.py',
    'restart_bot.sh',
    'resume_trading.sh',
    'start_real_trading.sh',
    'verify_coolify_ready.sh',
    'verify_monitor_fix.py',
    
    # Eski deployment scriptleri
    'DEPLOY_GEMINI_v11.5.sh',
    
    # Test dosyası (boş)
    'test',
    
    # macOS dosyaları
    '.DS_Store',
}

# ❌ SİLİNECEK KLASÖRLER
delete_dirs = {
    'archive',
    'market_reports',
    'migrations',
    '.idea',
    'Docker',
}

# ❌ SİLİNECEK DÖKÜMANTASYON (eski sistem için)
delete_docs = {
    'AI_ENHANCEMENTS_v12.2_REPORT.md',
    'AUTOMATED_NEWS_ANALYZER_v11.7.md',
    'BINANCE_INTEGRATION_GUIDE.md',
    'BINANCE_MANUAL_CLOSE_FIX_REPORT.md',
    'COIN_NEWS_ANALYZER_GUIDE.md',
    'COOLIFY_DEPLOYMENT.md',
    'COOLIFY_DEPLOYMENT_GUIDE.md',
    'COOLIFY_READY.md',
    'CROSSOVER_FIX_v11.6.2.md',
    'DEEPSEEK_AI_REPORT.md',
    'DEPLOYMENT.md',
    'DEPLOYMENT_v11.4.0.md',
    'GEMINI_AI_GUIDE.md',
    'HYBRID_SL_TP_IMPLEMENTATION.md',
    'HYBRID_SL_TP_QUICK_REFERENCE.md',
    'LIVE_TRADING_GUIDE.md',
    'MONITORING_GUIDE.md',
    'MULTI_AI_SETUP_GUIDE.md',
    'NEWS_ANALYSIS_SUMMARY.md',
    'POSITION_MONITOR_FIX.md',
    'QUICK_START_GUIDE.md',
    'RANDOM_SCAN_ORDER_IMPLEMENTATION.md',
}

def analyze_project():
    """Proje durumunu analiz et."""
    print("="*80)
    print("🔍 PROJE ANALİZİ")
    print("="*80)
    
    all_files = set()
    for item in os.listdir(project_root):
        if os.path.isfile(os.path.join(project_root, item)):
            all_files.add(item)
    
    # Kategorize et
    to_keep = all_files & keep_files
    to_delete_files = all_files & delete_files
    to_delete_docs = all_files & delete_docs
    unknown = all_files - keep_files - delete_files - delete_docs
    
    print(f"\n📊 Dosya Dağılımı:")
    print(f"   ✅ Korunacak: {len(to_keep)}")
    print(f"   ❌ Silinecek (kod): {len(to_delete_files)}")
    print(f"   ❌ Silinecek (doc): {len(to_delete_docs)}")
    print(f"   ⚠️  Bilinmeyen: {len(unknown)}")
    
    if unknown:
        print(f"\n⚠️  Bilinmeyen dosyalar:")
        for f in sorted(unknown):
            print(f"      • {f}")
    
    return to_delete_files, to_delete_docs

def clean_project():
    """Proje temizliği yap."""
    to_delete_files, to_delete_docs = analyze_project()
    
    print("\n" + "="*80)
    print("🗑️  SİLİNECEK DOSYALAR")
    print("="*80)
    
    all_to_delete = to_delete_files | to_delete_docs | delete_dirs
    
    print(f"\n📄 Kod dosyaları ({len(to_delete_files)}):")
    for f in sorted(to_delete_files):
        print(f"   • {f}")
    
    print(f"\n📝 Dökümantasyon ({len(to_delete_docs)}):")
    for f in sorted(to_delete_docs):
        print(f"   • {f}")
    
    print(f"\n📁 Klasörler ({len(delete_dirs)}):")
    for d in sorted(delete_dirs):
        print(f"   • {d}/")
    
    print(f"\n📊 Toplam silinecek: {len(all_to_delete)} öğe")
    
    # Onay al
    print("\n" + "="*80)
    response = input("❓ Bu dosyaları silmek istediğinize emin misiniz? (yes/no): ")
    
    if response.lower() != 'yes':
        print("\n❌ İşlem iptal edildi.")
        return
    
    # Sil
    print("\n🗑️  Silme işlemi başlıyor...")
    deleted_count = 0
    error_count = 0
    
    # Dosyaları sil
    for filename in to_delete_files | to_delete_docs:
        filepath = os.path.join(project_root, filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"   ✅ Silindi: {filename}")
                deleted_count += 1
        except Exception as e:
            print(f"   ❌ Hata ({filename}): {e}")
            error_count += 1
    
    # Klasörleri sil
    import shutil
    for dirname in delete_dirs:
        dirpath = os.path.join(project_root, dirname)
        try:
            if os.path.exists(dirpath):
                shutil.rmtree(dirpath)
                print(f"   ✅ Silindi: {dirname}/")
                deleted_count += 1
        except Exception as e:
            print(f"   ❌ Hata ({dirname}/): {e}")
            error_count += 1
    
    # Özet
    print("\n" + "="*80)
    print("📊 SONUÇ")
    print("="*80)
    print(f"✅ Silinen: {deleted_count}")
    print(f"❌ Hata: {error_count}")
    
    # Kalan dosyalar
    print("\n📁 Korunan önemli dosyalar:")
    for f in sorted(keep_files):
        if os.path.exists(os.path.join(project_root, f)):
            print(f"   ✅ {f}")
    
    print("\n✅ Temizlik tamamlandı!")
    print("\n💡 Şimdi sadece Range Trading sistemi dosyaları kaldı:")
    print("   • range_main.py")
    print("   • range_position_monitor.py")
    print("   • src/ (core modules)")
    print("   • data/ (database)")
    print("   • logs/ (log files)")

if __name__ == "__main__":
    try:
        clean_project()
    except KeyboardInterrupt:
        print("\n\n⛔ İşlem iptal edildi.")
    except Exception as e:
        print(f"\n❌ Kritik hata: {e}")
        import traceback
        traceback.print_exc()
