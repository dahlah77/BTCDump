#!/usr/bin/env python3
"""
main.py — Entry Point CLI
DAHLAH7 Scalper Pro Trading Bot

Usage:
    python main.py                   # Run live bot (dry run)
    python main.py --live            # Run live bot (real trading)
    python main.py --backtest        # Run backtest
    python main.py --backtest --tf 1h --symbol ETH/USDT
"""

import argparse
import sys

from config import Config
from utils import setup_logger, print_banner


def parse_args():
    parser = argparse.ArgumentParser(
        description='DAHLAH7 Scalper Pro Trading Bot'
    )

    parser.add_argument('--backtest', action='store_true',
                        help='Run backtesting mode')
    parser.add_argument('--live', action='store_true',
                        help='Enable live trading (disables dry run)')
    parser.add_argument('--symbol', type=str, default=None,
                        help='Trading pair (e.g., BTC/USDT)')
    parser.add_argument('--tf', type=str, default=None,
                        help='Timeframe (e.g., 1m, 5m, 15m, 1h, 4h)')
    parser.add_argument('--exchange', type=str, default=None,
                        help='Exchange (binance, bybit, etc.)')
    parser.add_argument('--leverage', type=int, default=None,
                        help='Leverage for futures')
    parser.add_argument('--balance', type=float, default=10000,
                        help='Initial balance for backtesting')
    parser.add_argument('--bars', type=int, default=500,
                        help='Number of candles to fetch')

    # Strategy params
    parser.add_argument('--st-factor', type=float, default=None,
                        help='Supertrend factor (default: 7)')
    parser.add_argument('--st-atr', type=int, default=None,
                        help='Supertrend ATR length (default: 10)')
    parser.add_argument('--atr-risk', type=int, default=None,
                        help='ATR Risk multiplier (default: 3)')
    parser.add_argument('--adx-threshold', type=int, default=None,
                        help='ADX sideways threshold (default: 15)')

    # Filters
    parser.add_argument('--no-adx', action='store_true',
                        help='Disable ADX filter')
    parser.add_argument('--no-rf', action='store_true',
                        help='Disable Range Filter')
    parser.add_argument('--no-tt', action='store_true',
                        help='Disable Trend Tracer')
    parser.add_argument('--no-smc', action='store_true',
                        help='Disable SMC analysis')
    parser.add_argument('--direction', type=str, default=None,
                        choices=['long', 'short', 'both'],
                        help='Trade direction')

    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    return parser.parse_args()


def build_config(args) -> Config:
    """Build config from CLI arguments."""
    config = Config()

    if args.symbol:
        config.SYMBOL = args.symbol
    if args.tf:
        config.TIMEFRAME = args.tf
    if args.exchange:
        config.EXCHANGE = args.exchange
    if args.leverage:
        config.LEVERAGE = args.leverage
    if args.bars:
        config.CANDLE_LIMIT = args.bars

    # Strategy params
    if args.st_factor:
        config.ST_FACTOR = args.st_factor
    if args.st_atr:
        config.ST_ATR_LEN = args.st_atr
    if args.atr_risk:
        config.ATR_RISK = args.atr_risk
    if args.adx_threshold:
        config.ADX_SIDEWAYS_THRESHOLD = args.adx_threshold

    # Filters
    if args.no_adx:
        config.USE_ADX_FILTER = False
    if args.no_rf:
        config.USE_RANGE_FILTER = False
    if args.no_tt:
        config.USE_TREND_TRACER = False
    if args.no_smc:
        config.SMC_ENABLED = False
    if args.direction:
        config.TRADE_DIRECTION = args.direction

    # Live mode
    if args.live:
        config.DRY_RUN = False
    else:
        config.DRY_RUN = True

    if args.debug:
        config.LOG_LEVEL = 'DEBUG'

    return config


def main():
    args = parse_args()
    config = build_config(args)

    # Setup
    print_banner()
    logger = setup_logger('dahlah7', config.LOG_LEVEL)

    # Also configure child loggers
    for module in ['indicators', 'strategy', 'smc', 'risk_manager',
                    'exchange_client', 'bot', 'backtester']:
        mod_logger = setup_logger(module, config.LOG_LEVEL)

    if args.backtest:
        # ═══════════════════════════
        # BACKTEST MODE
        # ═══════════════════════════
        logger.info("🔬 Starting BACKTEST mode...")
        from backtester import run_backtest_from_exchange
        run_backtest_from_exchange(config)

    else:
        # ═══════════════════════════
        # LIVE / DRY RUN MODE
        # ═══════════════════════════
        if not config.DRY_RUN:
            print("\n⚠️  WARNING: LIVE TRADING MODE ⚠️")
            print("Real money will be used. Are you sure? (yes/no)")
            confirm = input("> ").strip().lower()
            if confirm != 'yes':
                print("Aborted.")
                sys.exit(0)

        from bot import Bot
        bot = Bot(config)
        bot.start()


if __name__ == '__main__':
    main()