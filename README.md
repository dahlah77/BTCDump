# DAHLAH7 👑 Scalper Pro 👑 (NO REPAINT) — Python Bot

Translasi lengkap dari Pine Script DAHLAH7 Scalper Pro ke Python trading bot.

## Features

| Component | Pine Script | Python |
|-----------|------------|--------|
| Supertrend Signal | ✅ `f_supertrend(close, 7, 10)` | ✅ `indicators.supertrend()` |
| Range Filter Cloud | ✅ `smoothrng + rngfilt` | ✅ `indicators.range_filter()` |
| Trend Tracer Cloud | ✅ Dual range filter fill | ✅ `indicators.trend_tracer()` |
| ADX Sideways Filter | ✅ `adx < 15` | ✅ `indicators.calculate_adx()` |
| ATR-based TP/SL | ✅ 3 TP levels + SL | ✅ `risk_manager.py` |
| Hull MA | ✅ `tclength=600` | ✅ `indicators.hull_ma()` |
| EMA Suite | ✅ 5 EMAs on ohlc4 | ✅ `indicators.calculate_emas()` |
| SMC: BOS/CHoCH | ✅ Swing + Internal | ✅ `smc.py` |
| SMC: Order Blocks | ✅ Swing + Internal OB | ✅ `smc.py` |
| SMC: Fair Value Gaps | ✅ Bullish/Bearish FVG | ✅ `smc.py` |
| SMC: EQH/EQL | ✅ Equal Highs/Lows | ✅ `smc.py` |
| NO REPAINT | ✅ `barstate.isconfirmed` | ✅ Uses confirmed bars only |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup API keys
cp .env.example .env
# Edit .env with your API keys

# 3. Run backtest
python main.py --backtest --symbol BTC/USDT --tf 5m

# 4. Run dry run (paper trading)
python main.py --symbol BTC/USDT --tf 5m

# 5. Run live
python main.py --live --symbol BTC/USDT --tf 5m