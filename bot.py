"""
bot.py — Main Trading Bot Loop
Orchestrates strategy, exchange, and risk management.
"""

import time
import logging
from datetime import datetime
from typing import Optional

from config import Config
from strategy import Strategy, Signal
from risk_manager import RiskManager
from exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class Bot:
    """
    DAHLAH7 Scalper Pro Trading Bot.

    Flow:
    1. Fetch OHLCV data
    2. Calculate indicators + SMC
    3. Generate signal (Supertrend + filters)
    4. Manage position (open/close with TP/SL)
    5. Wait for next candle
    6. Repeat
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.strategy = Strategy(self.config)
        self.risk_manager = RiskManager(self.config)
        self.exchange = ExchangeClient(self.config)
        self.running = False
        self.cycle_count = 0

    def start(self):
        """Start the bot."""
        logger.info("=" * 60)
        logger.info("🚀 DAHLAH7 Scalper Pro Bot STARTED")
        logger.info(f"📊 Symbol: {self.config.SYMBOL}")
        logger.info(f"⏱️  Timeframe: {self.config.TIMEFRAME}")
        logger.info(f"💰 Market: {self.config.MARKET_TYPE.upper()}")
        logger.info(f"🔧 Leverage: {self.config.LEVERAGE}x")
        logger.info(f"📈 Supertrend: factor={self.config.ST_FACTOR}, "
                     f"ATR={self.config.ST_ATR_LEN}")
        logger.info(f"🛡️  Risk: {self.config.RISK_PER_TRADE*100}% per trade, "
                     f"ATR Risk={self.config.ATR_RISK}")
        logger.info(f"🔍 Filters: ADX={self.config.USE_ADX_FILTER}, "
                     f"RF={self.config.USE_RANGE_FILTER}, "
                     f"TT={self.config.USE_TREND_TRACER}")
        logger.info(f"📦 SMC: {self.config.SMC_ENABLED}")
        logger.info(f"{'🧪 DRY RUN MODE' if self.config.DRY_RUN else '⚡ LIVE MODE'}")
        logger.info("=" * 60)

        # Set leverage for futures
        if self.config.MARKET_TYPE == 'future':
            self.exchange.set_leverage(self.config.LEVERAGE)

        self.running = True
        self._main_loop()

    def stop(self):
        """Stop the bot."""
        self.running = False
        logger.info("🛑 Bot stopping...")

        # Print final stats
        stats = self.risk_manager.get_stats()
        self._print_stats(stats)

    def _main_loop(self):
        """Main bot loop."""
        while self.running:
            try:
                self.cycle_count += 1
                self._run_cycle()

                # Sleep
                time.sleep(self.config.SLEEP_INTERVAL)

            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                time.sleep(30)

    def _run_cycle(self):
        """Single bot cycle: fetch → analyze → act."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 1. Fetch data
        df = self.exchange.fetch_ohlcv(limit=self.config.CANDLE_LIMIT)
        if df is None or len(df) < 100:
            logger.warning("Insufficient data, skipping cycle")
            return

        # 2. Run strategy
        df, signal = self.strategy.analyze(df)

        # 3. Get current price info
        current_price = df['close'].values[-1]
        current_high = df['high'].values[-1]
        current_low = df['low'].values[-1]

        # 4. Check existing position
        if self.risk_manager.has_position:
            should_close, reason = self.risk_manager.check_position(
                current_price, current_high, current_low
            )

            if should_close:
                self._close_position(current_price, reason)

            # If opposite signal while in position → close and reverse
            pos = self.risk_manager.current_position
            if pos and pos.status == 'open':
                if signal.type == 'BUY' and pos.side == 'short':
                    self._close_position(current_price, 'reverse_signal')
                    self._open_position(signal)
                elif signal.type == 'SELL' and pos.side == 'long':
                    self._close_position(current_price, 'reverse_signal')
                    self._open_position(signal)
        else:
            # 5. Open new position on signal
            if signal.type in ('BUY', 'SELL'):
                self._open_position(signal)

        # 6. Log status
        self._log_status(timestamp, current_price, signal)

    def _open_position(self, signal: Signal):
        """Open a position based on signal."""
        # Get balance
        balance = self.exchange.get_balance()
        available = balance.get('free', 0)

        if available <= 0:
            logger.warning("No available balance!")
            return

        # Calculate position size
        amount = self.risk_manager.calculate_position_size(
            available, signal.entry, signal.stop_loss
        )

        if amount <= 0:
            logger.warning("Position size too small")
            return

        side = 'long' if signal.type == 'BUY' else 'short'
        order_side = 'buy' if signal.type == 'BUY' else 'sell'

        # Place market order
        order = self.exchange.place_market_order(order_side, amount)

        if order:
            # Record position in risk manager
            actual_price = order.get('price', signal.entry) or signal.entry
            self.risk_manager.open_position(
                side=side,
                entry_price=actual_price,
                amount=amount,
                stop_loss=signal.stop_loss,
                tp1=signal.tp1,
                tp2=signal.tp2,
                tp3=signal.tp3
            )

            # Place SL/TP orders on exchange
            sl_side = 'sell' if side == 'long' else 'buy'
            self.exchange.place_stop_loss(sl_side, amount, signal.stop_loss)

            logger.info(
                f"{'🟢 LONG' if side == 'long' else '🔴 SHORT'} opened | "
                f"Entry: {actual_price:.4f} | Amount: {amount:.6f} | "
                f"SL: {signal.stop_loss:.4f} | "
                f"TP1: {signal.tp1:.4f} | TP2: {signal.tp2:.4f} | TP3: {signal.tp3:.4f} | "
                f"Confidence: {signal.confidence}"
            )

    def _close_position(self, price: float, reason: str):
        """Close current position."""
        pos = self.risk_manager.current_position
        if not pos:
            return

        order_side = 'sell' if pos.side == 'long' else 'buy'
        self.exchange.place_market_order(order_side, pos.amount)
        self.exchange.cancel_all_orders()
        self.risk_manager.close_position(price, reason)

    def _log_status(self, timestamp: str, price: float, signal: Signal):
        """Log current bot status."""
        pos = self.risk_manager.current_position
        pos_str = "None"
        if pos and pos.status == 'open':
            unrealized = (price - pos.entry_price) * pos.amount
            if pos.side == 'short':
                unrealized = -unrealized
            pos_str = (
                f"{pos.side.upper()} @ {pos.entry_price:.2f} "
                f"(PnL: {unrealized:+.4f})"
            )

        filters_str = ""
        if signal.filters:
            sideways = "⚠️SIDEWAYS" if signal.filters.get('is_sideways') else "✅TRENDING"
            rf = "🔼" if signal.filters.get('rf_upward') else "🔽" if signal.filters.get('rf_downward') else "➡️"
            tt = "🟢" if signal.filters.get('tt_bullish') else "🔴" if signal.filters.get('tt_bearish') else "⚪"
            adx = signal.filters.get('adx', 0)
            filters_str = f" | ADX:{adx:.1f}{sideways} RF:{rf} TT:{tt}"

        if self.cycle_count % 10 == 0 or signal.type != 'HOLD':
            logger.info(
                f"[{timestamp}] Price: {price:.2f} | "
                f"Signal: {signal.type} ({signal.confidence}) | "
                f"Position: {pos_str}{filters_str}"
            )

    def _print_stats(self, stats: dict):
        """Print trading statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("📊 TRADING STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Trades: {stats.get('total_trades', 0)}")
        logger.info(f"Wins: {stats.get('wins', 0)} | Losses: {stats.get('losses', 0)}")
        logger.info(f"Win Rate: {stats.get('win_rate', 0):.1f}%")
        logger.info(f"Total PnL: {stats.get('total_pnl', 0):.4f}")
        logger.info(f"Profit Factor: {stats.get('profit_factor', 0):.2f}")
        logger.info(f"Avg Win: {stats.get('avg_win', 0):.4f}")
        logger.info(f"Avg Loss: {stats.get('avg_loss', 0):.4f}")
        logger.info(f"TP1 Hits: {stats.get('tp1_hits', 0)}")
        logger.info(f"TP2 Hits: {stats.get('tp2_hits', 0)}")
        logger.info(f"TP3 Hits: {stats.get('tp3_hits', 0)}")
        logger.info(f"SL Hits: {stats.get('sl_hits', 0)}")
        logger.info("=" * 60)