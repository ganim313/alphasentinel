"""
AlphaSentinel Configuration & Settings Module
Uses Pydantic Settings for type-safe environment variable parsing with defaults.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
import logging
import math

logger = logging.getLogger(__name__)

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core System
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DUCKDB_PATH: str = "alphasentinel.duckdb"
    PAPER_TRADING_MODE: bool = True
    SHADOW_MODE: bool = True  # If True, AI agents run in shadow mode for experimental validation

    # Free Tier LLM Keys
    GEMINI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # Model IDs for LiteLLM Waterfall
    PRIMARY_LLM: str = "gemini/gemini-flash-latest"
    REASONING_LLM: str = "gemini/gemini-flash-latest"
    FALLBACK_LLM_1: str = "groq/openai/gpt-oss-120b"
    FALLBACK_LLM_2: str = "openrouter/qwen/qwen3.8-27b:free"

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_ADMIN_USER_ID: Optional[str] = None

    # Liquidity & Risk Guard Constraints
    MIN_CIRCUIT_BAND_PCT: float = 10.0    # Warning if circuit band <= 10%
    MAX_PORTFOLIO_RISK_PER_TRADE_PCT: float = 1.5  # 1.5% max capital risk per trade
    MAX_SECTOR_ALLOCATION_PCT: float = 25.0        # Max 25% portfolio in single sector
    MAX_MONTHLY_DRAWDOWN_PCT: float = 6.0          # Backward compatibility
    MONTHLY_DRAWDOWN_SOFT_WARN_PCT: float = 4.0    # Monthly drawdown soft warning threshold
    MAX_DRAWDOWN_KILL_PCT: float = 6.0             # Lifetime HWM drawdown hard kill switch threshold
    CORRELATION_GUARD_THRESHOLD: float = 0.65      # Max allowable average Pearson correlation with open positions

    # Live Trading Safety Circuit
    LIVE_TRADING_ENABLED: bool = False  # Hard safety gate: MUST be explicitly True in .env to allow live HTTP exchange orders

    # Phase 6 Strategic Settings
    # P6-2 CPPI Drawdown Control
    CPPI_MULTIPLIER: float = 3.0        # m — risk multiplier
    CPPI_FLOOR_PCT: float = 0.94        # 6% headroom from lifetime HWM (Floor = 94% HWM)

    # P6-3 Portfolio Volatility Targeting
    VOL_TARGET_ANNUAL: float = 0.15     # 15% annualized portfolio volatility target
    VOL_TARGET_LOOKBACK_DAYS: int = 60  # Rolling window for covariance matrix

    # P6-5 Nightly DuckDB Cloud Backup (Backblaze B2 / S3-compatible)
    B2_ENDPOINT_URL: str = ""
    B2_KEY_ID: str = ""
    B2_APPLICATION_KEY: str = ""
    B2_BUCKET_NAME: str = "alphasentinel-backup"
    BACKUP_RETENTION_DAYS: int = 30

    # P6-6 Shadow Mode A/B Framework
    ML_CUTOFF_CONTROL: float = 0.75     # Production cutoff
    ML_CUTOFF_VARIANT: float = 0.65     # Experimental (shadow) cutoff

    # Scraping Config
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )
    REQUEST_TIMEOUT_SECONDS: int = 15

    # Broker Execution Mode (PAPER, DHAN, FYERS)
    EXECUTION_ENV: str = "PAPER"
    ALGO_ALLOCATED_CAPITAL: float = 1000000.0  # Max cash the algo is allowed to use
    
    # Fyers API (Free Data & Execution)
    FYERS_APP_ID: Optional[str] = None
    FYERS_SECRET_KEY: Optional[str] = None
    FYERS_REDIRECT_URI: str = "https://127.0.0.1:8080/"
    
    # Dhan API (Execution)
    DHAN_CLIENT_ID: Optional[str] = None
    DHAN_ACCESS_TOKEN: Optional[str] = None

    @model_validator(mode="after")
    def sync_paper_trading(self) -> "Settings":
        # Keep PAPER_TRADING_MODE synced with EXECUTION_ENV
        if self.EXECUTION_ENV.upper() != "PAPER":
            self.PAPER_TRADING_MODE = False
        else:
            self.PAPER_TRADING_MODE = True
        return self


# Global Singleton
settings = Settings()

def get_market_cap_tier(market_cap_cr: Optional[float]) -> str:
    """
    Classify stock into a market cap tier based on crores.
    Safely handles None, NaN, and non-numeric inputs.
    """
    if market_cap_cr is None:
        return "MICRO"
    try:
        val = float(market_cap_cr)
        if math.isnan(val) or val <= 0:
            return "MICRO"
        if val >= 20000:
            return "LARGE"
        elif val >= 5000:
            return "MID"
        elif val >= 1000:
            return "SMALL"
        else:
            return "MICRO"
    except (ValueError, TypeError):
        return "MICRO"

