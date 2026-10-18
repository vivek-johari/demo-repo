"""Compare buy-and-hold with a simple moving-average strategy on one price series."""

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from analyze_returns import Price, load_prices


EquityRow = Tuple[
    date, float, Optional[float], Optional[float], int, float, float, int, float, float
]
TradeRow = Tuple[
    Optional[date], date, str, float, int, float, float, float, int, str, str
]


class BacktestResult(NamedTuple):
    equity_rows: List[EquityRow]
    trades: List[TradeRow]
    summary: Dict[str, object]


def moving_averages(
    prices: List[Price], window: int
) -> List[Optional[float]]:
    """Return each trailing average; early dates are None until a full window exists."""
    averages = []
    for index in range(len(prices)):
        if index + 1 < window:
            averages.append(None)
        else:
            window_prices = prices[index + 1 - window : index + 1]
            averages.append(
                sum(price for _, price in window_prices) / float(window)
            )
    return averages


def _max_drawdown(equity_values: List[float], starting_cash: float) -> float:
    """Find the largest percentage fall from any earlier portfolio high."""
    highest_value = starting_cash
    largest_drop = 0.0
    for value in equity_values:
        highest_value = max(highest_value, value)
        if highest_value > 0:
            largest_drop = max(largest_drop, (highest_value - value) / highest_value)
    return largest_drop * 100


