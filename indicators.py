"""
indicators.py — Semua indikator teknikal dari Pine Script DAHLAH7.
Setiap fungsi di-translasi akurat dari Pine Script ke Python/NumPy/Pandas.
"""

import numpy as np
import pandas as pd
from typing import Tuple


# ╔═══════════════════════════════════════════════════════════════╗
# ║  HELPER FUNCTIONS                                             ║
# ╚═══════════════════════════════════════════════════════════════╝

def pine_rma(series: np.ndarray, period: int) -> np.ndarray:
    """
    Pine Script's RMA (Wilder's Moving Average).
    rma = (value + (period-1) * rma[1]) / period
    Initialized with SMA for first 'period' bars.
    """
    n = len(series)
    result = np.full(n, np.nan)

    if n < period:
        return result

    # Initialize with SMA
    result[period - 1] = np.mean(series[:period])

    # Apply RMA formula
    alpha = 1.0 / period
    for i in range(period, n):
        result[i] = alpha * series[i] + (1 - alpha) * result[i - 1]

    return result


def pine_ema(series: np.ndarray, period: int) -> np.ndarray:
    """
    Pine Script's EMA.
    Initialized with SMA, then applies EMA formula.
    """
    n = len(series)
    result = np.full(n, np.nan)

    if n < period:
        return result

    result[period - 1] = np.mean(series[:period])
    multiplier = 2.0 / (period + 1)

    for i in range(period, n):
        result[i] = (series[i] - result[i - 1]) * multiplier + result[i - 1]

    return result


def pine_sma(series: np.ndarray, period: int) -> np.ndarray:
    """Pine Script's SMA."""
    s = pd.Series(series)
    return s.rolling(window=period, min_periods=period).mean().values


def pine_wma(series: np.ndarray, period: int) -> np.ndarray:
    """Pine Script's WMA (Weighted Moving Average)."""
    n = len(series)
    result = np.full(n, np.nan)
    weights = np.arange(1, period + 1, dtype=float)
    weight_sum = weights.sum()

    for i in range(period - 1, n):
        window = series[i - period + 1: i + 1]
        result[i] = np.sum(window * weights) / weight_sum

    return result


