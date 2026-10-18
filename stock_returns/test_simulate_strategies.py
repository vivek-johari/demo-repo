import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from simulate_strategies import moving_averages, run_backtest, write_results


class SimulateStrategiesTests(unittest.TestCase):
    def setUp(self):
        start_date = date(2024, 1, 1)
        closes = [100, 90, 80, 70, 60, 70, 80, 90, 80, 60, 50]
        self.prices = [
            (start_date + timedelta(days=index), float(close))
            for index, close in enumerate(closes)
        ]

    def test_moving_average_waits_until_window_is_full(self):
        averages = moving_averages(self.prices, 2)

        self.assertIsNone(averages[0])
        self.assertEqual(averages[1], 95.0)
        self.assertEqual(averages[2], 85.0)

    def test_crossover_fills_on_the_following_price_row(self):
        result = run_backtest(
            self.prices,
            short_window=2,
            long_window=3,
            initial_cash=1000,
            fee_rate=0,
        )

        self.assertEqual([trade[2] for trade in result.trades], ["BUY", "SELL"])
        self.assertEqual(result.trades[0][1], self.prices[6][0])
        self.assertEqual(result.trades[0][0], self.prices[7][0])
        self.assertEqual(result.trades[0][3], 90.0)
        self.assertEqual(result.trades[1][1], self.prices[9][0])
        self.assertEqual(result.trades[1][0], self.prices[10][0])
        self.assertEqual(result.trades[1][3], 50.0)
        self.assertEqual(result.trades[0][9], "filled")

    def test_fees_are_charged_on_strategy_buy_and_sell(self):
        result = run_backtest(
            self.prices,
            short_window=2,
            long_window=3,
            initial_cash=1000,
            fee_rate=0.01,
        )

        buy, sell = result.trades
        self.assertAlmostEqual(buy[6], buy[5] * 0.01)
        self.assertAlmostEqual(sell[6], sell[5] * 0.01)
        self.assertLess(result.summary["strategy_final_equity"], 1000)

    def test_last_day_signal_is_reported_without_inventing_a_fill(self):
        result = run_backtest(
            self.prices[:7],
            short_window=2,
            long_window=3,
            initial_cash=1000,
            fee_rate=0,
        )

        self.assertEqual(len(result.trades), 1)
        self.assertIsNone(result.trades[0][0])
        self.assertEqual(result.trades[0][9], "unfilled")
        self.assertEqual(result.summary["strategy_unfilled_signals"], 1)
        self.assertEqual(result.summary["strategy_ending_shares"], 0)

    def test_rejects_invalid_windows_and_insufficient_history(self):
        with self.assertRaisesRegex(ValueError, "smaller"):
            run_backtest(self.prices, short_window=3, long_window=3)
        with self.assertRaisesRegex(ValueError, "at least"):
            run_backtest(self.prices[:3], short_window=2, long_window=3)

    def test_writes_equity_trades_and_summary_outputs(self):
        result = run_backtest(
            self.prices,
            short_window=2,
            long_window=3,
            initial_cash=1000,
            fee_rate=0,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "results"
            write_results(output_dir, result)

            with (output_dir / "equity.csv").open(
                newline="", encoding="utf-8"
            ) as csv_file:
                equity_rows = list(csv.reader(csv_file))
            with (output_dir / "trades.csv").open(
                newline="", encoding="utf-8"
            ) as csv_file:
                trade_rows = list(csv.reader(csv_file))

            self.assertEqual(len(equity_rows), len(self.prices) + 1)
            self.assertEqual(trade_rows[1][2], "BUY")
            self.assertTrue((output_dir / "summary.json").exists())
            self.assertEqual(result.summary["strategy_annualized_return_percent"], None)


if __name__ == "__main__":
    unittest.main()
