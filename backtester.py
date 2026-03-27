"""
backtester.py — Backtesting Engine
Simulates the strategy on historical data bar-by-bar.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Optional

from config import Config
from indicators import calculate_all
from smc import SMCAnalyzer
from risk_manager import RiskManager, Position
from strategy import Strategy

logger = logging.getLogger(__name__)


class BacktestResult:
    def __init__(self):
        self.trades: list = []
        self.equity_curve: list = []
        self.signals: list = []


class Backtester:
    """
    Historical backtesting engine.
    Simulates the DAHLAH7 strategy bar-by-bar on historical data.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.config.DRY_RUN = True  # Always dry run in backtest

    def run(
        self,
        df: pd.DataFrame,
        initial_balance: float = 10000.0,
        verbose: bool = True
    ) -> BacktestResult:
        """
        Run backtest on historical OHLCV data.

        Args:
            df: DataFrame with columns [open, high, low, close, volume]
            initial_balance: Starting balance in USDT
            verbose: Print progress
        """
        result = BacktestResult()
        strategy = Strategy(self.config)
        risk_manager = RiskManager(self.config)
        balance = initial_balance
        max_balance = initial_balance

        # Calculate all indicators once
        df = calculate_all(df, self.config)

        # Run SMC if enabled
        smc_result = None
        if self.config.SMC_ENABLED:
            smc = SMCAnalyzer(self.config)
            smc_result = smc.analyze(df)

        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        bull_signals = df['bull_raw'].values
        bear_signals = df['bear_raw'].values
        is_sideways = df['is_sideways'].values
        rf_upward = df['rf_upward'].values
        rf_downward = df['rf_downward'].values
        tt_direction = df['tt_direction'].values
        atr_risk_vals = df['atr_risk'].values

        n = len(df)
        warmup = 100  # Skip first N bars for indicator warmup

        if verbose:
            logger.info(f"🔄 Starting backtest: {n} bars, "
                        f"initial balance: ${initial_balance:,.2f}")

        for i in range(warmup, n):
            current_price = close[i]
            current_high = high[i]
            current_low = low[i]

            # Track equity
            equity = balance
            if risk_manager.has_position:
                pos = risk_manager.current_position
                if pos.side == 'long':
                    equity = balance + (current_price - pos.entry_price) * pos.amount
                else:
                    equity = balance + (pos.entry_price - current_price) * pos.amount

            result.equity_curve.append({
                'bar': i,
                'equity': equity,
                'price': current_price,
                'timestamp': df.index[i] if hasattr(df.index[i], 'strftime') else i
            })

            # Check existing position
            if risk_manager.has_position:
                should_close, reason = risk_manager.check_position(
                    current_price, current_high, current_low
                )

                if should_close:
                    pos = risk_manager.close_position(current_price, reason)
                    if pos:
                        balance += pos.pnl
                        result.trades.append({
                            'entry_bar': pos.entry_price,
                            'exit_bar': i,
                            'side': pos.side,
                            'entry': pos.entry_price,
                            'exit': current_price,
                            'pnl': pos.pnl,
                            'reason': reason,
                            'tp1_hit': pos.tp1_hit,
                            'tp2_hit': pos.tp2_hit,
                        })

            # Check for new signals
            is_bull = bull_signals[i]
            is_bear = bear_signals[i]

            # Apply filters
            signal_type = 'HOLD'
            if is_bull:
                signal_type = 'BUY'
            elif is_bear:
                signal_type = 'SELL'

            # ADX filter
            if self.config.USE_ADX_FILTER and signal_type != 'HOLD':
                if is_sideways[i]:
                    signal_type = 'HOLD'

            # Direction filter
            if signal_type == 'BUY' and self.config.TRADE_DIRECTION == 'short':
                signal_type = 'HOLD'
            if signal_type == 'SELL' and self.config.TRADE_DIRECTION == 'long':
                signal_type = 'HOLD'

            # Handle position reversal
            if risk_manager.has_position and signal_type != 'HOLD':
                pos = risk_manager.current_position
                if (signal_type == 'BUY' and pos.side == 'short') or \
                   (signal_type == 'SELL' and pos.side == 'long'):
                    closed = risk_manager.close_position(current_price, 'reverse')
                    if closed:
                        balance += closed.pnl
                        result.trades.append({
                            'exit_bar': i,
                            'side': closed.side,
                            'entry': closed.entry_price,
                            'exit': current_price,
                            'pnl': closed.pnl,
                            'reason': 'reverse',
                            'tp1_hit': closed.tp1_hit,
                            'tp2_hit': closed.tp2_hit,
                        })

            # Open new position
            if signal_type != 'HOLD' and not risk_manager.has_position:
                atr_val = atr_risk_vals[i]
                if np.isnan(atr_val):
                    continue

                atr_band = atr_val * self.config.ATR_RISK
                entry = current_price

                if signal_type == 'BUY':
                    sl = low[i] - atr_band
                    dist = entry - sl
                    tp1 = entry + dist
                    tp2 = entry + dist * 2
                    tp3 = entry + dist * 3
                    side = 'long'
                else:
                    sl = high[i] + atr_band
                    dist = sl - entry
                    tp1 = entry - dist
                    tp2 = entry - dist * 2
                    tp3 = entry - dist * 3
                    side = 'short'

                amount = risk_manager.calculate_position_size(balance, entry, sl)
                if amount > 0 and balance > 0:
                    risk_manager.open_position(side, entry, amount, sl, tp1, tp2, tp3)
                    result.signals.append({
                        'bar': i,
                        'type': signal_type,
                        'price': entry,
                        'sl': sl,
                        'tp1': tp1,
                        'tp2': tp2,
                        'tp3': tp3,
                    })

            max_balance = max(max_balance, equity)

        # Close any remaining position
        if risk_manager.has_position:
            pos = risk_manager.close_position(close[-1], 'end_of_data')
            if pos:
                balance += pos.pnl

        # Print results
        if verbose:
            self.print_report(result, initial_balance, balance, max_balance, n)

        return result

    def print_report(
        self,
        result: BacktestResult,
        initial_balance: float,
        final_balance: float,
        max_balance: float,
        total_bars: int
    ):
        """Print backtest report."""
        trades = result.trades
        total = len(trades)

        print("\n" + "=" * 70)
        print("📊 DAHLAH7 SCALPER PRO — BACKTEST REPORT")
        print("=" * 70)
        print(f"Total Bars:        {total_bars}")
        print(f"Total Trades:      {total}")

        if total == 0:
            print("No trades executed.")
            return

        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        total_pnl = sum(t['pnl'] for t in trades)
        win_pnl = sum(t['pnl'] for t in wins) if wins else 0
        loss_pnl = sum(t['pnl'] for t in losses) if losses else 0

        print(f"Wins:              {len(wins)}")
        print(f"Losses:            {len(losses)}")
        print(f"Win Rate:          {len(wins)/total*100:.1f}%")
        print(f"")
        print(f"Initial Balance:   ${initial_balance:,.2f}")
        print(f"Final Balance:     ${final_balance:,.2f}")
        print(f"Total PnL:         ${total_pnl:,.4f} ({(final_balance/initial_balance-1)*100:+.2f}%)")
        print(f"Max Balance:       ${max_balance:,.2f}")

        if loss_pnl != 0:
            pf = abs(win_pnl / loss_pnl)
            print(f"Profit Factor:     {pf:.2f}")

        if wins:
            print(f"Avg Win:           ${sum(t['pnl'] for t in wins)/len(wins):,.4f}")
        if losses:
            print(f"Avg Loss:          ${sum(t['pnl'] for t in losses)/len(losses):,.4f}")

        print(f"Max Win:           ${max((t['pnl'] for t in trades), default=0):,.4f}")
        print(f"Max Loss:          ${min((t['pnl'] for t in trades), default=0):,.4f}")

        # Drawdown
        if result.equity_curve:
            equities = [e['equity'] for e in result.equity_curve]
            peak = equities[0]
            max_dd = 0
            for eq in equities:
                peak = max(peak, eq)
                dd = (peak - eq) / peak * 100
                max_dd = max(max_dd, dd)
            print(f"Max Drawdown:      {max_dd:.2f}%")

        # TP/SL stats
        tp1_hits = sum(1 for t in trades if t.get('tp1_hit'))
        tp2_hits = sum(1 for t in trades if t.get('tp2_hit'))
        sl_hits = sum(1 for t in trades if t.get('reason') == 'stop_loss')
        reverse = sum(1 for t in trades if t.get('reason') == 'reverse')

        print(f"\n--- Exit Reasons ---")
        print(f"TP1 Hits:          {tp1_hits}")
        print(f"TP2 Hits:          {tp2_hits}")
        print(f"TP3 / Full TP:     {sum(1 for t in trades if t.get('reason') == 'tp3')}")
        print(f"Stop Loss:         {sl_hits}")
        print(f"Signal Reverse:    {reverse}")
        print("=" * 70)


def run_backtest_from_exchange(config: Config = None):
    """Convenience function: fetch data from exchange and backtest."""
    from exchange_client import ExchangeClient

    config = config or Config()
    exchange = ExchangeClient(config)

    print(f"Fetching {config.CANDLE_LIMIT} candles of {config.SYMBOL} ({config.TIMEFRAME})...")
    df = exchange.fetch_ohlcv(limit=config.CANDLE_LIMIT)

    backtester = Backtester(config)
    result = backtester.run(df, initial_balance=10000.0, verbose=True)
    return result