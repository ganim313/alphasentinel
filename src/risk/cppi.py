"""
CPPI (Constant Proportion Portfolio Insurance) Exposure Calculator.
Used by arbiter.py to scale suggested_shares as equity approaches the drawdown floor.
"""
import logging
from src.config.settings import settings

logger = logging.getLogger(__name__)


def calculate_cppi_exposure(core_equity: float, lifetime_hwm: float) -> float:
    """
    Returns CPPI exposure scalar in [0.0, 1.0].
    - 1.0  -> full position sizing (at or above HWM, comfortable cushion)
    - 0.0  -> no new positions (cushion depleted -- soft halt)

    Formula:
        Floor_t = FloorPct * HWM_t (default: 0.94 * HWM_t)
        Cushion_t = max(0, core_equity - Floor_t)
        MaxCushion_t = HWM_t * (1 - FloorPct)
        Exposure_t = min(1.0, Cushion_t / MaxCushion_t)

    Args:
        core_equity: Current portfolio equity (INITIAL_CAPITAL + realized + unrealized PnL)
        lifetime_hwm: All-time high-water mark from portfolio_state
    """
    if core_equity <= 0 or lifetime_hwm <= 0:
        logger.warning("CPPI: Non-positive equity or HWM -- blocking new positions (exposure=0.0).")
        return 0.0

    floor = lifetime_hwm * settings.CPPI_FLOOR_PCT
    cushion = core_equity - floor

    if cushion <= 0:
        logger.warning(
            f"CPPI cushion depleted: core_equity=Rs.{core_equity:,.2f}, "
            f"floor=Rs.{floor:,.2f}. Blocking new positions (exposure=0.0)."
        )
        return 0.0

    max_cushion = lifetime_hwm * (1.0 - settings.CPPI_FLOOR_PCT)
    if max_cushion <= 0:
        return 1.0

    exposure = min(1.0, cushion / max_cushion)
    logger.debug(
        f"CPPI: HWM=Rs.{lifetime_hwm:,.2f}, Floor=Rs.{floor:,.2f}, "
        f"Cushion=Rs.{cushion:,.2f}, Exposure={exposure:.4f}"
    )
    return float(exposure)