def run_backtest(
    prices: List[Price],
    short_window: int = 20,
    long_window: int = 50,
    initial_cash: float = 100000.0,
    fee_rate: float = 0.001,
) -> BacktestResult:
    """Simulate long-only whole-share trades and a buy-and-hold benchmark.

    A crossover is detected after a day's close and executed at the next
    available day's close. This is a simple close-only approximation, not a
    claim about the price an actual order could receive.
    """
    if short_window < 1 or long_window < 2:
        raise ValueError("Moving-average windows must be positive.")
    if short_window >= long_window:
        raise ValueError("The short window must be smaller than the long window.")
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("Initial cash must be a finite number above zero.")
    if not math.isfinite(fee_rate) or fee_rate < 0 or fee_rate >= 1:
        raise ValueError("Fee rate must be at least 0 and less than 1.")
    if len(prices) < long_window + 1:
        raise ValueError(
            "Need at least {} price rows to test a {}-day average crossover.".format(
                long_window + 1, long_window
            )
        )

    short_averages = moving_averages(prices, short_window)
    long_averages = moving_averages(prices, long_window)

    # The benchmark buys as many whole shares as it can afford on the first day.
    first_price = prices[0][1]
    buy_hold_shares = int(initial_cash / (first_price * (1 + fee_rate)))
    buy_hold_cash = initial_cash - buy_hold_shares * first_price * (1 + fee_rate)

    cash = initial_cash
    shares = 0
    pending_order: Optional[Tuple[date, str, str]] = None
    equity_rows: List[EquityRow] = []
    trades: List[TradeRow] = []

    for index, (trading_date, close) in enumerate(prices):
        # Fill yesterday's signal today; using today's close to create today's
        # signal would accidentally let the simulation see the future.
        if pending_order is not None:
            signal_date, action, reason = pending_order
            if action == "BUY":
                quantity = int(cash / (close * (1 + fee_rate)))
                notional = quantity * close
                fee = notional * fee_rate
                if quantity > 0:
                    cash -= notional + fee
                    shares += quantity
                    status = "filled"
                    detail = reason
                else:
                    fee = 0.0
                    status = "skipped"
                    detail = "Not enough cash to buy one share."
            else:
                quantity = shares
                notional = quantity * close
                fee = notional * fee_rate
                if quantity > 0:
                    cash += notional - fee
                    shares = 0
                    status = "filled"
                    detail = reason
                else:
                    fee = 0.0
                    status = "skipped"
                    detail = "No shares to sell."

            trades.append(
                (
                    trading_date,
                    signal_date,
                    action,
                    close,
                    quantity,
                    notional,
                    fee,
                    cash,
                    shares,
                    status,
                    detail,
                )
            )
            pending_order = None

        strategy_equity = cash + shares * close
        buy_hold_equity = buy_hold_cash + buy_hold_shares * close
        equity_rows.append(
            (
                trading_date,
                close,
                short_averages[index],
                long_averages[index],
                shares,
                cash,
                strategy_equity,
                buy_hold_shares,
                buy_hold_cash,
                buy_hold_equity,
            )
        )

        # A crossover is only knowable after the current day's closing price.
        if index == 0 or short_averages[index - 1] is None:
            continue
        short_today = short_averages[index]
        long_today = long_averages[index]
        short_yesterday = short_averages[index - 1]
        long_yesterday = long_averages[index - 1]
        if (
            short_today is None
            or long_today is None
            or short_yesterday is None
            or long_yesterday is None
        ):
            continue

        crossed_up = short_yesterday <= long_yesterday and short_today > long_today
        crossed_down = short_yesterday >= long_yesterday and short_today < long_today
        if crossed_up and shares == 0 and pending_order is None:
            pending_order = (trading_date, "BUY", "Short average crossed above long average.")
        elif crossed_down and shares > 0 and pending_order is None:
            pending_order = (trading_date, "SELL", "Short average crossed below long average.")

    # The last day's signal has no later price row on which to simulate a fill.
    if pending_order is not None:
        signal_date, action, reason = pending_order
        trades.append(
            (
                None,
                signal_date,
                action,
                0.0,
                0,
                0.0,
                0.0,
                cash,
                shares,
                "unfilled",
                "No later price row to execute this signal. " + reason,
            )
        )

    strategy_values = [row[6] for row in equity_rows]
    benchmark_values = [row[9] for row in equity_rows]
    elapsed_days = (prices[-1][0] - prices[0][0]).days

    def annualized_return(final_value: float) -> Optional[float]:
        # Annualizing a short sample can turn a tiny move into a misleadingly huge rate.
        if elapsed_days < 365 or final_value <= 0:
            return None
        return ((final_value / initial_cash) ** (365.25 / elapsed_days) - 1) * 100

    summary: Dict[str, object] = {
        "start_date": prices[0][0].isoformat(),
        "end_date": prices[-1][0].isoformat(),
        "price_rows": len(prices),
        "initial_cash": round(initial_cash, 2),
        "short_window": short_window,
        "long_window": long_window,
        "fee_rate_percent": round(fee_rate * 100, 6),
        "strategy_final_equity": round(strategy_values[-1], 2),
        "strategy_total_return_percent": round(
            (strategy_values[-1] / initial_cash - 1) * 100, 6
        ),
        "strategy_annualized_return_percent": _rounded_annualized_return(
            annualized_return(strategy_values[-1])
        ),
        "strategy_max_drawdown_percent": round(
            _max_drawdown(strategy_values, initial_cash), 6
        ),
        "strategy_filled_trades": sum(1 for trade in trades if trade[9] == "filled"),
        "strategy_skipped_trades": sum(1 for trade in trades if trade[9] == "skipped"),
        "strategy_unfilled_signals": sum(
            1 for trade in trades if trade[9] == "unfilled"
        ),
        "strategy_ending_shares": shares,
        "buy_and_hold_final_equity": round(benchmark_values[-1], 2),
        "buy_and_hold_total_return_percent": round(
            (benchmark_values[-1] / initial_cash - 1) * 100, 6
        ),
        "buy_and_hold_annualized_return_percent": _rounded_annualized_return(
            annualized_return(benchmark_values[-1])
        ),
        "buy_and_hold_max_drawdown_percent": round(
            _max_drawdown(benchmark_values, initial_cash), 6
        ),
        "buy_and_hold_shares": buy_hold_shares,
        "fees_included": True,
        "execution_assumption": "Signal after close; fill at next available close.",
    }
    return BacktestResult(equity_rows, trades, summary)


