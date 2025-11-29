#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scanner Sinyal Görüntüleyici
Bulunan sinyalleri database'den sorgular ve görüntüler
"""

import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database.models import ScannerSignal, db_session

def view_recent_signals(hours=24, limit=50):
    """
    Son N saatteki sinyalleri göster
    
    Args:
        hours: Kaç saatlik geçmiş (varsayılan: 24)
        limit: Maksimum gösterilecek sinyal sayısı
    """
    try:
        db = db_session()
        
        # Son N saatteki sinyaller
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        signals = db.query(ScannerSignal)\
            .filter(ScannerSignal.created_at >= cutoff_time)\
            .order_by(ScannerSignal.strength.desc())\
            .limit(limit)\
            .all()
        
        if not signals:
            print(f"\n❌ Son {hours} saatte sinyal bulunamadı.\n")
            return
        
        print(f"\n{'='*120}")
        print(f"📊 SON {hours} SAATTEKİ SİNYALLER ({len(signals)} adet)")
        print(f"{'='*120}\n")
        
        for i, sig in enumerate(signals, 1):
            icon = "🟢" if sig.signal_type == "bullish" else "🔴"
            direction = "LONG " if sig.signal_type == "bullish" else "SHORT"
            
            # Dinamik fiyat formatı (küçük sayılar için daha fazla ondalık)
            if sig.price < 0.01:
                price_fmt = f"${sig.price:.8f}"
                sl_fmt = f"${sig.stop_loss:.8f}"
                tp_fmt = f"${sig.take_profit:.8f}"
            elif sig.price < 1:
                price_fmt = f"${sig.price:.6f}"
                sl_fmt = f"${sig.stop_loss:.6f}"
                tp_fmt = f"${sig.take_profit:.6f}"
            else:
                price_fmt = f"${sig.price:.4f}"
                sl_fmt = f"${sig.stop_loss:.4f}"
                tp_fmt = f"${sig.take_profit:.4f}"
            
            print(f"{i}. {icon} {sig.symbol} - {direction}")
            print(f"   📅 Zaman: {sig.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   💰 Entry: {price_fmt} | SL: {sl_fmt} ({sig.sl_pct:.1f}%) | TP: {tp_fmt} ({sig.tp_pct:.1f}%)")
            print(f"   📊 Güç: {sig.strength:.1f}% | Uyum: {sig.alignment:.0f}% | Kalite: {sig.quality_grade} ({sig.quality_score:.0f}/100)")
            print(f"   🎯 RR: 1:{sig.rr_ratio:.1f} | Pozisyon: {sig.position_size_pct*100:.1f}%")
            print(f"   📈 1G Trend: {sig.daily_trend.upper()} | 4S Kalite: {sig.four_h_quality:.0f}%")
            
            if sig.position_opened:
                print(f"   ✅ POZİSYON AÇILDI (ID: {sig.position_id})")
            else:
                print(f"   ⏳ Pozisyon açılmadı")
            
            print()
        
        print(f"{'='*120}\n")
        
        # İstatistikler
        bullish_count = sum(1 for s in signals if s.signal_type == "bullish")
        bearish_count = len(signals) - bullish_count
        avg_strength = sum(s.strength for s in signals) / len(signals)
        opened_count = sum(1 for s in signals if s.position_opened)
        
        print(f"📊 İSTATİSTİKLER:")
        print(f"   🟢 Bullish: {bullish_count} | 🔴 Bearish: {bearish_count}")
        print(f"   📈 Ortalama Güç: {avg_strength:.1f}%")
        print(f"   ✅ Açılan Pozisyon: {opened_count}/{len(signals)} ({opened_count/len(signals)*100:.1f}%)")
        print()
        
    except Exception as e:
        print(f"❌ Hata: {e}")
    finally:
        db_session.remove()


def view_signal_stats():
    """Genel sinyal istatistikleri"""
    try:
        db = db_session()
        
        total_signals = db.query(ScannerSignal).count()
        
        if total_signals == 0:
            print("\n❌ Henüz hiç sinyal kaydedilmemiş.\n")
            return
        
        # Son 24 saat
        last_24h = db.query(ScannerSignal)\
            .filter(ScannerSignal.created_at >= datetime.utcnow() - timedelta(hours=24))\
            .count()
        
        # Son 7 gün
        last_7d = db.query(ScannerSignal)\
            .filter(ScannerSignal.created_at >= datetime.utcnow() - timedelta(days=7))\
            .count()
        
        # Açılan pozisyonlar
        positions_opened = db.query(ScannerSignal)\
            .filter(ScannerSignal.position_opened == True)\
            .count()
        
        # En iyi performans gösteren semboller
        top_symbols = db.query(
            ScannerSignal.symbol,
            db.func.count(ScannerSignal.id).label('count'),
            db.func.avg(ScannerSignal.strength).label('avg_strength')
        ).group_by(ScannerSignal.symbol)\
         .order_by(db.func.count(ScannerSignal.id).desc())\
         .limit(10)\
         .all()
        
        print(f"\n{'='*80}")
        print(f"📊 GENEL SİNYAL İSTATİSTİKLERİ")
        print(f"{'='*80}\n")
        
        print(f"🎯 TOPLAM SİNYAL SAYISI: {total_signals}")
        print(f"   📅 Son 24 saat: {last_24h}")
        print(f"   📅 Son 7 gün: {last_7d}")
        print(f"   ✅ Açılan pozisyon: {positions_opened} ({positions_opened/total_signals*100:.1f}%)")
        print()
        
        print(f"🏆 EN ÇOK SİNYAL VERİLEN SEMBOLLER:")
        for i, (symbol, count, avg_str) in enumerate(top_symbols, 1):
            print(f"   {i}. {symbol}: {count} sinyal (Ort. Güç: {avg_str:.1f}%)")
        
        print(f"\n{'='*80}\n")
        
    except Exception as e:
        print(f"❌ Hata: {e}")
    finally:
        db_session.remove()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Scanner Sinyal Görüntüleyici')
    parser.add_argument('--hours', type=int, default=24, help='Son kaç saatteki sinyaller (varsayılan: 24)')
    parser.add_argument('--limit', type=int, default=50, help='Maksimum gösterilecek sinyal (varsayılan: 50)')
    parser.add_argument('--stats', action='store_true', help='Genel istatistikleri göster')
    
    args = parser.parse_args()
    
    if args.stats:
        view_signal_stats()
    else:
        view_recent_signals(hours=args.hours, limit=args.limit)
