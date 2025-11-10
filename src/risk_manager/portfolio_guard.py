"""
Portfolio-level daily risk and drawdown guard.
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict

logger = logging.getLogger(__name__)

try:
    from src.database.models import OpenPosition, TradeHistory, AlphaCache, get_db_session
except Exception:
    # Lazy import inside functions if needed
    OpenPosition = TradeHistory = AlphaCache = None
    get_db_session = None


def _utc_day_start_ts(now: datetime = None) -> int:
    if now is None:
        now = datetime.now(timezone.utc)
    day_start = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)
    return int(day_start.timestamp())


def check_daily_limits(config, portfolio_usd: float) -> Tuple[bool, str, Dict]:
    """
    Enforce daily new-risk budget and daily drawdown circuit breaker.

    Returns:
        (allow_open, reason, status_dict)
    """
    try:
        max_daily_risk_pct = float(getattr(config, 'MAX_DAILY_RISK_PERCENT', 5.0))
        max_daily_dd_pct = float(getattr(config, 'MAX_DAILY_DRAWDOWN_PERCENT', 5.0))
        if portfolio_usd <= 0:
            return False, 'invalid_portfolio', {'portfolio_usd': portfolio_usd}

        day_start_ts = _utc_day_start_ts()
        realized_pnl_today = 0.0
        open_risk_today_pct = 0.0

        with get_db_session() as db:
            # Sum planned_risk_percent of positions opened today
            try:
                open_positions_today = db.query(OpenPosition).filter(OpenPosition.open_time >= day_start_ts).all()
                open_risk_today_pct = sum((p.planned_risk_percent or 0.0) for p in open_positions_today)
            except Exception as e:
                logger.warning(f"Open positions risk toplama hatası: {e}")

            # Sum realized PnL of closed trades today
            try:
                closed_trades_today = db.query(TradeHistory).filter(TradeHistory.close_time >= day_start_ts).all()
                realized_pnl_today = sum((t.pnl_usd or 0.0) for t in closed_trades_today)
            except Exception as e:
                logger.warning(f"Trade history toplama hatası: {e}")

            # Cache status (optional)
            try:
                status = {
                    'ts': int(time.time()),
                    'open_risk_today_pct': open_risk_today_pct,
                    'realized_pnl_today': realized_pnl_today,
                    'portfolio_usd': portfolio_usd,
                }
                cache = db.query(AlphaCache).filter(AlphaCache.key == 'portfolio_guard_status').first()
                if cache:
                    cache.value = status
                    db.merge(cache)
                else:
                    db.add(AlphaCache(key='portfolio_guard_status', value=status))
            except Exception as e:
                logger.debug(f"Guard status cache yazılamadı: {e}")

        # Evaluate limits
        if open_risk_today_pct >= max_daily_risk_pct:
            reason = f"daily_risk_budget_exhausted:{open_risk_today_pct:.2f}%>={max_daily_risk_pct:.2f}%"
            logger.warning(f"⛔ Yeni pozisyon engellendi - {reason}")
            return False, reason, {
                'open_risk_today_pct': open_risk_today_pct,
                'realized_pnl_today': realized_pnl_today,
            }

        dd_today_pct = 0.0
        if realized_pnl_today < 0:
            dd_today_pct = abs(realized_pnl_today) / portfolio_usd * 100.0
            if dd_today_pct >= max_daily_dd_pct:
                reason = f"daily_dd_exceeded:{dd_today_pct:.2f}%>={max_daily_dd_pct:.2f}%"
                logger.error(f"🚨 Günlük drawdown limiti aşıldı - {reason}")
                return False, reason, {
                    'open_risk_today_pct': open_risk_today_pct,
                    'realized_pnl_today': realized_pnl_today,
                    'dd_today_pct': dd_today_pct,
                }

        return True, 'ok', {
            'open_risk_today_pct': open_risk_today_pct,
            'realized_pnl_today': realized_pnl_today,
            'dd_today_pct': dd_today_pct,
        }
    except Exception as e:
        logger.error(f"Portfolio guard hata: {e}", exc_info=True)
        return True, 'guard_error', {}
