# src/trade_manager/margin_tracker.py
"""
v7.1 YENİ: Margin Kullanımı İzleme Sistemi
Tüm açık pozisyonların toplam margin kullanımını takip eder.
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from src.database.models import OpenPosition

logger = logging.getLogger(__name__)

class MarginTracker:
    """Margin kullanımını izler ve sağlık durumunu raporlar."""
    
    def __init__(self, config):
        self.config = config
        self.balance_usd = getattr(config, 'PORTFOLIO_USD', 200.0)
        
        # Güvenlik eşikleri
        self.margin_warning_threshold = 0.70  # %70 kullanım → Uyarı
        self.margin_critical_threshold = 0.85  # %85 kullanım → Kritik
        self.margin_stop_threshold = 0.90      # %90 kullanım → Yeni pozisyon yasak
    
    def calculate_total_margin_usage(self, db: Session) -> Dict[str, float]:
        """
        Tüm açık pozisyonların toplam margin kullanımını hesaplar.
        
        Returns:
            {
                'total_margin_used': 120.5,  # Toplam kullanılan margin (USD)
                'available_margin': 79.5,     # Kalan serbest margin (USD)
                'usage_percent': 0.60,        # Kullanım yüzdesi (0-1)
                'position_count': 5,          # Açık pozisyon sayısı
                'avg_leverage': 7.2,          # Ortalama kaldıraç
                'health_status': 'HEALTHY'    # HEALTHY / WARNING / CRITICAL / DANGER
            }
        """
        try:
            # Tüm açık pozisyonları al
            positions = db.query(OpenPosition).filter(
                OpenPosition.status == 'OPEN'
            ).all()
            
            if not positions:
                return {
                    'total_margin_used': 0.0,
                    'available_margin': self.balance_usd,
                    'usage_percent': 0.0,
                    'position_count': 0,
                    'avg_leverage': 0.0,
                    'health_status': 'HEALTHY'
                }
            
            total_margin = 0.0
            total_leverage_weighted = 0.0
            
            for pos in positions:
                # Margin = Position Value / Leverage
                position_value = pos.position_size_units * pos.entry_price  # ✅ position_size → position_size_units
                leverage = getattr(pos, 'leverage', 10)  # Default 10x
                margin = position_value / leverage
                
                total_margin += margin
                total_leverage_weighted += leverage
            
            # Metrikler
            position_count = len(positions)
            avg_leverage = total_leverage_weighted / position_count if position_count > 0 else 0.0
            usage_percent = total_margin / self.balance_usd if self.balance_usd > 0 else 0.0
            available_margin = self.balance_usd - total_margin
            
            # Sağlık durumu
            if usage_percent >= self.margin_stop_threshold:
                health_status = 'DANGER'
            elif usage_percent >= self.margin_critical_threshold:
                health_status = 'CRITICAL'
            elif usage_percent >= self.margin_warning_threshold:
                health_status = 'WARNING'
            else:
                health_status = 'HEALTHY'
            
            logger.info(f"📊 Margin Durumu: {health_status} - Kullanım: ${total_margin:.2f}/{self.balance_usd:.2f} ({usage_percent:.1%})")
            
            return {
                'total_margin_used': total_margin,
                'available_margin': available_margin,
                'usage_percent': usage_percent,
                'position_count': position_count,
                'avg_leverage': avg_leverage,
                'health_status': health_status
            }
            
        except Exception as e:
            logger.error(f"Margin hesaplaması sırasında hata: {e}", exc_info=True)
            return {
                'total_margin_used': 0.0,
                'available_margin': self.balance_usd,
                'usage_percent': 0.0,
                'position_count': 0,
                'avg_leverage': 0.0,
                'health_status': 'ERROR'
            }
    
    def can_open_new_position(self, required_margin: float, db: Session) -> tuple[bool, str]:
        """
        Yeni pozisyon için yeterli margin var mı kontrol eder.
        
        Args:
            required_margin: Yeni pozisyon için gerekli margin (USD)
            db: Database session
            
        Returns:
            (can_open: bool, reason: str)
        """
        try:
            status = self.calculate_total_margin_usage(db)
            
            # Toplam kullanım eşiği kontrolü
            if status['usage_percent'] >= self.margin_stop_threshold:
                return False, f"⛔ Margin kullanımı kritik seviyede ({status['usage_percent']:.1%}). Yeni pozisyon açılamaz."
            
            # Yeni pozisyon sonrası kullanım kontrolü
            new_total_margin = status['total_margin_used'] + required_margin
            new_usage_percent = new_total_margin / self.balance_usd
            
            if new_usage_percent > self.margin_stop_threshold:
                return False, f"⚠️ Yeni pozisyon toplam margin kullanımını {new_usage_percent:.1%}'e çıkaracak (Limit: {self.margin_stop_threshold:.1%})"
            
            # Serbest margin yeterli mi?
            if status['available_margin'] < required_margin:
                return False, f"💰 Yetersiz margin. Gereken: ${required_margin:.2f}, Mevcut: ${status['available_margin']:.2f}"
            
            logger.info(f"✅ Margin yeterli: Gereken ${required_margin:.2f}, Kullanım: {new_usage_percent:.1%}")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Margin kontrolü sırasında hata: {e}", exc_info=True)
            return False, f"Hata: {str(e)}"
    
    def get_position_margin_breakdown(self, db: Session) -> List[Dict]:
        """
        Her pozisyonun margin kullanımını detaylı gösterir.
        
        Returns:
            [
                {
                    'symbol': 'BTCUSDT',
                    'direction': 'LONG',
                    'position_value': 240.0,
                    'leverage': 8,
                    'margin_used': 30.0,
                    'margin_percent': 0.15  # Toplam balance'ın %15'i
                },
                ...
            ]
        """
        try:
            positions = db.query(OpenPosition).filter(
                OpenPosition.status == 'OPEN'
            ).all()
            
            breakdown = []
            for pos in positions:
                position_value = pos.position_size_units * pos.entry_price  # ✅ position_size → position_size_units
                leverage = getattr(pos, 'leverage', 10)
                margin = position_value / leverage
                margin_percent = margin / self.balance_usd if self.balance_usd > 0 else 0.0
                
                breakdown.append({
                    'symbol': pos.symbol,
                    'direction': pos.direction,
                    'position_value': position_value,
                    'leverage': leverage,
                    'margin_used': margin,
                    'margin_percent': margin_percent
                })
            
            # Margin kullanımına göre sırala (büyükten küçüğe)
            breakdown.sort(key=lambda x: x['margin_used'], reverse=True)
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Margin detay raporu oluşturulamadı: {e}", exc_info=True)
            return []
    
    def log_margin_health_report(self, db: Session):
        """Detaylı margin sağlık raporu loglar."""
        try:
            status = self.calculate_total_margin_usage(db)
            breakdown = self.get_position_margin_breakdown(db)
            
            logger.info("=" * 60)
            logger.info("📊 MARGIN SAĞLIK RAPORU")
            logger.info("=" * 60)
            logger.info(f"💰 Toplam Balance: ${self.balance_usd:.2f}")
            logger.info(f"📈 Kullanılan Margin: ${status['total_margin_used']:.2f} ({status['usage_percent']:.1%})")
            logger.info(f"💵 Serbest Margin: ${status['available_margin']:.2f}")
            logger.info(f"📊 Açık Pozisyon: {status['position_count']} adet")
            logger.info(f"⚡ Ortalama Kaldıraç: {status['avg_leverage']:.1f}x")
            logger.info(f"🏥 Sağlık Durumu: {status['health_status']}")
            logger.info("-" * 60)
            
            if breakdown:
                logger.info("📋 Pozisyon Bazında Margin Dağılımı:")
                for i, pos in enumerate(breakdown, 1):
                    logger.info(
                        f"  {i}. {pos['symbol']} {pos['direction']}: "
                        f"${pos['margin_used']:.2f} margin "
                        f"({pos['margin_percent']:.1%} balance) "
                        f"[{pos['leverage']}x kaldıraç]"
                    )
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Margin raporu loglanamadı: {e}", exc_info=True)


def create_margin_tracker(config) -> MarginTracker:
    """Margin tracker instance oluşturur."""
    return MarginTracker(config)
