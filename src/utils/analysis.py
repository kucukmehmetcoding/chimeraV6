# src/utils/analysis.py

import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional

# Proje kök dizinini path'e ekle (config'i bulabilmek için)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# Loglamayı ayarla (opsiyonel, ana betikten alabilir)
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')

# Config'i import etmeye çalış (dosya yolu için)
try:
    from src import config
except ImportError:
    logger.error("analysis.py: config.py import edilemedi. Varsayılan dosya yolları kullanılacak.")
    config = None # Config yoksa None olarak işaretle


def calculate_performance_metrics(trade_history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Verilen işlem geçmişi listesinden performans metriklerini hesaplar.

    Args:
        trade_history (List[Dict[str, Any]]): Kapanan işlemlerin listesi.

    Returns:
        Optional[Dict[str, Any]]: Hesaplanan metrikleri içeren bir sözlük veya
                                    hesaplama yapılamazsa None.
    """
    if not trade_history:
        logger.warning("Hesaplanacak işlem geçmişi bulunamadı.")
        return None

    total_trades = len(trade_history)
    winning_trades = 0
    losing_trades = 0
    breakeven_trades = 0 # PnL tam 0 olanlar

    total_pnl_usd = Decimal('0.0')
    total_gains_usd = Decimal('0.0')
    total_losses_usd = Decimal('0.0')
    total_duration_seconds = 0
    valid_duration_trades = 0

    # PnL'i Decimal olarak işlemek için
    zero = Decimal('0.00') # Karşılaştırma için

    for trade in trade_history:
        try:
            # pnl_usd değerini al ve Decimal'a çevir
            pnl_str = str(trade.get('pnl_usd', '0.0')) # None ise veya yoksa '0.0'
            pnl = Decimal(pnl_str).quantize(Decimal('0.01'), ROUND_HALF_UP)
        except (InvalidOperation, TypeError):
            logger.warning(f"Geçersiz pnl_usd değeri ({trade.get('pnl_usd')}) işlemde bulundu ({trade.get('symbol')}), PnL hesaplamasında 0 olarak kabul ediliyor.")
            pnl = zero

        total_pnl_usd += pnl

        if pnl > zero:
            winning_trades += 1
            total_gains_usd += pnl
        elif pnl < zero:
            losing_trades += 1
            total_losses_usd += pnl # Negatif olduğu için direkt ekliyoruz
        else:
            breakeven_trades += 1

        # İşlem süresini hesapla (eğer zaman bilgisi varsa)
        open_time = trade.get('open_time')
        close_time = trade.get('close_time')
        if open_time and close_time:
            try:
                duration = float(close_time) - float(open_time)
                if duration >= 0:
                    total_duration_seconds += duration
                    valid_duration_trades += 1
            except (ValueError, TypeError):
                pass # Zaman damgası geçersizse atla

    # Türetilmiş Metrikleri Hesapla
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    profit_factor = (total_gains_usd / abs(total_losses_usd)) if total_losses_usd != zero else float('inf') # Kayıp yoksa sonsuz
    avg_win_usd = (total_gains_usd / winning_trades) if winning_trades > 0 else zero
    avg_loss_usd = (total_losses_usd / losing_trades) if losing_trades > 0 else zero
    avg_reward_risk = (avg_win_usd / abs(avg_loss_usd)) if avg_loss_usd != zero else float('inf')
    avg_trade_duration_hours = (total_duration_seconds / valid_duration_trades / 3600) if valid_duration_trades > 0 else 0

    metrics = {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "breakeven_trades": breakeven_trades,
        "win_rate_percent": round(win_rate, 2),
        "total_pnl_usd": round(float(total_pnl_usd), 2), # Raporlama için float'a çevir
        "total_gains_usd": round(float(total_gains_usd), 2),
        "total_losses_usd": round(float(total_losses_usd), 2),
        "profit_factor": round(float(profit_factor), 2) if profit_factor != float('inf') else "∞",
        "average_win_usd": round(float(avg_win_usd), 2),
        "average_loss_usd": round(float(avg_loss_usd), 2),
        "average_reward_risk_ratio": round(float(avg_reward_risk), 2) if avg_reward_risk != float('inf') else "∞",
        "average_trade_duration_hours": round(avg_trade_duration_hours, 2),
    }

    return metrics

def display_metrics(metrics: Dict[str, Any]):
    """Hesaplanan metrikleri konsola yazdırır."""
    if not metrics:
        print("\nGörüntülenecek performans metriği yok.")
        return

    print("\n--- Performans Metrikleri ---")
    print(f"Toplam İşlem Sayısı:        {metrics['total_trades']}")
    print(f"Kazanan İşlem Sayısı:       {metrics['winning_trades']}")
    print(f"Kaybeden İşlem Sayısı:      {metrics['losing_trades']}")
    print(f"Başa Baş İşlem Sayısı:      {metrics['breakeven_trades']}")
    print("-" * 30)
    print(f"Kazanma Oranı (%):          {metrics['win_rate_percent']}%")
    print(f"Toplam PnL (USD):           {metrics['total_pnl_usd']:.2f} USD")
    print(f"Toplam Kazanç (USD):        {metrics['total_gains_usd']:.2f} USD")
    print(f"Toplam Kayıp (USD):         {metrics['total_losses_usd']:.2f} USD")
    print(f"Kar Faktörü:                {metrics['profit_factor']}")
    print("-" * 30)
    print(f"Ortalama Kazanç (USD):      {metrics['average_win_usd']:.2f} USD")
    print(f"Ortalama Kayıp (USD):       {metrics['average_loss_usd']:.2f} USD")
    print(f"Ortalama Ödül/Risk Oranı:   {metrics['average_reward_risk_ratio']}")
    print("-" * 30)
    print(f"Ort. İşlem Süresi (Saat):   {metrics['average_trade_duration_hours']:.2f} saat")
    print("-----------------------------\n")


# --- Ana Çalıştırma Bloğu ---
if __name__ == "__main__":
    logger.info("--- Performans Analiz Scripti Başlatıldı ---")

    # İşlem geçmişi dosyasının yolunu al (config'den veya varsayılan)
    if config and hasattr(config, 'TRADE_HISTORY_FILE'):
        history_file = config.TRADE_HISTORY_FILE
    else:
        # Config yoksa varsayılan yolu kullan
        history_file = os.path.join(project_root, 'data', 'trade_history.json')
        logger.warning(f"Config bulunamadı, varsayılan geçmiş dosyası kullanılıyor: {history_file}")

    if not os.path.exists(history_file):
        logger.error(f"İşlem geçmişi dosyası bulunamadı: {history_file}")
        print(f"\nHATA: İşlem geçmişi dosyası bulunamadı: {history_file}")
    else:
        logger.info(f"İşlem geçmişi okunuyor: {history_file}")
        # Geçmişi yükle
        trade_history_data = persistence.load_from_disk(history_file, default=[])

        if not trade_history_data:
            print("\nİşlem geçmişi boş veya okunamadı.")
        else:
            # Metrikleri hesapla
            calculated_metrics = calculate_performance_metrics(trade_history_data)
            # Metrikleri göster
            display_metrics(calculated_metrics)

    logger.info("--- Performans Analiz Scripti Tamamlandı ---")