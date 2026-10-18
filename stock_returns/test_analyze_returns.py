import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from analyze_returns import calculate_returns, load_prices, write_results


class AnalyzeReturnsTests(unittest.TestCase):
    def test_loads_prices_in_date_order_and_calculates_returns(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            # Make a tiny CSV with dates deliberately out of order.
            input_path = Path(temporary_directory) / "prices.csv"
            input_path.write_text(
                "Date,Close\n2024-01-03,110\n2024-01-01,100\n2024-01-02,105\n",
                encoding="utf-8",
            )

            # Load and calculate from the temporary example file.
            prices = load_prices(input_path, "Close")
            results = calculate_returns(prices)

        # Loading sorts dates, and the first date has no daily return yet.
        self.assertEqual(
            prices,
            [
                (date(2024, 1, 1), 100.0),
                (date(2024, 1, 2), 105.0),
                (date(2024, 1, 3), 110.0),
            ],
        )
        self.assertIsNone(results[0][2])
        self.assertAlmostEqual(results[1][2], 5.0)
        self.assertAlmostEqual(results[2][2], (110 / 105 - 1) * 100)
        self.assertAlmostEqual(results[2][3], 10.0)

    def test_rejects_non_positive_prices(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            # Zero is not a valid stock price, so loading should reject it.
            input_path = Path(temporary_directory) / "prices.csv"
            input_path.write_text(
                "Date,Close\n2024-01-01,0\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "above zero"):
                load_prices(input_path, "Close")

    def test_writes_csv_with_first_daily_return_blank(self):
        # Prepare two dates to check both the blank first-day return and a 10% rise.
        results = calculate_returns(
            [(date(2024, 1, 1), 100.0), (date(2024, 1, 2), 110.0)]
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            # Save and read the output just as a user or spreadsheet would.
            output_path = Path(temporary_directory) / "returns.csv"
            write_results(output_path, results)

            with output_path.open(newline="", encoding="utf-8") as csv_file:
                rows = list(csv.reader(csv_file))

        # Check the headings, missing first daily return, and calculated percentages.
        self.assertEqual(
            rows[0],
            ["Date", "Close", "Daily Return (%)", "Cumulative Return (%)"],
        )
        self.assertEqual(rows[1][2], "")
        self.assertEqual(rows[2][2], "10.000000")
        self.assertEqual(rows[2][3], "10.000000")


if __name__ == "__main__":
    unittest.main()
