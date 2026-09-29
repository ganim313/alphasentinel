# Continuous Improvement & AutoML Blueprint

This document outlines how the AlphaSentinel system will evolve from a static Machine Learning model into a self-learning, autonomous strategy generator over the next 1-2 months.

## Phase 1: The Feedback Loop (Months 1-2)
Currently, the XGBoost model is "frozen" based on historical data. However, the system is silently collecting a massive dataset of live performance.

### What we are tracking:
1.  **AI Confidence vs. Reality:** Every trade logs the `ml_probability` score. We will correlate this with the actual `realized_pnl` to see if a 90% AI score actually performs better than a 70% score in live markets.
2.  **Arbiter Overrides:** We track every time the Multi-Agent Debate rejects a trade. Did the Arbiter save us from a crash, or did it make us miss a massive breakout?
3.  **Slippage Logging:** Tracking `limit_price` vs `executed_price` to mathematically optimize our 0.1% limit chaser.

### The 60-Day Retraining Trigger:
In 2 months, we will export the `paper_trades` database and feed it *back* into the Jupyter Notebook. We will use **Reinforcement Learning from Human Feedback (RLHF)** (or in this case, Market Feedback) to penalize the model for setups that look good historically but fail in modern market microstructure.

---

## Phase 2: Autonomous Strategy Discovery (Alpha Factory)
Currently, our features (`dist_high`, `ema_dist`) are engineered based on human logic (Mark Minervini's strategy). To make the system build its *own* strategies, we will implement an **Alpha Factory** using Genetic Programming.

### How it will work:
1.  **Formula Generation:** A background Python script will randomly combine basic price action data (Open, High, Low, Close, Volume) using mathematical operators (Add, Subtract, Rolling Mean, Standard Deviation).
    *   *Example output:* `(Close - Rolling_Min(Low, 14)) / Volume_EMA(20)`
2.  **Tournament Selection:** The system will generate 10,000 of these random formulas overnight and test them against 5 years of Nifty 500 data.
3.  **Survival of the Fittest:** The top 50 formulas that generate the highest Sharpe Ratio will "breed" to create a new generation of formulas.
4.  **Auto-Deployment:** If a machine-generated feature proves mathematically superior to our human-engineered `dist_high`, the system will automatically inject it into the XGBoost feature pipeline.

By implementing this, the system stops relying on human trading books and starts discovering mathematical anomalies that human traders cannot see.
