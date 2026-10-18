"""Calculate historical price returns from a CSV file; this does not place trades."""

import argparse
import csv
import math
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple


Price = Tuple[date, float]
ReturnRow = Tuple[date, float, Optional[float], float]


def load_prices(csv_path: Path, price_column: str) -> List[Price]:
    """Load and validate Date and price columns, sorting rows by date."""
    prices = []
    # Remember dates we've seen so one trading day cannot be counted twice.
    seen_dates = set()

    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        # DictReader lets us find values by their column names, such as "Date".
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("The CSV file must have a header row.")

        # Match column names without caring about capitalization or extra spaces.
        columns = {
            name.strip().casefold(): name
            for name in reader.fieldnames
            if name and name.strip()
        }
        date_column = columns.get("date")
        value_column = columns.get(price_column.strip().casefold())
        if date_column is None:
            raise ValueError("The CSV must contain a 'Date' column.")
        if value_column is None:
            raise ValueError(
                "The CSV must contain a '{}' column.".format(price_column)
            )

        # CSV row 1 is the header, so the first data row is row 2.
        for row_number, row in enumerate(reader, start=2):
            if not any(value and value.strip() for value in row.values()):
                continue

            try:
                trading_date = date.fromisoformat(row[date_column].strip())
            except (AttributeError, ValueError):
                raise ValueError(
                    "Invalid date on CSV row {}. Use YYYY-MM-DD.".format(row_number)
                )

            try:
                close = float(row[value_column].strip())
            except (AttributeError, ValueError):
                raise ValueError(
                    "Invalid price on CSV row {}.".format(row_number)
                )

            # Prices must be real positive numbers, and dates must be unique.
            if not math.isfinite(close) or close <= 0:
                raise ValueError(
                    "Price on CSV row {} must be a finite number above zero.".format(
                        row_number
                    )
                )
            if trading_date in seen_dates:
                raise ValueError(
                    "Duplicate date on CSV row {}: {}.".format(
                        row_number, trading_date.isoformat()
                    )
                )

            seen_dates.add(trading_date)
            prices.append((trading_date, close))

    if not prices:
        raise ValueError("The CSV contains no price rows.")

    # Sort once here so return calculations always move forward through time.
    return sorted(prices, key=lambda item: item[0])


def calculate_returns(prices: List[Price]) -> List[ReturnRow]:
    """Calculate daily and since-first-observation price returns in percent."""
    if not prices:
        raise ValueError("At least one price is needed to calculate returns.")

    first_close = prices[0][1]  # Used as the starting point for total return.
    results = []
    previous_close = None

    for trading_date, close in prices:
        # There is no daily change for the first date because it has no prior price.
        daily_return = None
        if previous_close is not None:
            # Divide the price change by yesterday's price, then convert to percent.
            daily_return = (close / previous_close - 1) * 100
        # Compare every price with the first price to get the period's total change.
        cumulative_return = (close / first_close - 1) * 100
        results.append(
            (trading_date, close, daily_return, cumulative_return)
        )
        # Today's price becomes the previous price for the next loop.
        previous_close = close

    return results


def write_results(output_path: Path, results: List[ReturnRow]) -> None:
    """Write calculated returns to a CSV file."""
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        # Write column names first, then one calculated row per date.
        writer.writerow(
            ["Date", "Close", "Daily Return (%)", "Cumulative Return (%)"]
        )
        for trading_date, close, daily_return, cumulative_return in results:
            writer.writerow(
                [
                    trading_date.isoformat(),
                    "{:.10g}".format(close),
                    "" if daily_return is None else "{:.6f}".format(daily_return),
                    "{:.6f}".format(cumulative_return),
                ]
            )


def main() -> None:
    # argparse reads the file name and options typed after the script command.
    parser = argparse.ArgumentParser(
        description="Calculate historical stock price returns from a CSV."
    )
    parser.add_argument(
        "input_csv",
        type=Path,
        help="CSV containing Date and Close (or another selected price column).",
    )
    parser.add_argument(
        "--price-column",
        default="Close",
        help="CSV price column to use (default: Close).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("daily_returns.csv"),
        help="Where to write the results (default: daily_returns.csv).",
    )
    args = parser.parse_args()

    # Stop safely with a helpful command-line error if input or output fails.
    try:
        # Prevent accidentally replacing the source prices with calculated data.
        if args.input_csv.resolve() == args.output.resolve():
            raise ValueError("The output path must not overwrite the input CSV.")
        prices = load_prices(args.input_csv, args.price_column)
        results = calculate_returns(prices)
        write_results(args.output, results)
    except (OSError, csv.Error, ValueError) as error:
        parser.error(str(error))

    # The final cumulative value is the overall price change for the full period.
    total_return = results[-1][3]
    print("Loaded {} price rows.".format(len(prices)))
    print(
        "Period: {} to {}".format(
            prices[0][0].isoformat(), prices[-1][0].isoformat()
        )
    )
    print("Price return over period: {:.2f}%".format(total_return))
    print("Wrote results to {}.".format(args.output))
    print("This is a historical price calculation, not a trading simulation.")


if __name__ == "__main__":
    # Run the command-line program only when this file is launched directly.
    main()
