"""
exchange_client.py — Exchange Connection via CCXT
Supports Binance, Bybit, and other CCXT-compatible exchanges.
"""

import ccxt
import pandas as pd
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class ExchangeClient:
    """Wrapper around CCXT for exchange operations."""

    def __init__(self, config):
        self.config = config

        exchange_class = getattr(ccxt, config.EXCHANGE)

        exchange_params = {
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': config.MARKET_TYPE,
            }
        }

        if config.TESTNET:
            exchange_params['options']['sandboxMode'] = True

        self.exchange = exchange_class(exchange_params)

        if config.TESTNET:
            self.exchange.set_sandbox_mode(True)

        logger.info(
            f"Exchange initialized: {config.EXCHANGE.upper()} "
            f"({'TESTNET' if config.TESTNET else 'LIVE'}) "
            f"({config.MARKET_TYPE})"
        )

    def fetch_ohlcv(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        limit: int = 500
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candlestick data.

        Returns DataFrame with columns: timestamp, open, high, low, close, volume
        """
        symbol = symbol or self.config.SYMBOL
        timeframe = timeframe or self.config.TIMEFRAME

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df = df.astype(float)

            logger.debug(f"Fetched {len(df)} candles for {symbol} ({timeframe})")
            return df

        except Exception as e:
            logger.error(f"Error fetching OHLCV: {e}")
            raise

    def get_balance(self, currency: str = 'USDT') -> dict:
        """Get account balance."""
        try:
            balance = self.exchange.fetch_balance()
            free = balance.get('free', {}).get(currency, 0)
            used = balance.get('used', {}).get(currency, 0)
            total = balance.get('total', {}).get(currency, 0)
            return {'free': float(free), 'used': float(used), 'total': float(total)}
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return {'free': 0, 'used': 0, 'total': 0}

    def get_ticker(self, symbol: Optional[str] = None) -> dict:
        """Get current ticker info."""
        symbol = symbol or self.config.SYMBOL
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Error fetching ticker: {e}")
            return {}

    def place_market_order(
        self,
        side: str,
        amount: float,
        symbol: Optional[str] = None
    ) -> dict:
        """Place market order. side = 'buy' or 'sell'."""
        symbol = symbol or self.config.SYMBOL

        if self.config.DRY_RUN:
            ticker = self.get_ticker(symbol)
            price = ticker.get('last', 0)
            logger.info(f"[DRY RUN] {side.upper()} {amount} {symbol} @ ~{price}")
            return {
                'id': f'dry_run_{int(time.time())}',
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price,
                'status': 'filled',
                'dry_run': True
            }

        try:
            order = self.exchange.create_market_order(symbol, side, amount)
            logger.info(
                f"Market order placed: {side.upper()} {amount} {symbol} "
                f"→ ID: {order['id']}"
            )
            return order
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            raise

    def place_stop_loss(
        self,
        side: str,
        amount: float,
        stop_price: float,
        symbol: Optional[str] = None
    ) -> dict:
        """Place stop loss order."""
        symbol = symbol or self.config.SYMBOL

        if self.config.DRY_RUN:
            logger.info(f"[DRY RUN] Stop Loss: {side.upper()} {amount} {symbol} @ {stop_price}")
            return {'id': f'dry_sl_{int(time.time())}', 'dry_run': True}

        try:
            params = {'stopPrice': stop_price, 'type': 'stop_market'}
            order = self.exchange.create_order(
                symbol, 'stop_market', side, amount, None, params
            )
            logger.info(f"Stop Loss placed: {side.upper()} @ {stop_price}")
            return order
        except Exception as e:
            logger.error(f"Error placing stop loss: {e}")
            raise

    def place_take_profit(
        self,
        side: str,
        amount: float,
        tp_price: float,
        symbol: Optional[str] = None
    ) -> dict:
        """Place take profit order."""
        symbol = symbol or self.config.SYMBOL

        if self.config.DRY_RUN:
            logger.info(f"[DRY RUN] Take Profit: {side.upper()} {amount} {symbol} @ {tp_price}")
            return {'id': f'dry_tp_{int(time.time())}', 'dry_run': True}

        try:
            params = {'stopPrice': tp_price, 'type': 'take_profit_market'}
            order = self.exchange.create_order(
                symbol, 'take_profit_market', side, amount, None, params
            )
            logger.info(f"Take Profit placed: {side.upper()} @ {tp_price}")
            return order
        except Exception as e:
            logger.error(f"Error placing take profit: {e}")
            raise

    def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        """Cancel all open orders."""
        symbol = symbol or self.config.SYMBOL
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            for order in orders:
                self.exchange.cancel_order(order['id'], symbol)
            logger.info(f"Cancelled {len(orders)} orders for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            return False

    def set_leverage(self, leverage: int, symbol: Optional[str] = None) -> bool:
        """Set leverage for futures trading."""
        symbol = symbol or self.config.SYMBOL
        try:
            self.exchange.set_leverage(leverage, symbol)
            logger.info(f"Leverage set to {leverage}x for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            return False

    def get_position_info(self, symbol: Optional[str] = None) -> dict:
        """Get current position info (futures)."""
        symbol = symbol or self.config.SYMBOL
        try:
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                if pos['symbol'] == symbol and float(pos.get('contracts', 0)) > 0:
                    return pos
            return {}
        except Exception as e:
            logger.error(f"Error fetching position: {e}")
            return {}