def _rounded_annualized_return(value: Optional[float]) -> Optional[float]:
    """Round annualized return when the sample is long enough to report one."""
    return None if value is None else round(value, 6)


def write_results(output_dir: Path, result: BacktestResult) -> None:
    """Save daily portfolio values, simulated order fills, and summary metrics."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "equity.csv").open(
        "w", newline="", encoding="utf-8"
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "Date",
                "Price",
                "Short Average",
                "Long Average",
                "Strategy Shares",
                "Strategy Cash",
                "Strategy Equity",
                "Buy And Hold Shares",
                "Buy And Hold Cash",
                "Buy And Hold Equity",
            ]
        )
        for row in result.equity_rows:
            writer.writerow(
                [
                    row[0].isoformat(),
                    "{:.6f}".format(row[1]),
                    "" if row[2] is None else "{:.6f}".format(row[2]),
                    "" if row[3] is None else "{:.6f}".format(row[3]),
                    row[4],
                    "{:.2f}".format(row[5]),
                    "{:.2f}".format(row[6]),
                    row[7],
                    "{:.2f}".format(row[8]),
                    "{:.2f}".format(row[9]),
                ]
            )

    with (output_dir / "trades.csv").open(
        "w", newline="", encoding="utf-8"
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "Fill Date",
                "Signal Date",
                "Action",
                "Fill Price",
                "Shares",
                "Notional",
                "Fee",
                "Cash After",
                "Shares After",
                "Status",
                "Note",
            ]
        )
        for row in result.trades:
            writer.writerow(
                [
                    "" if row[0] is None else row[0].isoformat(),
                    row[1].isoformat(),
                    row[2],
                    "{:.6f}".format(row[3]),
                    row[4],
                    "{:.2f}".format(row[5]),
                    "{:.2f}".format(row[6]),
                    "{:.2f}".format(row[7]),
                    row[8],
                    row[9],
                    row[10],
                ]
            )

    with (output_dir / "summary.json").open("w", encoding="utf-8") as json_file:
        json.dump(result.summary, json_file, indent=2)
        json_file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research-only comparison of buy-and-hold and an SMA crossover."
    )
    parser.add_argument("input_csv", type=Path, help="CSV with Date and price columns.")
    parser.add_argument(
        "--price-column",
        default="Close",
        help="Price column to use (default: Close).",
    )
    parser.add_argument("--short-window", type=int, default=20)
    parser.add_argument("--long-window", type=int, default=50)
    parser.add_argument("--initial-cash", type=float, default=100000.0)
    parser.add_argument(
        "--fee-rate",
        type=float,
        default=0.001,
        help="Illustrative proportional cost per trade (0.001 means 0.1%%).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backtest_output"),
        help="Folder for equity.csv, trades.csv, and summary.json.",
    )
    args = parser.parse_args()

    try:
        prices = load_prices(args.input_csv, args.price_column)
        result = run_backtest(
            prices,
            short_window=args.short_window,
            long_window=args.long_window,
            initial_cash=args.initial_cash,
            fee_rate=args.fee_rate,
        )
        write_results(args.output_dir, result)
    except (OSError, csv.Error, ValueError) as error:
        parser.error(str(error))

    print("Research-only simulation complete; no real orders were placed.")
    print(
        "Buy-and-hold final equity: {:.2f} ({:.2f}%)".format(
            result.summary["buy_and_hold_final_equity"],
            result.summary["buy_and_hold_total_return_percent"],
        )
    )
    print(
        "SMA strategy final equity: {:.2f} ({:.2f}%)".format(
            result.summary["strategy_final_equity"],
            result.summary["strategy_total_return_percent"],
        )
    )
    print("Results saved in {}.".format(args.output_dir))


if __name__ == "__main__":
    main()
