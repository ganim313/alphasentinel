import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Optional, Any

from src.utils.holidays import is_nse_holiday

class IndianMarketCompliance:
    IST = ZoneInfo('Asia/Kolkata')

    @classmethod
    def is_holiday(cls, dt: datetime.date) -> bool:
        if isinstance(dt, datetime.datetime):
            dt = dt.date()
        return is_nse_holiday(dt)

    @classmethod
    def get_next_trading_day(cls, dt: datetime.date) -> datetime.date:
        if isinstance(dt, datetime.datetime):
            dt = dt.date()
            
        next_day = dt + datetime.timedelta(days=1)
        # Skip weekends (5=Saturday, 6=Sunday) and holidays
        while next_day.weekday() >= 5 or cls.is_holiday(next_day):
            next_day += datetime.timedelta(days=1)
        return next_day

    @classmethod
    def is_market_open(cls, dt: Optional[datetime.datetime] = None) -> bool:
        """
        Check if the Indian market is currently open.
        Trading hours: 9:15 AM to 3:30 PM IST, Monday to Friday.
        """
        if dt is None:
            dt = datetime.datetime.now(cls.IST)
        else:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=cls.IST)
            else:
                dt = dt.astimezone(cls.IST)

        # Check weekend
        if dt.weekday() >= 5: # 5 = Saturday, 6 = Sunday
            return False

        # Check holiday
        if cls.is_holiday(dt.date()):
            return False

        # Market hours: 09:15 to 15:30
        market_open_time = datetime.time(9, 15)
        market_close_time = datetime.time(15, 30)

        current_time = dt.time()

        return market_open_time <= current_time <= market_close_time

    @classmethod
    def calculate_margin(cls, sell_amount: float, dt: Optional[datetime.date] = None) -> Dict[str, Any]:
        """
        Calculate available margin under T+1 settlement rules.
        80% of sell proceeds are available today.
        20% of sell proceeds are available tomorrow (T+1 trading day).
        """
        if sell_amount <= 0:
            return {
                "available_today": 0.0,
                "available_tomorrow": 0.0,
                "t1_settlement_date": None
            }
            
        if dt is None:
            dt = datetime.datetime.now(cls.IST).date()
        elif isinstance(dt, datetime.datetime):
            dt = dt.date()
            
        t1_date = cls.get_next_trading_day(dt)

        return {
            "available_today": sell_amount * 0.80,
            "available_tomorrow": sell_amount * 0.20,
            "t1_settlement_date": t1_date.isoformat()
        }
