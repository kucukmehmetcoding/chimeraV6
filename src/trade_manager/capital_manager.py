# src/trade_manager/capital_manager.py

"""
Sermaye Yönetimi Modülü
- Devre Kesici (Circuit Breaker): Maksimum zarar limitini kontrol eder
- Kâr Realizasyonu: Belirli kâr hedeflerine ulaşıldığında kârı Spot'a transfer eder
"""

import logging
from typing import Optional
from threading import Event

logger = logging.getLogger(__name__)


class CapitalManager:
    """
    Sermaye yönetimi ve risk kontrolü sınıfı.
    """
    
    def __init__(self, config_module, executor, stop_event: Event):
        """
        Args:
            config_module: src.config modülü
            executor: BinanceFuturesExecutor instance
            stop_event: Threading.Event (bot'u durdurmak için)
        """
        self.config = config_module
        self.executor = executor
        self.stop_event = stop_event
        
        # Config'den ayarları al
        self.starting_capital = float(getattr(config_module, 'VIRTUAL_PORTFOLIO_USD', 200.0))
        self.max_drawdown_percent = float(getattr(config_module, 'MAX_DRAWDOWN_PERCENT', -50.0))
        self.profit_target_percent = float(getattr(config_module, 'PROFIT_TARGET_PERCENT', 50.0))
        self.auto_close_on_breaker = getattr(config_module, 'AUTO_CLOSE_ON_CIRCUIT_BREAKER', False)
        self.auto_transfer_profit = getattr(config_module, 'AUTO_TRANSFER_PROFIT', False)
        
        logger.info(f"💰 Capital Manager başlatıldı:")
        logger.info(f"   Başlangıç Sermaye: ${self.starting_capital:.2f}")
        logger.info(f"   Maks Zarar Limiti: {self.max_drawdown_percent}%")
        logger.info(f"   Kâr Hedefi: {self.profit_target_percent}%")
        logger.info(f"   Otomatik Kapatma: {self.auto_close_on_breaker}")
        logger.info(f"   Otomatik Transfer: {self.auto_transfer_profit}")
    
    def check_capital(self):
        """
        Ana sermaye kontrolü fonksiyonu.
        Saatte bir çağrılır (schedule.every(1).hour.do()).
        """
        logger.info("=" * 60)
        logger.info("📊 SERMAYE KONTROLÜ BAŞLADI")
        logger.info("=" * 60)
        
        try:
            # 1. Mevcut bakiyeyi al
            current_balance = self.executor.get_futures_account_balance()
            
            if current_balance is None or current_balance == 0:
                logger.warning("⚠️ Futures bakiyesi 0 veya alınamadı. Kontrol atlanıyor.")
                return
            
            # 2. PnL hesapla
            pnl = current_balance - self.starting_capital
            pnl_percent = (pnl / self.starting_capital) * 100 if self.starting_capital > 0 else 0
            
            logger.info(f"💵 Mevcut Bakiye: ${current_balance:.2f}")
            logger.info(f"💵 Başlangıç Sermaye: ${self.starting_capital:.2f}")
            logger.info(f"📈 PnL: ${pnl:.2f} ({pnl_percent:+.2f}%)")
            
            # 3. Risk Kontrolü (Devre Kesici)
            self._check_circuit_breaker(current_balance, pnl_percent)
            
            # 4. Kâr Kontrolü (Kâr Realizasyonu)
            self._check_profit_target(current_balance, pnl, pnl_percent)
            
            logger.info("=" * 60)
            logger.info("✅ SERMAYE KONTROLÜ TAMAMLANDI")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Sermaye kontrolü sırasında hata: {e}", exc_info=True)
    
    def _check_circuit_breaker(self, current_balance: float, pnl_percent: float):
        """
        Devre kesici kontrolü.
        Maksimum zarar limitini aşarsa sistemi durdurur.
        """
        if pnl_percent <= self.max_drawdown_percent:
            # KRİTİK DURUM!
            logger.critical("🚨" * 20)
            logger.critical(f"🚨 DEVRE KESİCİ AKTİF!")
            logger.critical(f"🚨 Toplam Zarar: {pnl_percent:.2f}%")
            logger.critical(f"🚨 Limit: {self.max_drawdown_percent}%")
            logger.critical(f"🚨 Mevcut Bakiye: ${current_balance:.2f}")
            logger.critical("🚨" * 20)
            
            # Telegram bildirimi gönder
            self._send_circuit_breaker_alert(current_balance, pnl_percent)
            
            # Sistemi durdur
            logger.critical("⛔ SİSTEM DURDURULUYOR...")
            self.stop_event.set()
            
            # Otomatik kapatma (TEHLİKELİ!)
            if self.auto_close_on_breaker:
                logger.critical("⚠️ OTOMATİK KAPATMA AKTİF - TÜM POZİSYONLAR KAPATILIYOR!")
                self._emergency_close_all_positions()
            else:
                logger.critical("ℹ️ Otomatik kapatma kapalı. Lütfen pozisyonları MANUEL kontrol edin!")
    
    def _check_profit_target(self, current_balance: float, pnl: float, pnl_percent: float):
        """
        Kâr hedefi kontrolü.
        Belirli kâr yüzdesine ulaşıldığında kârı Spot'a transfer eder.
        """
        if pnl_percent >= self.profit_target_percent:
            logger.info("🎯" * 20)
            logger.info(f"🎯 KÂR HEDEFİNE ULAŞILDI!")
            logger.info(f"🎯 Kâr: ${pnl:.2f} ({pnl_percent:+.2f}%)")
            logger.info(f"🎯 Hedef: {self.profit_target_percent}%")
            logger.info("🎯" * 20)
            
            # Telegram bildirimi
            self._send_profit_target_alert(current_balance, pnl, pnl_percent)
            
            # Otomatik transfer
            if self.auto_transfer_profit:
                logger.info("💸 OTOMATİK TRANSFER AKTİF - Kâr Spot'a aktarılıyor...")
                self._transfer_profit_to_spot(pnl, current_balance)
            else:
                logger.info("ℹ️ Otomatik transfer kapalı. Kârı manuel çekmek için Binance'e gidin.")
    
    def _send_circuit_breaker_alert(self, current_balance: float, pnl_percent: float):
        """Devre kesici Telegram bildirimi."""
        try:
            from src.notifications import telegram as telegram_notifier
            from src.notifications.telegram import escape_markdown_v2
            
            # Açık pozisyonları al
            open_positions = self.executor.get_open_positions_from_binance()
            
            message = f"*🚨 KRİTİK RİSK UYARISI 🚨*\n\n"
            message += f"*DEVRE KESİCİ AKTİF\\!*\n\n"
            message += f"*{escape_markdown_v2('-')} Toplam Zarar:* {escape_markdown_v2(f'{pnl_percent:.2f}%')}\n"
            message += f"*{escape_markdown_v2('-')} Limit:* {escape_markdown_v2(f'{self.max_drawdown_percent}%')}\n"
            message += f"*{escape_markdown_v2('-')} Mevcut Bakiye:* {escape_markdown_v2(f'${current_balance:.2f}')}\n"
            message += f"*{escape_markdown_v2('-')} Açık Pozisyon:* {escape_markdown_v2(str(len(open_positions)))}\n\n"
            message += f"*⛔ SİSTEM DURDURULDU\\!*\n\n"
            
            if self.auto_close_on_breaker:
                message += f"*⚠️ Tüm pozisyonlar otomatik kapatılıyor\\!*"
            else:
                message += f"*ℹ️ Lütfen pozisyonları MANUEL kontrol edin\\!*\n\n"
                message += f"*Öneriler:*\n"
                message += f"{escape_markdown_v2('1.')} Binance'e giriş yapın\n"
                message += f"{escape_markdown_v2('2.')} Açık pozisyonları inceleyin\n"
                message += f"{escape_markdown_v2('3.')} Zarar durdur ayarlarını kontrol edin"
            
            telegram_notifier.send_message(message)
            logger.info("✅ Telegram bildirimi gönderildi")
            
        except Exception as e:
            logger.error(f"❌ Telegram bildirimi gönderilemedi: {e}", exc_info=True)
    
    def _send_profit_target_alert(self, current_balance: float, pnl: float, pnl_percent: float):
        """Kâr hedefi Telegram bildirimi."""
        try:
            from src.notifications import telegram as telegram_notifier
            from src.notifications.telegram import escape_markdown_v2
            
            message = f"*🎯 KÂR HEDEFİNE ULAŞILDI 🎯*\n\n"
            message += f"*{escape_markdown_v2('-')} Kâr:* {escape_markdown_v2(f'${pnl:.2f}')} \\({escape_markdown_v2(f'{pnl_percent:+.2f}%')}\\)\n"
            message += f"*{escape_markdown_v2('-')} Hedef:* {escape_markdown_v2(f'{self.profit_target_percent}%')}\n"
            message += f"*{escape_markdown_v2('-')} Mevcut Bakiye:* {escape_markdown_v2(f'${current_balance:.2f}')}\n\n"
            
            if self.auto_transfer_profit:
                message += f"*💸 Kâr otomatik olarak Spot cüzdana aktarılıyor\\!*"
            else:
                message += f"*ℹ️ Kârı manuel çekmek için:*\n"
                message += f"{escape_markdown_v2('1.')} Binance {escape_markdown_v2('>')} Wallet\n"
                message += f"{escape_markdown_v2('2.')} Transfer {escape_markdown_v2('>')} Futures to Spot\n"
                message += f"{escape_markdown_v2('3.')} Miktar: {escape_markdown_v2(f'${pnl:.2f}')}"
            
            telegram_notifier.send_message(message)
            logger.info("✅ Telegram bildirimi gönderildi")
            
        except Exception as e:
            logger.error(f"❌ Telegram bildirimi gönderilemedi: {e}", exc_info=True)
    
    def _emergency_close_all_positions(self):
        """
        ACİL DURUM: Tüm açık pozisyonları piyasa fiyatından kapatır.
        ⚠️ TEHLİKELİ - Sadece kritik durumlarda kullanılır!
        """
        logger.warning("⚠️ ACİL KAPATMA BAŞLADI...")
        
        try:
            positions = self.executor.get_open_positions_from_binance()
            
            if not positions:
                logger.info("ℹ️ Kapatılacak açık pozisyon yok")
                return
            
            for pos in positions:
                symbol = pos['symbol']
                position_amt = float(pos['positionAmt'])
                
                if position_amt == 0:
                    continue
                
                try:
                    logger.warning(f"⚠️ {symbol} kapatılıyor (Miktar: {position_amt})...")
                    # NOT: close_position_market fonksiyonu henüz yazılmadı
                    # Adım 3'te eklenecek
                    logger.warning(f"⚠️ {symbol} kapatma kodu henüz implement edilmedi!")
                    
                except Exception as e:
                    logger.error(f"❌ {symbol} kapatılamadı: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"❌ Acil kapatma hatası: {e}", exc_info=True)
    
    def _transfer_profit_to_spot(self, profit_amount: float, current_balance: float):
        """
        Kârı Futures'tan Spot cüzdana transfer eder.
        ⚠️ Bu fonksiyon Adım 3'te implement edilecek
        """
        logger.warning("⚠️ Otomatik transfer fonksiyonu henüz implement edilmedi!")
        logger.info(f"ℹ️ Transfer edilecek miktar: ${profit_amount:.2f}")
        logger.info(f"ℹ️ Kalan bakiye: ${current_balance - profit_amount:.2f}")
        
        # TODO: Adım 3'te eklenecek
        # self.executor.transfer_futures_to_spot(profit_amount)


# --- Yardımcı Fonksiyonlar ---
def initialize_capital_manager(config_module, executor, stop_event: Event) -> CapitalManager:
    """
    Capital Manager'ı başlatır.
    
    Args:
        config_module: src.config modülü
        executor: BinanceFuturesExecutor instance
        stop_event: Threading.Event
    
    Returns:
        CapitalManager instance
    """
    logger.info("🏦 Capital Manager başlatılıyor...")
    return CapitalManager(config_module, executor, stop_event)


# --- Test Bloğu ---
if __name__ == '__main__':
    import sys
    import os
    from threading import Event
    
    # Config'i import et
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, project_root)
    
    from src import config
    from src.trade_manager.executor import initialize_executor
    
    # Loglama ayarla
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s'
    )
    
    print("=" * 60)
    print("CAPITAL MANAGER TEST")
    print("=" * 60)
    
    try:
        # Mock stop event
        stop_event = Event()
        
        # Executor'ı başlat
        executor = initialize_executor(config)
        
        # Capital Manager'ı başlat
        capital_mgr = initialize_capital_manager(config, executor, stop_event)
        
        # Test kontrolü
        print("\n🔍 Sermaye kontrolü yapılıyor...\n")
        capital_mgr.check_capital()
        
        print("\n" + "=" * 60)
        print("✅ TEST TAMAMLANDI!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST HATASI: {e}")
        import traceback
        traceback.print_exc()
