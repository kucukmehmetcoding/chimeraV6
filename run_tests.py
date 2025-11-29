#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Çalıştırıcı
Test sisteminin ana giriş noktası
"""

import logging
import os
import sys
from datetime import datetime
from binance.client import Client

from test_manager import TestManager


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def check_binance_connection():
    """Binance bağlantısını kontrol et"""
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_SECRET_KEY', '')
    
    if not api_key or not api_secret:
        print("\n" + "="*64)
        print("⚠️  BINANCE API KEYS NOT FOUND")
        print("="*64)
        print("\nTo run backtest with real data, you need:")
        print("1. Create a .env file in project root")
        print("2. Add these lines:")
        print("   BINANCE_API_KEY=your_api_key_here")
        print("   BINANCE_SECRET_KEY=your_api_secret_here")
        print("\nNote: Read-only API keys are sufficient for backtesting")
        print("="*64 + "\n")
        
        return None
    
    try:
        client = Client(api_key, api_secret)
        # Test connection
        client.ping()
        
        print("\n" + "="*64)
        print("✅ BINANCE CONNECTION SUCCESSFUL")
        print("="*64 + "\n")
        
        return client
        
    except Exception as e:
        print(f"\n❌ Binance connection failed: {e}\n")
        return None


def print_menu():
    """Ana menüyü yazdır"""
    print("\n" + "╔" + "═"*62 + "╗")
    print("║" + " "*15 + "🤖 AI TRADING TEST SUITE" + " "*24 + "║")
    print("╚" + "═"*62 + "╝\n")
    
    print("📊 TEST MODES:")
    print("  1️⃣  Quick Backtest (7 days, 2 symbols)")
    print("  2️⃣  Full Backtest (30 days, 5 symbols)")
    print("  3️⃣  Strategy Analysis (Compare 3 strategies)")
    print("  4️⃣  Custom Backtest (Choose parameters)")
    print("  5️⃣  Comprehensive Test Suite (All tests)")
    print("  6️⃣  View Previous Test Results")
    print("  0️⃣  Exit")
    print("\n" + "─"*64)


def run_quick_backtest(test_manager):
    """Hızlı backtest (7 gün, 2 sembol)"""
    print("\n" + "═"*64)
    print("🚀 QUICK BACKTEST (7 days)")
    print("═"*64 + "\n")
    
    symbols = ['BTCUSDT', 'ETHUSDT']
    days = 7
    mode = 'conservative'
    
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Days: {days}")
    print(f"Mode: {mode}\n")
    
    report = test_manager.run_backtest(
        symbols=symbols,
        days=days,
        mode=mode
    )
    
    # Özet göster
    test_manager.print_test_summary()


def run_full_backtest(test_manager):
    """Full backtest (30 gün, 5 sembol)"""
    print("\n" + "═"*64)
    print("🎯 FULL BACKTEST (30 days)")
    print("═"*64 + "\n")
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
    days = 30
    mode = 'moderate'
    
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Days: {days}")
    print(f"Mode: {mode}\n")
    
    confirm = input("⚠️  This may take 10-15 minutes. Continue? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        return
    
    report = test_manager.run_backtest(
        symbols=symbols,
        days=days,
        mode=mode
    )
    
    # Özet göster
    test_manager.print_test_summary()


def run_strategy_analysis(test_manager):
    """Strateji analizi"""
    print("\n" + "═"*64)
    print("📊 STRATEGY ANALYSIS")
    print("═"*64 + "\n")
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    days = 7
    
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Days: {days} per strategy")
    print("Strategies: Aggressive, Moderate, Conservative\n")
    
    confirm = input("⚠️  This will run 3 backtests. Continue? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        return
    
    results = test_manager.run_strategy_analysis(
        symbols=symbols,
        days=days
    )
    
    print("\n✅ Strategy analysis complete!")


def run_custom_backtest(test_manager):
    """Özel parametrelerle backtest"""
    print("\n" + "═"*64)
    print("⚙️  CUSTOM BACKTEST")
    print("═"*64 + "\n")
    
    # Sembol seçimi
    print("Available symbols: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT, DOTUSDT, LINKUSDT, AVAXUSDT")
    symbols_input = input("Enter symbols (comma-separated, e.g. BTCUSDT,ETHUSDT): ").strip()
    
    if not symbols_input:
        symbols = ['BTCUSDT', 'ETHUSDT']
    else:
        symbols = [s.strip().upper() for s in symbols_input.split(',')]
    
    # Gün sayısı
    days_input = input("Enter days (1-90, default: 7): ").strip()
    try:
        days = int(days_input) if days_input else 7
        days = max(1, min(days, 90))  # 1-90 arası
    except:
        days = 7
    
    # Mod seçimi
    print("\nModes:")
    print("  1. Aggressive (more signals, lower quality)")
    print("  2. Moderate (balanced)")
    print("  3. Conservative (fewer signals, higher quality)")
    mode_choice = input("Select mode (1-3, default: 2): ").strip()
    
    mode_map = {'1': 'aggressive', '2': 'moderate', '3': 'conservative'}
    mode = mode_map.get(mode_choice, 'moderate')
    
    print(f"\n📋 Configuration:")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Days: {days}")
    print(f"  Mode: {mode}\n")
    
    confirm = input("Start backtest? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        return
    
    report = test_manager.run_backtest(
        symbols=symbols,
        days=days,
        mode=mode
    )
    
    # Özet göster
    test_manager.print_test_summary()


def run_comprehensive_test(test_manager):
    """Kapsamlı test suite"""
    print("\n" + "═"*64)
    print("🧪 COMPREHENSIVE TEST SUITE")
    print("═"*64 + "\n")
    
    print("This will run:")
    print("  1. Quick backtest (7 days)")
    print("  2. Strategy analysis (3 strategies)")
    print("  3. Performance comparison")
    print("\nEstimated time: 15-20 minutes\n")
    
    confirm = input("Continue? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        return
    
    # 1. Quick backtest
    print("\n" + "─"*64)
    print("STEP 1/3: Quick Backtest")
    print("─"*64)
    run_quick_backtest(test_manager)
    
    # 2. Strategy analysis
    print("\n" + "─"*64)
    print("STEP 2/3: Strategy Analysis")
    print("─"*64)
    run_strategy_analysis(test_manager)
    
    # 3. Final report
    print("\n" + "─"*64)
    print("STEP 3/3: Final Report")
    print("─"*64)
    test_manager.print_test_summary()
    
    print("\n" + "╔" + "═"*62 + "╗")
    print("║" + " "*15 + "🎉 TEST SUITE COMPLETE!" + " "*24 + "║")
    print("╚" + "═"*62 + "╝\n")


def view_previous_results(test_manager):
    """Önceki test sonuçlarını görüntüle"""
    print("\n" + "═"*64)
    print("📜 PREVIOUS TEST RESULTS")
    print("═"*64 + "\n")
    
    import sqlite3
    conn = test_manager.db.get_connection()
    cursor = conn.cursor()
    
    # Tüm test performance kayıtlarını al
    cursor.execute("""
        SELECT test_id, test_mode, start_time, total_trades, 
               total_pnl, total_pnl_pct, win_rate, max_drawdown_pct
        FROM test_performance
        ORDER BY start_time DESC
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        print("No previous test results found.\n")
        return
    
    print(f"{'Test ID':<30} {'Mode':<12} {'Trades':<8} {'PnL %':<10} {'Win Rate':<10}")
    print("─"*64)
    
    for row in results:
        test_id = row['test_id'][:28]  # Truncate
        mode = row['test_mode']
        trades = row['total_trades']
        pnl_pct = row['total_pnl_pct']
        win_rate = row['win_rate']
        
        pnl_symbol = "🟢" if pnl_pct > 0 else "🔴"
        print(f"{test_id:<30} {mode:<12} {trades:<8} {pnl_symbol}{pnl_pct:>7.2f}%  {win_rate:>6.1f}%")
    
    print("\n" + "─"*64)
    
    # Detay görüntüleme
    view_detail = input("\nView details for a test? Enter test_id (or press Enter to skip): ").strip()
    if view_detail:
        test_manager.print_test_summary(view_detail)


