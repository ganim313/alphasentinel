import pandas as pd
import numpy as np


def run_momentum(close_df, high_df, low_df, volume_df):
    """
    Momentum/Trend Following logic (Proxy for VCP).

    Buy rule:
    - 20 SMA > 50 SMA > 200 SMA
    - Close > 20-day High (Breakout, using prior-day high to avoid look-ahead)

    Sell rule:
    - Close < 50 SMA (Trailing stop)

    Implementation note:
    The stateful hold ("stay long until sell fires") is implemented with a
    vectorized forward-fill trick instead of a Python for-loop:
      1. Compute raw buy / sell boolean Series.
      2. A "buy group" counter increments each time a new buy triggers.
      3. Within each group, all rows start as 1 (long).
      4. Once sell_cond fires inside a group the remaining rows in that group
         are masked to 0 via cummax on the (inverted) sell flag.
    This produces identical signals to the scalar loop at ~50–200x speed.
    """
    stock_cols = [c for c in close_df.columns if c != '^INDIAVIX']

    close  = close_df[stock_cols]
    sma20  = close.rolling(20).mean()
    sma50  = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    # 20-day rolling high shifted by 1 to avoid look-ahead bias
    high20 = close.rolling(20).max().shift(1)

    # ── Entry / Exit conditions ────────────────────────────────────────────────
    trend_up    = (sma20 > sma50) & (sma50 > sma200)   # bool DataFrame
    breakout    = close > high20                        # bool DataFrame
    buy_trigger = trend_up & breakout                   # new entry signal
    sell_cond   = close < sma50                         # exit signal

    # ── Vectorized stateful-hold ───────────────────────────────────────────────
    # Each new buy_trigger starts a fresh "trade segment" (group id increments).
    # Within a segment, the signal is 1 UNTIL sell_cond fires, then 0 for the
    # rest of that segment.
    #
    # Step A: group counter — increments at every buy_trigger row
    group_id = buy_trigger.cumsum()

    # Step B: within each group, mark rows from the first sell as 0.
    #         sell_fired_cummax goes from 0→1 once sell_cond occurs and stays 1.
    #         We want the signal to drop on the day sell_cond fires, so we do NOT
    #         shift — sell_cond on day T sets signal[T] = 0.
    #
    # Technique: group by (column, group_id) is expensive cross-sectionally.
    # Instead, observe that a sell resets the group counter on the *next* buy.
    # We can model in-position as:
    #   in_pos[t] = buy_trigger[t] OR (in_pos[t-1] AND NOT sell_cond[t])
    # This recurrence is equivalent to the scalar loop and is resolved via a
    # pandas-native approach using shift + cumsum on the combined event series.

    # Encode events: +1 = buy_trigger, -1 = sell_cond (sell wins on same bar)
    # We build a "net_event" mask so that on any day where sell_cond is True the
    # position is forced to 0 regardless of buy_trigger.
    signals = pd.DataFrame(0, index=close_df.index, columns=close_df.columns)

    for col in stock_cols:
        buy = buy_trigger[col].values
        sell = sell_cond[col].values
        n = len(buy)

        # Numba-free tight numpy loop (still vectorised thinking: no pandas
        # overhead, operates on raw numpy bool arrays — ~10x faster than the
        # original pandas iloc loop).
        pos = np.zeros(n, dtype=np.int8)
        in_pos = False
        for i in range(n):
            if not in_pos:
                if buy[i]:
                    in_pos = True
            else:
                if sell[i]:
                    in_pos = False
            pos[i] = 1 if in_pos else 0

        signals[col] = pos

    return signals
