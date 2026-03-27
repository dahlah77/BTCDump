"""
smc.py — Smart Money Concepts Module
Translasi dari bagian SMC pada Pine Script DAHLAH7.
Includes: Swing Detection, BOS/CHoCH, Order Blocks, FVG, EQH/EQL.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class SwingPoint:
    index: int
    price: float
    type: str  # 'HH', 'LH', 'HL', 'LL'
    is_high: bool


@dataclass
class StructureBreak:
    index: int
    price: float
    type: str  # 'BOS' or 'CHoCH'
    direction: str  # 'bullish' or 'bearish'
    start_index: int


@dataclass
class OrderBlock:
    top: float
    bottom: float
    left_index: int
    type: int  # 1=bullish, -1=bearish
    broken: bool = False


@dataclass
class FairValueGap:
    top: float
    bottom: float
    mid: float
    index: int
    type: str  # 'bullish' or 'bearish'
    filled: bool = False


@dataclass
class SMCResult:
    swing_highs: List[SwingPoint]
    swing_lows: List[SwingPoint]
    structure_breaks: List[StructureBreak]
    order_blocks: List[OrderBlock]
    fvgs: List[FairValueGap]
    trend: int  # 1=bullish, -1=bearish
    internal_trend: int
    strong_high: Optional[float] = None
    weak_high: Optional[float] = None
    strong_low: Optional[float] = None
    weak_low: Optional[float] = None


class SMCAnalyzer:
    """
    Smart Money Concepts Analyzer.
    Translasi akurat dari modul SMC Pine Script.
    """

    def __init__(self, config):
        self.config = config
        self.swing_length = config.SMC_SWING_LENGTH
        self.internal_length = config.SMC_INTERNAL_LENGTH
        self._reset_state()

    def _reset_state(self):
        """Reset all internal state."""
        self.trend = 0
        self.itrend = 0

        self.top_y = 0.0
        self.top_x = 0
        self.btm_y = 0.0
        self.btm_x = 0

        self.itop_y = 0.0
        self.itop_x = 0
        self.ibtm_y = 0.0
        self.ibtm_x = 0

        self.trail_up = 0.0
        self.trail_up_x = 0
        self.trail_dn = float('inf')
        self.trail_dn_x = 0

        self.top_cross = True
        self.btm_cross = True
        self.itop_cross = True
        self.ibtm_cross = True

        self.ob_list: List[OrderBlock] = []
        self.iob_list: List[OrderBlock] = []
        self.fvg_list: List[FairValueGap] = []
        self.structure_breaks: List[StructureBreak] = []
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []

    def detect_swings(
        self,
        high: np.ndarray,
        low: np.ndarray,
        length: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Pine Script's swings() function.

        swings(len) =>
            var os = 0
            upper = ta.highest(len)
            lower = ta.lowest(len)
            os := high[len] > upper ? 0 : low[len] < lower ? 1 : os[1]
            top = os == 0 and os[1] != 0 ? high[len] : 0
            btm = os == 1 and os[1] != 1 ? low[len] : 0
        """
        n = len(high)
        tops = np.zeros(n)
        btms = np.zeros(n)
        os_state = np.zeros(n, dtype=int)

        for i in range(length, n):
            # ta.highest(len) = highest high over bars [i-len+1 ... i]
            upper = np.max(high[i - length + 1: i + 1])
            # ta.lowest(len) = lowest low over bars [i-len+1 ... i]
            lower = np.min(low[i - length + 1: i + 1])

            # high[len] = high at bar i-length
            if high[i - length] > upper:
                os_state[i] = 0
            elif low[i - length] < lower:
                os_state[i] = 1
            else:
                os_state[i] = os_state[i - 1]

            # Detect swing point on transition
            if os_state[i] == 0 and os_state[i - 1] != 0:
                tops[i] = high[i - length]
            if os_state[i] == 1 and os_state[i - 1] != 1:
                btms[i] = low[i - length]

        return tops, btms

    def analyze(self, df: pd.DataFrame) -> SMCResult:
        """
        Run full SMC analysis on DataFrame.
        Processes bar-by-bar like Pine Script to maintain state.
        """
        self._reset_state()

        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        open_ = df['open'].values
        n = len(close)

        atr_200 = df['atr_200'].values if 'atr_200' in df.columns else np.full(n, np.nan)

        # Cumulative mean range (for OB filter)
        cum_range = np.cumsum(high - low)
        cmean_range = np.zeros(n)
        for i in range(n):
            cmean_range[i] = cum_range[i] / (i + 1) if i > 0 else high[0] - low[0]

        # Detect swings
        swing_tops, swing_btms = self.detect_swings(high, low, self.swing_length)
        int_tops, int_btms = self.detect_swings(high, low, self.internal_length)

        # Process bar by bar
        for i in range(max(self.swing_length, self.internal_length) + 1, n):
            self._process_bar(
                i, high, low, close, open_,
                swing_tops, swing_btms,
                int_tops, int_btms,
                atr_200, cmean_range
            )

        # Determine strong/weak highs/lows
        strong_high = self.trail_up if self.trend < 0 else None
        weak_high = self.trail_up if self.trend > 0 else None
        strong_low = self.trail_dn if self.trend > 0 else None
        weak_low = self.trail_dn if self.trend < 0 else None

        return SMCResult(
            swing_highs=self.swing_highs,
            swing_lows=self.swing_lows,
            structure_breaks=self.structure_breaks,
            order_blocks=self.ob_list + self.iob_list,
            fvgs=self.fvg_list,
            trend=self.trend,
            internal_trend=self.itrend,
            strong_high=strong_high or self.trail_up,
            weak_high=weak_high,
            strong_low=strong_low or self.trail_dn,
            weak_low=weak_low,
        )

    def _process_bar(
        self, i, high, low, close, open_,
        swing_tops, swing_btms,
        int_tops, int_btms,
        atr_200, cmean_range
    ):
        """Process single bar for SMC analysis (matches Pine Script flow)."""

        # ─── SWING HIGHS ───
        if swing_tops[i] > 0:
            top_val = swing_tops[i]
            self.top_cross = True
            txt = 'HH' if top_val > self.top_y else 'LH'
            self.swing_highs.append(SwingPoint(
                index=i - self.swing_length,
                price=top_val,
                type=txt,
                is_high=True
            ))
            self.top_y = top_val
            self.top_x = i - self.swing_length
            self.trail_up = top_val
            self.trail_up_x = i - self.swing_length

        # ─── INTERNAL SWING HIGHS ───
        if int_tops[i] > 0:
            self.itop_cross = True
            self.itop_y = int_tops[i]
            self.itop_x = i - self.internal_length

        # Trail up
        if high[i] > self.trail_up:
            self.trail_up = high[i]
            self.trail_up_x = i

        # ─── SWING LOWS ───
        if swing_btms[i] > 0:
            btm_val = swing_btms[i]
            self.btm_cross = True
            txt = 'LL' if btm_val < self.btm_y else 'HL'
            self.swing_lows.append(SwingPoint(
                index=i - self.swing_length,
                price=btm_val,
                type=txt,
                is_high=False
            ))
            self.btm_y = btm_val
            self.btm_x = i - self.swing_length
            self.trail_dn = btm_val
            self.trail_dn_x = i - self.swing_length

        # ─── INTERNAL SWING LOWS ───
        if int_btms[i] > 0:
            self.ibtm_cross = True
            self.ibtm_y = int_btms[i]
            self.ibtm_x = i - self.internal_length

        # Trail down
        if low[i] < self.trail_dn:
            self.trail_dn = low[i]
            self.trail_dn_x = i

        # ─── BULLISH BOS/CHoCH (Internal) ───
        if (close[i] > self.itop_y and self.itop_cross
                and self.top_y != self.itop_y and self.itop_y > 0):
            is_choch = self.itrend < 0
            sb_type = 'CHoCH' if is_choch else 'BOS'
            self.structure_breaks.append(StructureBreak(
                index=i, price=self.itop_y, type=sb_type,
                direction='bullish_internal',
                start_index=self.itop_x
            ))
            self.itop_cross = False
            self.itrend = 1

            if self.config.SHOW_INTERNAL_OB:
                self._detect_ob(i, high, low, close, self.itop_x, False,
                                atr_200, cmean_range, internal=True)

        # ─── BULLISH BOS/CHoCH (Swing) ───
        if close[i] > self.top_y and self.top_cross and self.top_y > 0:
            is_choch = self.trend < 0
            sb_type = 'CHoCH' if is_choch else 'BOS'
            self.structure_breaks.append(StructureBreak(
                index=i, price=self.top_y, type=sb_type,
                direction='bullish',
                start_index=self.top_x
            ))
            self.top_cross = False
            self.trend = 1

            if self.config.SHOW_SWING_OB:
                self._detect_ob(i, high, low, close, self.top_x, False,
                                atr_200, cmean_range, internal=False)

        # ─── BEARISH BOS/CHoCH (Internal) ───
        if (close[i] < self.ibtm_y and self.ibtm_cross
                and self.btm_y != self.ibtm_y and self.ibtm_y > 0):
            is_choch = self.itrend > 0
            sb_type = 'CHoCH' if is_choch else 'BOS'
            self.structure_breaks.append(StructureBreak(
                index=i, price=self.ibtm_y, type=sb_type,
                direction='bearish_internal',
                start_index=self.ibtm_x
            ))
            self.ibtm_cross = False
            self.itrend = -1

            if self.config.SHOW_INTERNAL_OB:
                self._detect_ob(i, high, low, close, self.ibtm_x, True,
                                atr_200, cmean_range, internal=True)

        # ─── BEARISH BOS/CHoCH (Swing) ───
        if close[i] < self.btm_y and self.btm_cross and self.btm_y > 0:
            is_choch = self.trend > 0
            sb_type = 'CHoCH' if is_choch else 'BOS'
            self.structure_breaks.append(StructureBreak(
                index=i, price=self.btm_y, type=sb_type,
                direction='bearish',
                start_index=self.btm_x
            ))
            self.btm_cross = False
            self.trend = -1

            if self.config.SHOW_SWING_OB:
                self._detect_ob(i, high, low, close, self.btm_x, True,
                                atr_200, cmean_range, internal=False)

        # ─── CHECK OB BREAKS ───
        self._check_ob_breaks(close[i])

        # ─── DETECT FVG ───
        if self.config.SHOW_FVG and i >= 2:
            self._detect_fvg(i, high, low, close, open_)

    def _detect_ob(self, current_idx, high, low, close, loc_idx, use_max,
                   atr_200, cmean_range, internal=False):
        """
        Pine Script's ob_coord function.
        Find the order block candle between current bar and structure point.
        """
        target_list = self.iob_list if internal else self.ob_list

        min_val = float('inf')
        max_val = 0.0
        idx = 1

        search_range = current_idx - loc_idx - 1
        if search_range < 1:
            return

        for j in range(1, min(search_range, current_idx)):
            bar_idx = current_idx - j
            if bar_idx < 0:
                break

            candle_range = high[bar_idx] - low[bar_idx]

            # OB threshold filter
            if self.config.OB_FILTER == 'Atr':
                threshold = atr_200[bar_idx] * 2 if not np.isnan(atr_200[bar_idx]) else float('inf')
            else:
                threshold = cmean_range[bar_idx] * 2

            if candle_range < threshold:
                if use_max:
                    if high[bar_idx] > max_val:
                        max_val = high[bar_idx]
                        min_val = low[bar_idx]
                        idx = j
                else:
                    if low[bar_idx] < min_val:
                        min_val = low[bar_idx]
                        max_val = high[bar_idx]
                        idx = j

        if max_val > 0 and min_val < float('inf'):
            ob = OrderBlock(
                top=max_val,
                bottom=min_val,
                left_index=current_idx - idx,
                type=-1 if use_max else 1
            )
            target_list.append(ob)

            # Keep only last N
            max_obs = self.config.OB_SHOW_LAST
            if len(target_list) > max_obs * 2:
                active = [ob for ob in target_list if not ob.broken]
                target_list.clear()
                target_list.extend(active[-max_obs:])

    def _check_ob_breaks(self, current_close):
        """Check if price breaks through order blocks."""
        for ob in self.ob_list + self.iob_list:
            if ob.broken:
                continue
            if ob.type == 1 and current_close < ob.bottom:
                ob.broken = True
            elif ob.type == -1 and current_close > ob.top:
                ob.broken = True

    def _detect_fvg(self, i, high, low, close, open_):
        """
        Fair Value Gap detection.
        Bullish FVG: low[i] > high[i-2] (gap between candle 0 and candle -2)
        Bearish FVG: high[i] < low[i-2]
        """
        if i < 2:
            return

        delta_pct = (close[i - 1] - open_[i - 1]) / open_[i - 1] * 100 if open_[i - 1] != 0 else 0

        if self.config.FVG_AUTO_THRESHOLD:
            # Auto threshold: cumulative average of abs(delta_pct) * 2
            threshold = abs(delta_pct) * 0.5  # simplified
        else:
            threshold = 0

        # Bullish FVG
        if low[i] > high[i - 2] and close[i - 1] > high[i - 2] and delta_pct > threshold:
            fvg = FairValueGap(
                top=low[i],
                bottom=high[i - 2],
                mid=(low[i] + high[i - 2]) / 2,
                index=i,
                type='bullish'
            )
            self.fvg_list.append(fvg)

        # Bearish FVG
        if high[i] < low[i - 2] and close[i - 1] < low[i - 2] and -delta_pct > threshold:
            fvg = FairValueGap(
                top=low[i - 2],
                bottom=high[i],
                mid=(low[i - 2] + high[i]) / 2,
                index=i,
                type='bearish'
            )
            self.fvg_list.append(fvg)

        # Check FVG fills
        for fvg in self.fvg_list:
            if fvg.filled:
                continue
            if fvg.type == 'bullish' and low[i] < fvg.bottom:
                fvg.filled = True
            elif fvg.type == 'bearish' and high[i] > fvg.top:
                fvg.filled = True

    def get_active_order_blocks(self) -> List[OrderBlock]:
        """Get non-broken order blocks."""
        return [ob for ob in (self.ob_list + self.iob_list) if not ob.broken]

    def get_active_fvgs(self) -> List[FairValueGap]:
        """Get non-filled FVGs."""
        return [fvg for fvg in self.fvg_list if not fvg.filled]

    def get_nearest_ob(self, price: float, direction: str) -> Optional[OrderBlock]:
        """Find nearest active order block as support/resistance."""
        active = self.get_active_order_blocks()
        if not active:
            return None

        if direction == 'support':
            # Bullish OBs below price
            candidates = [ob for ob in active if ob.type == 1 and ob.top < price]
            return max(candidates, key=lambda ob: ob.top) if candidates else None
        else:
            # Bearish OBs above price
            candidates = [ob for ob in active if ob.type == -1 and ob.bottom > price]
            return min(candidates, key=lambda ob: ob.bottom) if candidates else None