def main():
    """Ana fonksiyon"""
    print("\n" + "╔" + "═"*62 + "╗")
    print("║" + " "*10 + "AI TRADING SYSTEM - TEST RUNNER" + " "*19 + "║")
    print("╚" + "═"*62 + "╝")
    
    # Binance bağlantısını kontrol et
    client = check_binance_connection()
    
    if not client:
        print("⚠️  Continuing without Binance connection...")
        print("   Some features may not work correctly.\n")
        
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Exiting...")
            return
    
    # Test manager'ı başlat
    try:
        test_manager = TestManager(binance_client=client)
    except Exception as e:
        print(f"\n❌ Error initializing TestManager: {e}")
        logger.error(f"TestManager initialization error: {e}", exc_info=True)
        return
    
    # Ana döngü
    while True:
        try:
            print_menu()
            choice = input("Select option (0-6): ").strip()
            
            if choice == '0':
                print("\n👋 Goodbye!")
                break
                
            elif choice == '1':
                run_quick_backtest(test_manager)
                
            elif choice == '2':
                run_full_backtest(test_manager)
                
            elif choice == '3':
                run_strategy_analysis(test_manager)
                
            elif choice == '4':
                run_custom_backtest(test_manager)
                
            elif choice == '5':
                run_comprehensive_test(test_manager)
                
            elif choice == '6':
                view_previous_results(test_manager)
                
            else:
                print("❌ Invalid choice! Please select 0-6.")
            
            # Devam etmek ister mi?
            if choice in ['1', '2', '3', '4', '5']:
                input("\nPress Enter to continue...")
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.error(f"Main loop error: {e}", exc_info=True)
            input("Press Enter to continue...")


if __name__ == "__main__":
    # Logs klasörünü oluştur
    os.makedirs('logs', exist_ok=True)
    
    # Programı çalıştır
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
