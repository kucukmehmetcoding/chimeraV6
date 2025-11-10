"""
Kelly Criterion bazlı gelişmiş pozisyon boyutlandırma
"""
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class KellyPositionSizer:
    """
    Kelly Criterion ile pozisyon boyutu hesaplama
    """
    
    def __init__(self, config, db_session: Session):
        self.config = config
        self.db = db_session
        self.use_fractional_kelly = getattr(config, 'USE_FRACTIONAL_KELLY', True)
        self.kelly_fraction = getattr(config, 'KELLY_FRACTION', 0.25)  # %25 Kelly (Kelly / 4)
    
    def calculate_kelly_size(
        self,
        win_rate: Optional[float],
        avg_win_loss_ratio: Optional[float],
        rr_ratio: float,
        max_position_value: float
    ) -> Dict[str, float]:
        """
        Kelly Criterion ile optimal pozisyon boyutu hesapla
        
        Args:
            win_rate: Geçmiş kazanma oranı (0-1), None ise varsayılan kullan
            avg_win_loss_ratio: Ortalama kazanç/kayıp oranı, None ise RR kullan
            rr_ratio: Mevcut sinyalin RR oranı
            max_position_value: Maksimum pozisyon değeri (USD)
            
        Returns:
            {
                'kelly_percent': float,      # Kelly yüzdesi
                'recommended_size': float,   # Önerilen pozisyon boyutu (USD)
                'confidence': str            # 'HIGH', 'MEDIUM', 'LOW', 'NONE'
            }
        """
        # Geçmiş verileri al
        historical_stats = self._get_historical_performance()
        
        # Win rate belirle
        if win_rate is None:
            win_rate = historical_stats.get('win_rate', 0.5)  # Varsayılan %50
        
        # Win/Loss ratio belirle
        if avg_win_loss_ratio is None:
            avg_win_loss_ratio = historical_stats.get('avg_wl_ratio', rr_ratio)
        
        # Kelly formülü: K = (p * b - q) / b
        # p = kazanma olasılığı
        # q = kaybetme olasılığı = 1 - p
        # b = kazanç/kayıp oranı
        
        p = win_rate
        q = 1 - p
        b = avg_win_loss_ratio
        
        kelly_percent = (p * b - q) / b if b > 0 else 0.0
        
        # Negatif Kelly = hiç pozisyon açma
        if kelly_percent <= 0:
            logger.warning(f"Negatif Kelly ({kelly_percent:.2%}) - pozisyon önerilmez")
            return {
                'kelly_percent': 0.0,
                'recommended_size': 0.0,
                'confidence': 'NONE'
            }
        
        # Fractional Kelly uygula (risk yönetimi için)
        if self.use_fractional_kelly:
            kelly_percent *= self.kelly_fraction
            logger.info(f"Fractional Kelly uygulandı: {self.kelly_fraction} -> {kelly_percent:.2%}")

        # Kelly üst sınırını uygula (hem %100 hem config limit)
        max_fraction = getattr(self.config, 'KELLY_MAX_FRACTION', 0.15)
        kelly_percent = min(kelly_percent, max_fraction)

        # Veri güvenilirliği düşükse (az trade) ekstra konservatif kırp
        total_trades = historical_stats.get('total_trades', 0)
        min_trades = getattr(self.config, 'KELLY_MIN_TRADES_REQUIRED', 30)
        risk_reasoning = []
        if total_trades < min_trades:
            logger.info(f"Kelly: Yetersiz geçmiş ({total_trades} < {min_trades}), konservatif kırpma uygulanıyor.")
            kelly_percent = min(kelly_percent, max_fraction * 0.5)
            risk_reasoning.append(f"insufficient_history:{total_trades}/{min_trades}")

        # Güven seviyesi belirle
        if kelly_percent > 0.15:  # %15'ten fazla
            confidence = 'HIGH'
        elif kelly_percent > 0.05:  # %5-15 arası
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'
        
        recommended_size = max_position_value * kelly_percent
        
        logger.info(
            f"Kelly hesaplandı: WinRate={p:.1%}, W/L={b:.2f}, "
            f"Kelly={kelly_percent:.2%}, Size=${recommended_size:.2f}, "
            f"Confidence={confidence}"
        )
        
        return {
            'kelly_percent': kelly_percent,
            'recommended_size': recommended_size,
            'confidence': confidence,
            'risk_reasoning': ';'.join(risk_reasoning) if 'risk_reasoning' in locals() else ''
        }
    
    def _get_historical_performance(self) -> Dict[str, float]:
        """
        Geçmiş işlemlerden performans istatistikleri çıkar
        
        Returns:
            {
                'win_rate': float,
                'avg_wl_ratio': float,
                'total_trades': int
            }
        """
        try:
            from src.database.models import TradeHistory
            
            # Son 100 kapanmış pozisyonu al
            trades = self.db.query(TradeHistory).order_by(
                TradeHistory.close_time.desc()
            ).limit(100).all()
            
            if not trades:
                logger.warning("Geçmiş işlem bulunamadı, varsayılan değerler kullanılıyor")
                return {
                    'win_rate': 0.5,
                    'avg_wl_ratio': 1.5,
                    'total_trades': 0
                }
            
            wins = [t for t in trades if t.pnl_usd > 0]
            losses = [t for t in trades if t.pnl_usd <= 0]
            
            win_rate = len(wins) / len(trades) if trades else 0.5
            
            avg_win = sum(t.pnl_usd for t in wins) / len(wins) if wins else 0
            avg_loss = abs(sum(t.pnl_usd for t in losses) / len(losses)) if losses else 1
            
            avg_wl_ratio = avg_win / avg_loss if avg_loss > 0 else 1.5
            
            logger.info(
                f"Geçmiş performans: {len(trades)} işlem, "
                f"Win rate: {win_rate:.1%}, Avg W/L: {avg_wl_ratio:.2f}"
            )
            
            return {
                'win_rate': win_rate,
                'avg_wl_ratio': avg_wl_ratio,
                'total_trades': len(trades)
            }
            
        except Exception as e:
            logger.error(f"Performans istatistikleri alınamadı: {e}", exc_info=True)
            return {
                'win_rate': 0.5,
                'avg_wl_ratio': 1.5,
                'total_trades': 0
            }
