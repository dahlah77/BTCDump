"""
strategy.py — Signal Generator
Combines Supertrend signals + all filters from Pine Script.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Tuple

from indicators import calculate_all, crossover, crossunder
from smc import SMCAnalyzer, SMCResult


@dataclass
class Signal:
    type: str          # 'BUY', 'SELL', 'HOLD'
    price: float       # current close price
    entry: float       # entry price
    stop_loss: float   # stop loss price
    tp1: float         # take profit 1
    tp2: float         # take profit 2
    tp3: float         # take profit 3
    bar_index: int     # bar index of signal
    confidence: str    # 'HIGH', 'MEDIUM', 'LOW'
    filters: dict      # status of all filters
    smc: Optional[SMCResult] = None  # SMC analysis result


class Strategy:
    """
    DAHLAH7 Scalper Pro Strategy.

    Signal Logic:
        BUY  = crossover(close, supertrend)  + filters
        SELL = crossunder(close, supertrend) + filters

    Filters (optional confluence):
        1. ADX Sideways Filter: skip when ADX < threshold
        2. Range Filter Direction: confirm trend direction
        3. Trend Tracer Cloud: confirm trend direction
        4. SMC Order Blocks: confluence support/resistance

    Risk Management:
        - ATR-based Stop Loss
        - 3 Take Profit levels (1:1, 2:1, 3:1 RR)
    """

    def __init__(self, config):
        self.config = config
        self.smc_analyzer = SMCAnalyzer(config) if config.SMC_ENABLED else None
        self.last_signal_type = None
        self.last_signal_bar = -1

    def analyze(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Signal]:
        """
        Run full analysis and return signal for the last confirmed bar.

        Returns:
            df: DataFrame with all indicators
            signal: Signal object for current bar
        """
        # Calculate all indicators
        df = calculate_all(df, self.config)

        # Run SMC analysis
        smc_result = None
        if self.smc_analyzer and self.config.SMC_ENABLED:
            smc_result = self.smc_analyzer.analyze(df)

        # Generate signal on last confirmed bar (index -2, since -1 may be forming)
        signal = self._generate_signal(df, smc_result)

        return df, signal

    def _generate_signal(self, df: pd.DataFrame, smc_result: Optional[SMCResult]) -> Signal:
        """
        Generate trading signal from the last confirmed bar.
        Matches Pine Script's barstate.isconfirmed logic.
        """
        # Use second-to-last bar as "confirmed" (last bar may still be forming)
        idx = len(df) - 2
        if idx < 1:
            return self._hold_signal(df, idx)

        close = df['close'].values
        st = df['supertrend'].values

        # ─── PRIMARY SIGNAL: Supertrend Crossover/Crossunder ───
        is_bull = df['bull_raw'].values[idx]
        is_bear = df['bear_raw'].values[idx]

        # ─── FILTERS ───
        filters = self._evaluate_filters(df, idx)

        # ─── Determine signal type ───
        signal_type = 'HOLD'
        confidence = 'LOW'

        if is_bull and self.config.ENABLE_BUY_SELL:
            if self.config.TRADE_DIRECTION in ('long', 'both'):
                signal_type = 'BUY'
                confidence = self._calculate_confidence(filters, 'BUY')

        elif is_bear and self.config.ENABLE_BUY_SELL:
            if self.config.TRADE_DIRECTION in ('short', 'both'):
                signal_type = 'SELL'
                confidence = self._calculate_confidence(filters, 'SELL')

        # ─── Apply ADX Filter ───
        if self.config.USE_ADX_FILTER and signal_type != 'HOLD':
            if filters.get('is_sideways', False):
                signal_type = 'HOLD'
                confidence = 'FILTERED'

        # ─── Calculate TP/SL ───
        entry, sl, tp1, tp2, tp3 = self._calculate_levels(df, idx, signal_type)

        # Avoid duplicate signals
        if signal_type != 'HOLD':
            if signal_type == self.last_signal_type and idx - self.last_signal_bar < 3:
                signal_type = 'HOLD'
            else:
                self.last_signal_type = signal_type
                self.last_signal_bar = idx

        return Signal(
            type=signal_type,
            price=close[idx],
            entry=entry,
            stop_loss=sl,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            bar_index=idx,
            confidence=confidence,
            filters=filters,
            smc=smc_result
        )

    def _evaluate_filters(self, df: pd.DataFrame, idx: int) -> dict:
        """Evaluate all filter conditions at given bar index."""
        filters = {}

        # ADX Sideways
        filters['adx'] = float(df['adx'].values[idx]) if not np.isnan(df['adx'].values[idx]) else 0
        filters['is_sideways'] = bool(df['is_sideways'].values[idx])

        # Range Filter Direction
        filters['rf_upward'] = df['rf_upward'].values[idx] > 0
        filters['rf_downward'] = df['rf_downward'].values[idx] > 0
        filters['rf_neutral'] = not filters['rf_upward'] and not filters['rf_downward']

        # Trend Tracer
        filters['tt_bullish'] = df['tt_direction'].values[idx] == 1
        filters['tt_bearish'] = df['tt_direction'].values[idx] == -1

        # Bar color/trend
        filters['bar_color'] = df['bar_color'].values[idx]

        # Supertrend direction
        filters['st_bullish'] = df['st_direction'].values[idx] == -1
        filters['st_bearish'] = df['st_direction'].values[idx] == 1

        return filters

    def _calculate_confidence(self, filters: dict, signal_type: str) -> str:
        """
        Calculate signal confidence based on filter confluence.
        HIGH: all filters align
        MEDIUM: most filters align
        LOW: only supertrend signal
        """
        score = 0
        max_score = 0

        if self.config.USE_RANGE_FILTER:
            max_score += 1
            if signal_type == 'BUY' and filters['rf_upward']:
                score += 1
            elif signal_type == 'SELL' and filters['rf_downward']:
                score += 1

        if self.config.USE_TREND_TRACER:
            max_score += 1
            if signal_type == 'BUY' and filters['tt_bullish']:
                score += 1
            elif signal_type == 'SELL' and filters['tt_bearish']:
                score += 1

        if self.config.USE_ADX_FILTER:
            max_score += 1
            if not filters['is_sideways']:
                score += 1

        if max_score == 0:
            return 'MEDIUM'

        ratio = score / max_score
        if ratio >= 0.8:
            return 'HIGH'
        elif ratio >= 0.5:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _calculate_levels(
        self, df: pd.DataFrame, idx: int, signal_type: str
    ) -> Tuple[float, float, float, float, float]:
        """
        Calculate Entry, Stop Loss, TP1, TP2, TP3.

        Pine Script Logic:
            trigger = 1 (last was bull), 0 (last was bear)
            atrBand = atr(atrLen) * atrRisk
            atrStop = trigger==1 ? low - atrBand : high + atrBand
            entry = close
            stop = atrStop
            tp1 = (entry - stop) * 1 + entry
            tp2 = (entry - stop) * 2 + entry
            tp3 = (entry - stop) * 3 + entry
        """
        close = df['close'].values[idx]
        high = df['high'].values[idx]
        low = df['low'].values[idx]
        atr_val = df['atr_risk'].values[idx]

        if np.isnan(atr_val) or signal_type == 'HOLD':
            return close, close, close, close, close

        atr_band = atr_val * self.config.ATR_RISK
        entry = close

        if signal_type == 'BUY':
            sl = low - atr_band
            distance = entry - sl
            tp1 = entry + distance * 1
            tp2 = entry + distance * 2
            tp3 = entry + distance * 3
        elif signal_type == 'SELL':
            sl = high + atr_band
            distance = sl - entry
            tp1 = entry - distance * 1
            tp2 = entry - distance * 2
            tp3 = entry - distance * 3
        else:
            sl = entry
            tp1 = tp2 = tp3 = entry

        return entry, sl, tp1, tp2, tp3

    def _hold_signal(self, df: pd.DataFrame, idx: int) -> Signal:
        """Return a HOLD signal."""
        price = df['close'].values[idx] if idx >= 0 else 0
        return Signal(
            type='HOLD', price=price,
            entry=price, stop_loss=price,
            tp1=price, tp2=price, tp3=price,
            bar_index=idx, confidence='NONE',
            filters={}, smc=None
        )