def crossover(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pine Script's ta.crossover: a crosses above b."""
    n = len(a)
    result = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if not np.isnan(a[i]) and not np.isnan(b[i]) and not np.isnan(a[i-1]) and not np.isnan(b[i-1]):
            result[i] = (a[i] > b[i]) and (a[i - 1] <= b[i - 1])
    return result


def crossunder(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pine Script's ta.crossunder: a crosses below b."""
    n = len(a)
    result = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if not np.isnan(a[i]) and not np.isnan(b[i]) and not np.isnan(a[i-1]) and not np.isnan(b[i-1]):
            result[i] = (a[i] < b[i]) and (a[i - 1] >= b[i - 1])
    return result


# ╔═══════════════════════════════════════════════════════════════╗
# ║  TRUE RANGE & ATR                                             ║
# ╚═══════════════════════════════════════════════════════════════╝

def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Calculate True Range."""
    n = len(high)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]

    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    return tr


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """
    Pine Script's ta.atr(period) = rma(tr, period)
    """
    tr = true_range(high, low, close)
    return pine_rma(tr, period)


# ╔═══════════════════════════════════════════════════════════════╗
# ║  SUPERTREND (Core Signal Generator)                           ║
# ║  Pine: f_supertrend(close, nsensitivity * 7, 10)              ║
# ╚═══════════════════════════════════════════════════════════════╝

def supertrend(
    df: pd.DataFrame,
    sensitivity: float = 1.0,
    factor: float = 7.0,
    atr_len: int = 10
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Exact translation of Pine Script's f_supertrend function.

    Returns:
        supertrend_values: array of supertrend line values
        direction: array of direction (-1=bullish, 1=bearish)
    """
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    n = len(close)

    actual_factor = sensitivity * factor  # 1.0 * 7.0 = 7.0

    # Calculate ATR using Pine's RMA
    atr_values = atr(high, low, close, atr_len)

    upper_band = np.zeros(n)
    lower_band = np.zeros(n)
    direction = np.ones(n, dtype=int)  # 1 = bearish default
    st = np.zeros(n)

    for i in range(n):
        if np.isnan(atr_values[i]):
            upper_band[i] = np.nan
            lower_band[i] = np.nan
            direction[i] = 1
            st[i] = np.nan
            continue

        # Basic bands
        basic_upper = close[i] + actual_factor * atr_values[i]
        basic_lower = close[i] - actual_factor * atr_values[i]

        # First valid bar
        if i == 0 or np.isnan(lower_band[i - 1]):
            lower_band[i] = basic_lower
            upper_band[i] = basic_upper
            direction[i] = 1
            st[i] = upper_band[i]
            continue

        prev_lower = lower_band[i - 1]
        prev_upper = upper_band[i - 1]

        # Pine: lowerBand := lowerBand > prevLowerBand or close[1] < prevLowerBand
        #                     ? lowerBand : prevLowerBand
        if basic_lower > prev_lower or close[i - 1] < prev_lower:
            lower_band[i] = basic_lower
        else:
            lower_band[i] = prev_lower

        # Pine: upperBand := upperBand < prevUpperBand or close[1] > prevUpperBand
        #                     ? upperBand : prevUpperBand
        if basic_upper < prev_upper or close[i - 1] > prev_upper:
            upper_band[i] = basic_upper
        else:
            upper_band[i] = prev_upper

        # Direction logic
        prev_st = st[i - 1]
        prev_atr = atr_values[i - 1] if i > 0 else np.nan

        if np.isnan(prev_atr):
            direction[i] = 1
        elif prev_st == upper_band[i - 1]:
            # Was bearish → check if should flip
            direction[i] = -1 if close[i] > upper_band[i] else 1
        else:
            # Was bullish → check if should flip
            direction[i] = 1 if close[i] < lower_band[i] else -1

        # Supertrend value
        st[i] = lower_band[i] if direction[i] == -1 else upper_band[i]

    return st, direction


# ╔═══════════════════════════════════════════════════════════════╗
# ║  RANGE FILTER (Trend Cloud)                                   ║
# ║  Pine: smoothrng(close, 22, 6) → rngfilt(close, smrng)        ║
# ╚═══════════════════════════════════════════════════════════════╝

def smooth_range(series: np.ndarray, period: int = 22, multiplier: float = 6.0) -> np.ndarray:
    """
    Pine Script's smoothrng function.
    wper = period * 2 - 1
    avrng = ema(abs(x - x[1]), period)
    smoothrng = ema(avrng, wper) * multiplier
    """
    n = len(series)
    abs_change = np.zeros(n)
    abs_change[0] = 0
    for i in range(1, n):
        abs_change[i] = abs(series[i] - series[i - 1])

    wper = period * 2 - 1
    avrng = pine_ema(abs_change, period)
    smrng = pine_ema(avrng, wper) * multiplier

    return smrng


def range_filter(series: np.ndarray, smrng: np.ndarray) -> np.ndarray:
    """
    Pine Script's rngfilt function.
    Adaptive range filter that acts as dynamic support/resistance.
    """
    n = len(series)
    rngf = np.zeros(n)
    rngf[0] = series[0]

    for i in range(1, n):
        if np.isnan(smrng[i]):
            rngf[i] = rngf[i - 1]
            continue

        if series[i] > rngf[i - 1]:
            rngf[i] = max(rngf[i - 1], series[i] - smrng[i])
        else:
            rngf[i] = min(rngf[i - 1], series[i] + smrng[i])

    return rngf


def range_filter_direction(filt: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate upward/downward counters from range filter.

    Pine:
        upward := filt > filt[1] ? nz(upward[1]) + 1 : filt < filt[1] ? 0 : nz(upward[1])
        downward := filt < filt[1] ? nz(downward[1]) + 1 : filt > filt[1] ? 0 : nz(downward[1])
    """
    n = len(filt)
    upward = np.zeros(n)
    downward = np.zeros(n)

    for i in range(1, n):
        if filt[i] > filt[i - 1]:
            upward[i] = upward[i - 1] + 1
            downward[i] = 0
        elif filt[i] < filt[i - 1]:
            downward[i] = downward[i - 1] + 1
            upward[i] = 0
        else:
            upward[i] = upward[i - 1]
            downward[i] = downward[i - 1]

    return upward, downward


# ╔═══════════════════════════════════════════════════════════════╗
# ║  TREND TRACER CLOUD                                           ║
# ║  Pine: Two range filters (22,9) and (15,5), filled between    ║
# ╚═══════════════════════════════════════════════════════════════╝

def trend_tracer(
    close: np.ndarray,
    period1: int = 22, mult1: float = 9.0,
    period2: int = 15, mult2: float = 5.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Two range filters → cloud.
    Returns: filt1, filt2, trend_direction (1=bullish, -1=bearish)
    filt1 > filt2 → bearish (red), filt1 <= filt2 → bullish (green)
    """
    smrng1 = smooth_range(close, period1, mult1)
    smrng2 = smooth_range(close, period2, mult2)
    filt1 = range_filter(close, smrng1)
    filt2 = range_filter(close, smrng2)

    n = len(close)
    trend_dir = np.zeros(n, dtype=int)
    for i in range(n):
        if not np.isnan(filt1[i]) and not np.isnan(filt2[i]):
            trend_dir[i] = -1 if filt1[i] > filt2[i] else 1  # -1=bearish, 1=bullish
        else:
            trend_dir[i] = 0

    return filt1, filt2, trend_dir


# ╔═══════════════════════════════════════════════════════════════╗
# ║  ADX (Average Directional Index)                               ║
# ║  Pine: adxlen=15, dilen=15, sidewaysThreshold=15               ║
# ╚═══════════════════════════════════════════════════════════════╝

def calculate_adx(
    df: pd.DataFrame,
    di_len: int = 15,
    adx_len: int = 15
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Exact translation of Pine Script's ADX calculation.

    Returns:
        adx_values: ADX line
        plus_di: +DI
        minus_di: -DI
    """
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    n = len(close)

    # Directional Movement
    up = np.zeros(n)
    down = np.zeros(n)
    for i in range(1, n):
        up[i] = high[i] - high[i - 1]
        down[i] = -(low[i] - low[i - 1])

    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(n):
        plus_dm[i] = up[i] if (up[i] > down[i] and up[i] > 0) else 0
        minus_dm[i] = down[i] if (down[i] > up[i] and down[i] > 0) else 0

    # True Range with RMA
    tr = true_range(high, low, close)
    tr_rma = pine_rma(tr, di_len)

    # +DI and -DI
    plus_di_raw = pine_rma(plus_dm, di_len)
    minus_di_raw = pine_rma(minus_dm, di_len)

    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    for i in range(n):
        if not np.isnan(tr_rma[i]) and tr_rma[i] != 0:
            plus_di[i] = 100 * plus_di_raw[i] / tr_rma[i]
            minus_di[i] = 100 * minus_di_raw[i] / tr_rma[i]

    # fixnan equivalent (forward fill)
    for i in range(1, n):
        if plus_di[i] == 0 and not np.isnan(plus_di[i - 1]):
            plus_di[i] = plus_di[i - 1]
        if minus_di[i] == 0 and not np.isnan(minus_di[i - 1]):
            minus_di[i] = minus_di[i - 1]

    # ADX
    dx = np.zeros(n)
    for i in range(n):
        di_sum = plus_di[i] + minus_di[i]
        if di_sum != 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / di_sum

    adx_values = pine_rma(dx, adx_len)

    return adx_values, plus_di, minus_di


def is_sideways(adx_values: np.ndarray, threshold: int = 15) -> np.ndarray:
    """Check if market is sideways based on ADX threshold."""
    result = np.zeros(len(adx_values), dtype=bool)
    for i in range(len(adx_values)):
        if not np.isnan(adx_values[i]):
            result[i] = adx_values[i] < threshold
    return result


# ╔═══════════════════════════════════════════════════════════════╗
# ║  HULL MOVING AVERAGE                                          ║
# ║  Pine: tclength=600                                            ║
# ║  hullma = wma(2*wma(close,n/2)-wma(close,n), sqrt(n))         ║
# ╚═══════════════════════════════════════════════════════════════╝

def hull_ma(series: np.ndarray, period: int = 600) -> np.ndarray:
    """Hull Moving Average."""
    half_period = period // 2
    sqrt_period = int(np.floor(np.sqrt(period)))

    wma1 = pine_wma(series, half_period)
    wma2 = pine_wma(series, period)

    diff = np.zeros(len(series))
    for i in range(len(series)):
        if not np.isnan(wma1[i]) and not np.isnan(wma2[i]):
            diff[i] = 2 * wma1[i] - wma2[i]
        else:
            diff[i] = np.nan

    return pine_wma(diff, sqrt_period)


# ╔═══════════════════════════════════════════════════════════════╗
# ║  EMAs & SMAs (Volume Sensitivity)                              ║
# ╚═══════════════════════════════════════════════════════════════╝

def calculate_emas(df: pd.DataFrame, vol_sensitivity: int = 3) -> dict:
    """
    Pine:
        ohlc4 = (open+high+low+close)/4
        ema1 = ema(ohlc4, 5*volSen)  → period 15
        ema2 = ema(ohlc4, 9*volSen)  → period 27
        ema3 = ema(ohlc4, 13*volSen) → period 39
        ema4 = ema(ohlc4, 34*volSen) → period 102
        ema5 = ema(ohlc4, 50*volSen) → period 150
    """
    ohlc4 = (df['open'].values + df['high'].values +
             df['low'].values + df['close'].values) / 4

    periods = [5, 9, 13, 34, 50]
    emas = {}
    for p in periods:
        actual_period = p * vol_sensitivity
        emas[f'ema_{actual_period}'] = pine_ema(ohlc4, actual_period)

    return emas


def calculate_smas(close: np.ndarray, fast: int = 8, slow: int = 9) -> Tuple[np.ndarray, np.ndarray]:
    """
    Pine: sma4_strong = ta.sma(close, 8), sma5_strong = ta.sma(close, 9)
    """
    return pine_sma(close, fast), pine_sma(close, slow)


# ╔═══════════════════════════════════════════════════════════════╗
# ║  MASTER FUNCTION: Calculate All Indicators                     ║
# ╚═══════════════════════════════════════════════════════════════╝

def calculate_all(df: pd.DataFrame, config) -> pd.DataFrame:
    """
    Calculate ALL indicators and add as columns to DataFrame.
    Returns DataFrame with all indicator columns added.
    """
    df = df.copy()
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values

    # ─── Supertrend ───
    st_values, st_dir = supertrend(
        df, config.ST_SENSITIVITY, config.ST_FACTOR, config.ST_ATR_LEN
    )
    df['supertrend'] = st_values
    df['st_direction'] = st_dir  # -1=bullish, 1=bearish

    # ─── Buy/Sell Signals ───
    df['bull_raw'] = crossover(close, st_values)
    df['bear_raw'] = crossunder(close, st_values)

    # ─── ATR for Risk Management ───
    df['atr_risk'] = atr(high, low, close, config.ATR_LEN)

    # ─── ATR Band / Stop ───
    atr_band = df['atr_risk'].values * config.ATR_RISK

    # Determine trigger (last signal direction)
    trigger = np.zeros(len(close), dtype=int)
    last_bull = -1
    last_bear = -1
    for i in range(len(close)):
        if df['bull_raw'].values[i]:
            last_bull = i
        if df['bear_raw'].values[i]:
            last_bear = i

        if last_bull >= 0 and (last_bear < 0 or last_bull > last_bear):
            trigger[i] = 1  # last signal was bull
        elif last_bear >= 0:
            trigger[i] = 0  # last signal was bear

    df['trigger'] = trigger

    # ATR Stop
    atr_stop = np.zeros(len(close))
    for i in range(len(close)):
        if not np.isnan(atr_band[i]):
            atr_stop[i] = (low[i] - atr_band[i]) if trigger[i] == 1 else (high[i] + atr_band[i])
        else:
            atr_stop[i] = np.nan
    df['atr_stop'] = atr_stop

    # ─── Range Filter ───
    smrng = smooth_range(close, config.RF_PERIOD, config.RF_MULTIPLIER)
    filt = range_filter(close, smrng)
    upw, dnw = range_filter_direction(filt)
    df['range_filter'] = filt
    df['rf_upward'] = upw
    df['rf_downward'] = dnw

    # ─── Trend Tracer ───
    tt_f1, tt_f2, tt_dir = trend_tracer(
        close, config.TT_PERIOD1, config.TT_MULT1,
        config.TT_PERIOD2, config.TT_MULT2
    )
    df['trend_tracer_1'] = tt_f1
    df['trend_tracer_2'] = tt_f2
    df['tt_direction'] = tt_dir  # 1=bullish, -1=bearish

    # ─── ADX ───
    adx_vals, plus_di, minus_di = calculate_adx(df, config.DI_LEN, config.ADX_LEN)
    df['adx'] = adx_vals
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    df['is_sideways'] = is_sideways(adx_vals, config.ADX_SIDEWAYS_THRESHOLD)

    # ─── EMAs ───
    emas = calculate_emas(df, config.VOL_SENSITIVITY)
    for name, values in emas.items():
        df[name] = values

    # ─── SMAs ───
    sma_fast, sma_slow = calculate_smas(close, config.SMA_FAST, config.SMA_SLOW)
    df['sma_fast'] = sma_fast
    df['sma_slow'] = sma_slow

    # ─── ATR 30 (for label placement, also useful) ───
    df['atr_30'] = atr(high, low, close, 30)

    # ─── ATR 200 (for OB filter in SMC) ───
    df['atr_200'] = atr(high, low, close, 200)

    # ─── Bar Color (trend indicator) ───
    bar_color = np.full(len(close), 'neutral', dtype=object)
    for i in range(len(close)):
        if df['is_sideways'].values[i]:
            bar_color[i] = 'sideways'  # purple
        elif close[i] > st_values[i] if not np.isnan(st_values[i]) else False:
            bar_color[i] = 'bullish'   # green
        else:
            bar_color[i] = 'bearish'   # red
    df['bar_color'] = bar_color

    return df