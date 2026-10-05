import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.session import get_read_connection
import pandas as pd
import datetime

def generate_monthly_report(year: int, month: int):
    print(f"\\n🕌 SHARIAH PURIFICATION MONTHLY REPORT: {year}-{month:02d} 🕌")
    print("="*60)
    
    with get_read_connection() as conn:
        df = conn.execute(f"""
            SELECT p.trade_id, p.symbol, p.exit_date, p.net_profit, p.impure_income_ratio, p.purification_amount
            FROM purification_log p
            WHERE EXTRACT(YEAR FROM p.exit_date) = {year} 
            AND EXTRACT(MONTH FROM p.exit_date) = {month}
            ORDER BY p.exit_date ASC
        """).df()
        
    if df.empty:
        print("No profitable Shariah trades closed this month.")
        print("="*60)
        return
        
    total_profit = df['net_profit'].sum()
    total_purification = df['purification_amount'].sum()
    
    # Formatting for terminal
    df['exit_date'] = pd.to_datetime(df['exit_date']).dt.strftime('%Y-%m-%d')
    df['net_profit'] = df['net_profit'].apply(lambda x: f"₹{x:.2f}")
    df['impure_ratio'] = df['impure_income_ratio'].apply(lambda x: f"{x*100:.2f}%")
    df['donation'] = df['purification_amount'].apply(lambda x: f"₹{x:.2f}")
    
    print(df[['exit_date', 'symbol', 'net_profit', 'impure_ratio', 'donation']].to_string(index=False))
    print("-" * 60)
    print(f"Total Gross Profit: ₹{total_profit:.2f}")
    print(f"Total Mandatory Charity (Zakat/Purification): ₹{total_purification:.2f}")
    print(f"Net Halal Profit Kept: ₹{(total_profit - total_purification):.2f}")
    print("="*60)
    print("Note: Purified amounts must be donated to charity without the intention of receiving spiritual reward for it.\\n")

def resolve_report_year_month(
    now: datetime.datetime | None = None,
    argv: list[str] | None = None,
) -> tuple[int, int]:
    """
    Resolves (year, month) for the Shariah purification report.
    If explicit CLI arguments [script, year, month] are given, uses those.
    Otherwise, when executed on the 1st of the month without explicit CLI year/month arguments,
    reports on the previous completed calendar month.
    """
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    if now is None:
        now = datetime.datetime.now(ist)
    elif getattr(now, "tzinfo", None) is not None:
        now = now.astimezone(ist)
    args = argv if argv is not None else sys.argv
    if len(args) == 3:
        return int(args[1]), int(args[2])
    if now.day == 1:
        prev_month = now.replace(day=1) - datetime.timedelta(days=1)
        return prev_month.year, prev_month.month
    return now.year, now.month


if __name__ == "__main__":
    y, m = resolve_report_year_month()
    generate_monthly_report(y, m)
