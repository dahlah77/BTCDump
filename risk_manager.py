"""
risk_manager.py — Position Sizing & Risk Management
ATR-based TP/SL matching Pine Script logic.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Position:
    side: str           # 'long' or 'short'
    entry_price: float
    amount: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    pnl: float = 0.0
    status: str = 'open'  # 'open', 'closed'
    close_reason: str = ''


class RiskManager:
    """Manages position sizing and TP/SL monitoring."""

    def __init__(self, config):
        self.config = config
        self.current_position: Optional[Position] = None
        self.trade_history: list = []

    @property
    def has_position(self) -> bool:
        return self.current_position is not None and self.current_position.status == 'open'

    def calculate_position_size(
        self,
        balance: float,
        entry: float,
        stop_loss: float
    ) -> float:
        """
        Calculate position size based on risk percentage.

        Formula:
            risk_amount = balance * risk_per_trade
            distance = abs(entry - stop_loss)
            position_size = risk_amount / distance
        """
        risk_amount = balance * self.config.RISK_PER_TRADE
        distance = abs(entry - stop_loss)

        if distance == 0:
            logger.warning("SL distance is 0, using minimum position size")
            return risk_amount / entry * self.config.LEVERAGE

        position_size = (risk_amount / distance) * self.config.LEVERAGE

        # Apply leverage
        max_position = (balance * self.config.LEVERAGE) / entry
        position_size = min(position_size, max_position * 0.95)  # 95% max

        return round(position_size, 6)

    def open_position(
        self,
        side: str,
        entry_price: float,
        amount: float,
        stop_loss: float,
        tp1: float,
        tp2: float,
        tp3: float
    ) -> Position:
        """Open a new position."""
        if self.has_position:
            logger.warning("Already have an open position! Closing first.")
            self.close_position(entry_price, 'new_signal')

        self.current_position = Position(
            side=side,
            entry_price=entry_price,
            amount=amount,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3
        )

        logger.info(
            f"📊 Opened {side.upper()} position: "
            f"Entry={entry_price:.4f}, Amount={amount:.6f}, "
            f"SL={stop_loss:.4f}, TP1={tp1:.4f}, TP2={tp2:.4f}, TP3={tp3:.4f}"
        )

        return self.current_position

    def check_position(self, current_price: float, current_high: float, current_low: float) -> Tuple[bool, str]:
        """
        Check if position should be closed (TP/SL hit).

        Returns:
            (should_close, reason)
        """
        if not self.has_position:
            return False, ''

        pos = self.current_position

        if pos.side == 'long':
            # Check stop loss
            if current_low <= pos.stop_loss:
                return True, 'stop_loss'

            # Check take profits
            if not pos.tp1_hit and current_high >= pos.tp1:
                pos.tp1_hit = True
                # Move SL to breakeven
                pos.stop_loss = pos.entry_price
                logger.info(f"✅ TP1 hit! SL moved to breakeven ({pos.entry_price:.4f})")

            if not pos.tp2_hit and current_high >= pos.tp2:
                pos.tp2_hit = True
                # Move SL to TP1
                pos.stop_loss = pos.tp1
                logger.info(f"✅ TP2 hit! SL moved to TP1 ({pos.tp1:.4f})")

            if current_high >= pos.tp3:
                return True, 'tp3'

        elif pos.side == 'short':
            # Check stop loss
            if current_high >= pos.stop_loss:
                return True, 'stop_loss'

            # Check take profits
            if not pos.tp1_hit and current_low <= pos.tp1:
                pos.tp1_hit = True
                pos.stop_loss = pos.entry_price
                logger.info(f"✅ TP1 hit! SL moved to breakeven ({pos.entry_price:.4f})")

            if not pos.tp2_hit and current_low <= pos.tp2:
                pos.tp2_hit = True
                pos.stop_loss = pos.tp1
                logger.info(f"✅ TP2 hit! SL moved to TP1 ({pos.tp1:.4f})")

            if current_low <= pos.tp3:
                return True, 'tp3'

        return False, ''

    def close_position(self, close_price: float, reason: str) -> Optional[Position]:
        """Close current position and calculate PnL."""
        if not self.has_position:
            return None

        pos = self.current_position

        if pos.side == 'long':
            pos.pnl = (close_price - pos.entry_price) * pos.amount
        else:
            pos.pnl = (pos.entry_price - close_price) * pos.amount

        pos.status = 'closed'
        pos.close_reason = reason
        self.trade_history.append(pos)

        pnl_pct = ((close_price / pos.entry_price) - 1) * 100
        if pos.side == 'short':
            pnl_pct = -pnl_pct
        pnl_pct *= self.config.LEVERAGE

        emoji = "🟢" if pos.pnl > 0 else "🔴"
        logger.info(
            f"{emoji} Closed {pos.side.upper()} | "
            f"Entry={pos.entry_price:.4f} → Exit={close_price:.4f} | "
            f"PnL={pos.pnl:.4f} ({pnl_pct:+.2f}%) | "
            f"Reason={reason}"
        )

        self.current_position = None
        return pos

    def get_stats(self) -> dict:
        """Get trading statistics."""
        if not self.trade_history:
            return {'total_trades': 0}

        trades = self.trade_history
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in trades)
        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0

        return {
            'total_trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(sum(t.pnl for t in wins) / sum(t.pnl for t in losses)) if losses and sum(t.pnl for t in losses) != 0 else float('inf'),
            'max_win': max((t.pnl for t in trades), default=0),
            'max_loss': min((t.pnl for t in trades), default=0),
            'tp1_hits': sum(1 for t in trades if t.tp1_hit),
            'tp2_hits': sum(1 for t in trades if t.tp2_hit),
            'tp3_hits': sum(1 for t in trades if t.close_reason == 'tp3'),
            'sl_hits': sum(1 for t in trades if t.close_reason == 'stop_loss'),
        }
        