#!/usr/bin/env python3
"""
Fibonacci Bot - Ana Orchestrator
5 dakikalık döngüde Fibonacci retracement tabanlı spot alım botu
"""

import logging
import time
import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database import FibonacciDatabase
from scanner import FibonacciScanner
from calculator import FibonacciCalculator
from entry_manager import EntryManager
from exit_manager import ExitManager
from portfolio_manager import PortfolioManager

# Config'den parametreleri al
from src.config import (
    FIBONACCI_MAX_COINS,
    FIBONACCI_BUDGET_PER_COIN,
    FIBONACCI_TOTAL_BUDGET,
    FIBONACCI_SCAN_INTERVAL_MINUTES,
    FIBONACCI_DROP_THRESHOLD,
    FIBONACCI_MIN_VOLUME,
    FIBONACCI_LOOKBACK_DAYS,
    FIBONACCI_ADX_THRESHOLD
)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../logs/fibonacci_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('fibonacci_bot.main')


class FibonacciBot:
    """Ana Fibonacci bot orchestrator"""
    
    def __init__(
        self,
        scan_interval_minutes: int = 5,
        max_total_budget: float = 1000.0,
        max_budget_per_coin: float = 100.0,
        lookback_days: int = 90,
        adx_threshold: float = 40.0
    ):
        """
        Args:
            scan_interval_minutes: Tarama döngüsü aralığı (dakika)
            max_total_budget: Maksimum toplam bütçe (USD)
            max_budget_per_coin: Coin başına maksimum bütçe (USD)
            lookback_days: Fibonacci hesabı için geriye bakış (gün)
            adx_threshold: ADX eşiği (üstündeki coinler atlanır)
        """
        self.scan_interval = scan_interval_minutes * 60  # Saniyeye çevir
        self.max_total_budget = max_total_budget
        self.max_budget_per_coin = max_budget_per_coin
        
        # Modülleri başlat
        logger.info("🚀 Fibonacci Bot başlatılıyor...")
        
        self.db = FibonacciDatabase()
        logger.info("✅ Database bağlantısı kuruldu")
        
        try:
            self.scanner = FibonacciScanner(
                drop_threshold=FIBONACCI_DROP_THRESHOLD,
                min_volume_usdt=FIBONACCI_MIN_VOLUME,
                top_n=FIBONACCI_MAX_COINS  # Max coin sayısı kadar seç
            )
            logger.info("✅ Scanner hazır")
        except Exception as e:
            logger.error(f"❌ Scanner başlatılamadı: {e}")
            logger.error("İnternet bağlantınızı kontrol edin veya daha sonra tekrar deneyin.")
            raise
        
        self.calculator = FibonacciCalculator(
            lookback_days=lookback_days,
            adx_threshold=adx_threshold
        )
        logger.info(f"✅ Calculator hazır (Lookback: {lookback_days} gün, ADX: {adx_threshold})")
        
        self.entry_manager = EntryManager(self.db)
        logger.info("✅ Entry Manager hazır")
        
        self.exit_manager = ExitManager(self.db)
        logger.info("✅ Exit Manager hazır")
        
        self.portfolio = PortfolioManager(
            self.db,
            max_total_budget=max_total_budget,
            max_budget_per_coin=max_budget_per_coin
        )
        logger.info(f"✅ Portfolio Manager hazır (Total: ${max_total_budget}, Per Coin: ${max_budget_per_coin})")
        
        logger.info("="*60)
        logger.info("🎯 FİBONACCI BOT HAZIR!")
        logger.info("="*60)
    
    def scan_and_calculate_fibonacci(self) -> dict:
        """1. Adım: Market taraması ve Fibonacci hesaplaması"""
        logger.info("\n" + "="*60)
        logger.info("📊 ADIM 1: MARKET TARAMASI VE FİBONACCI HESAPLAMA")
        logger.info("="*60)
        
        # 1. Düşüş yapan coinleri tara
        losers = self.scanner.scan_losers()
        
        if not losers:
            logger.warning("⚠️ Düşüş yapan coin bulunamadı")
            return {}
        
        symbols = [coin['symbol'] for coin in losers]
        logger.info(f"✅ {len(symbols)} coin tarandı")
        
        # 2. Her coin için Fibonacci seviyeleri hesapla
        fib_results = self.calculator.analyze_multiple_coins(symbols)
        
        if not fib_results:
            logger.warning("⚠️ Fibonacci hesaplaması yapılamadı")
            return {}
        
        # 3. Fibonacci seviyelerini veritabanına kaydet
        for symbol, data in fib_results.items():
            self.db.save_fibonacci_levels(symbol, data)
        
        logger.info(f"✅ {len(fib_results)} coin için Fibonacci seviyeleri kaydedildi")
        
        return fib_results
    
    def check_entry_signals(self, fib_results: dict):
        """2. Adım: Giriş sinyali kontrolü"""
        logger.info("\n" + "="*60)
        logger.info("🔍 ADIM 2: GİRİŞ SİNYALİ KONTROLÜ")
        logger.info("="*60)
        
        all_signals = []
        
        for symbol, fib_data in fib_results.items():
            # Portfolio risk kontrolü
            can_open, msg = self.portfolio.can_open_position(symbol, self.max_budget_per_coin)
            
            if not can_open:
                logger.warning(f"⚠️ {symbol}: {msg}")
                continue
            
            # Entry sinyallerini kontrol et
            signals = self.entry_manager.check_entry_signals(
                symbol, 
                fib_data, 
                max_budget_per_coin=self.max_budget_per_coin
            )
            
            all_signals.extend(signals)
        
        logger.info(f"\n✅ Toplam {len(all_signals)} giriş sinyali bulundu")
        
        return all_signals
    
    def execute_entries(self, signals: list) -> int:
        """3. Adım: Giriş sinyallerini uygula"""
        logger.info("\n" + "="*60)
        logger.info("💰 ADIM 3: GİRİŞ SİNYALLERİ UYGULAMASI")
        logger.info("="*60)
        
        executed = 0
        
        for signal in signals:
            # Son bir kez risk kontrolü
            can_open, msg = self.portfolio.can_open_position(
                signal['symbol'], 
                signal['budget']
            )
            
            if not can_open:
                logger.warning(f"⚠️ {signal['symbol']}: {msg} - Atlanıyor")
                continue
            
            # Giriş yap
            if self.entry_manager.execute_entry(signal):
                executed += 1
        
        logger.info(f"\n✅ {executed} / {len(signals)} giriş gerçekleşti")
        
        return executed
    
    def monitor_exits(self):
        """4. Adım: Çıkış sinyallerini kontrol et ve uygula"""
        logger.info("\n" + "="*60)
        logger.info("📈 ADIM 4: ÇIKIŞ SİNYALİ KONTROLÜ")
        logger.info("="*60)
        
        # Çıkış sinyallerini kontrol et
        exit_signals = self.exit_manager.monitor_positions()
        
        if not exit_signals:
            logger.info("⏸️ Çıkış sinyali yok")
            return 0
        
        # Çıkışları uygula
        executed = self.exit_manager.execute_exit_signals(exit_signals)
        
        logger.info(f"✅ {executed} / {len(exit_signals)} çıkış gerçekleşti")
        
        return executed
    
    def run_cycle(self):
        """Tek bir döngü iterasyonu"""
        try:
            logger.info("\n\n" + "="*80)
            logger.info(f"🔄 YENİ DÖNGÜ BAŞLADI - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*80)
            
            # Portföy durumunu göster
            self.portfolio.log_portfolio_status()
            
            # 1. Market tara + Fibonacci hesapla
            fib_results = self.scan_and_calculate_fibonacci()
            
            # 2. Giriş sinyallerini kontrol et
            if fib_results:
                entry_signals = self.check_entry_signals(fib_results)
                
                # 3. Giriş sinyallerini uygula
                if entry_signals:
                    self.execute_entries(entry_signals)
            
            # 4. Çıkış sinyallerini kontrol et ve uygula
            self.monitor_exits()
            
            # Portföy durumunu tekrar göster
            self.portfolio.log_portfolio_status()
            
            # İstatistikler
            self.portfolio.log_statistics()
            
            logger.info("\n" + "="*80)
            logger.info(f"✅ DÖNGÜ TAMAMLANDI - Sonraki döngü {self.scan_interval // 60} dakika sonra")
            logger.info("="*80 + "\n")
            
        except Exception as e:
            logger.error(f"❌ Döngü hatası: {e}", exc_info=True)
    
    def run(self):
        """Ana döngüyü başlat"""
        logger.info("\n" + "="*80)
        logger.info("🚀 FİBONACCI BOT ÇALIŞMAYA BAŞLADI")
        logger.info(f"   Döngü Aralığı: {self.scan_interval // 60} dakika")
        logger.info(f"   Maksimum Bütçe: ${self.max_total_budget}")
        logger.info(f"   Coin Başına: ${self.max_budget_per_coin}")
        logger.info("="*80)
        
        try:
            while True:
                self.run_cycle()
                
                logger.info(f"😴 {self.scan_interval // 60} dakika bekleniyor...\n")
                time.sleep(self.scan_interval)
                
        except KeyboardInterrupt:
            logger.info("\n\n" + "="*80)
            logger.info("🛑 FIBONACCI BOT DURDURULDU (Kullanıcı)")
            logger.info("="*80)
        
        except Exception as e:
            logger.error(f"\n\n❌ FIBONACCI BOT KRITIK HATA: {e}", exc_info=True)
            logger.info("="*80)
            logger.info("🛑 BOT DURDU")
            logger.info("="*80)


if __name__ == "__main__":
    """Bot'u başlat"""
    
    # Konfigürasyon (.env dosyasından alınıyor)
    print("\n" + "="*80)
    print("🎯 FİBONACCI BOT KONFIGÜRASYONU (.env)")
    print("="*80)
    print(f"  Maksimum Coin Sayısı: {FIBONACCI_MAX_COINS}")
    print(f"  Coin Başına Bütçe: ${FIBONACCI_BUDGET_PER_COIN}")
    print(f"  Toplam Bütçe: ${FIBONACCI_TOTAL_BUDGET}")
    print(f"  Tarama Aralığı: {FIBONACCI_SCAN_INTERVAL_MINUTES} dakika")
    print(f"  Düşüş Eşiği: {FIBONACCI_DROP_THRESHOLD}%")
    print(f"  Min Hacim: ${FIBONACCI_MIN_VOLUME:,.0f}")
    print(f"  Lookback: {FIBONACCI_LOOKBACK_DAYS} gün")
    print(f"  ADX Threshold: {FIBONACCI_ADX_THRESHOLD}")
    print("="*80 + "\n")
    
    bot = FibonacciBot(
        scan_interval_minutes=FIBONACCI_SCAN_INTERVAL_MINUTES,
        max_total_budget=FIBONACCI_TOTAL_BUDGET,
        max_budget_per_coin=FIBONACCI_BUDGET_PER_COIN,
        lookback_days=FIBONACCI_LOOKBACK_DAYS,
        adx_threshold=FIBONACCI_ADX_THRESHOLD
    )
    
    # Çalıştır
    bot.run()
