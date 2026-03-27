"""
config.py — Semua parameter dari Pine Script DAHLAH7 Scalper Pro
Setiap parameter di-mapping 1:1 dari input Pine Script.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # ═══════════════════════════════════════════
    # EXCHANGE
    # ═══════════════════════════════════════════
    EXCHANGE: str = "binance"
    API_KEY: str = field(default_factory=lambda: os.getenv("API_KEY", ""))
    API_SECRET: str = field(default_factory=lambda: os.getenv("API_SECRET", ""))
    SYMBOL: str = "BTC/USDT"
    TIMEFRAME: str = "5m"
    MARKET_TYPE: str = "future"  # "spot" or "future"
    LEVERAGE: int = 10
    TESTNET: bool = True

    # ═══════════════════════════════════════════
    # SUPERTREND (Primary Signal)
    # Pine: f_supertrend(close, nsensitivity * 7, 10)
    # ═══════════════════════════════════════════
    ST_SENSITIVITY: float = 1.0
    ST_FACTOR: float = 7.0
    ST_ATR_LEN: int = 10

    # ═══════════════════════════════════════════
    # BUY / SELL SIGNAL
    # ═══════════════════════════════════════════
    ENABLE_BUY_SELL: bool = True
    STOP_LOSS_PCT: float = 1.0  # percentStop input (0 to disable)

    # ═══════════════════════════════════════════
    # RISK MANAGEMENT
    # Pine: atrRisk=3, atrLen=14
    # ═══════════════════════════════════════════
    ATR_RISK: int = 3
    ATR_LEN: int = 14
    SHOW_TP_SL: bool = True
    RISK_PER_TRADE: float = 0.02  # 2% of balance

    # ═══════════════════════════════════════════
    # ADX SIDEWAYS FILTER
    # Pine: adxlen=15, dilen=15, sidewaysThreshold=15
    # ═══════════════════════════════════════════
    ADX_LEN: int = 15
    DI_LEN: int = 15
    ADX_SIDEWAYS_THRESHOLD: int = 15
    USE_ADX_FILTER: bool = True  # skip trades when sideways

    # ═══════════════════════════════════════════
    # RANGE FILTER (Trend Cloud)
    # Pine: smoothrng(close, 22, 6) + rngfilt
    # ═══════════════════════════════════════════
    RF_PERIOD: int = 22
    RF_MULTIPLIER: float = 6.0
    USE_RANGE_FILTER: bool = True  # use as confluence

    # ═══════════════════════════════════════════
    # TREND TRACER CLOUD
    # Pine: x1=22, x2=9, x3=15, x4=5
    # ═══════════════════════════════════════════
    TT_PERIOD1: int = 22
    TT_MULT1: float = 9.0
    TT_PERIOD2: int = 15
    TT_MULT2: float = 5.0
    USE_TREND_TRACER: bool = True

    # ═══════════════════════════════════════════
    # HULL MA TREND CLOUD
    # Pine: tclength=600
    # ═══════════════════════════════════════════
    HULL_LENGTH: int = 600

    # ═══════════════════════════════════════════
    # EMA (Volume Sensitivity)
    # Pine: volSen=3, ema(ohlc4, 5*3), ema(ohlc4, 9*3), ...
    # ═══════════════════════════════════════════
    VOL_SENSITIVITY: int = 3
    EMA_PERIODS: list = field(default_factory=lambda: [15, 27, 39, 102, 150])

    # SMA
    SMA_FAST: int = 8
    SMA_SLOW: int = 9

    # ═══════════════════════════════════════════
    # SMART MONEY CONCEPTS
    # ═══════════════════════════════════════════
    SMC_ENABLED: bool = True
    SMC_MODE: str = "Historical"  # "Historical" or "Present"
    SMC_SWING_LENGTH: int = 50
    SMC_INTERNAL_LENGTH: int = 5

    # Order Blocks
    SHOW_SWING_OB: bool = True
    SHOW_INTERNAL_OB: bool = False
    OB_SHOW_LAST: int = 5
    OB_FILTER: str = "Atr"  # "Atr" or "CumulativeMeanRange"

    # Fair Value Gaps
    SHOW_FVG: bool = True
    FVG_AUTO_THRESHOLD: bool = True
    FVG_EXTEND: int = 10

    # Equal Highs/Lows
    SHOW_EQ_HL: bool = False
    EQ_BARS: int = 3
    EQ_THRESHOLD: float = 0.1

    # Structure
    SHOW_SWING_STRUCTURE: bool = True
    SHOW_INTERNAL_STRUCTURE: bool = False
    CONFLUENCE_FILTER: bool = False

    # Premium/Discount
    SHOW_PREMIUM_DISCOUNT: bool = False

    # ═══════════════════════════════════════════
    # BOT SETTINGS
    # ═══════════════════════════════════════════
    CANDLE_LIMIT: int = 500
    SLEEP_INTERVAL: int = 10  # seconds between checks
    DRY_RUN: bool = True  # paper trading
    LOG_LEVEL: str = "INFO"
    ENABLE_NOTIFICATIONS: bool = False
    TRADE_DIRECTION: str = "both"  # "long", "short", "both"
    