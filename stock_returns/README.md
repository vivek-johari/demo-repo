# Indian stock price returns starter

This is a small, research-only Python exercise. It reads historical prices from
a CSV file, calculates daily and cumulative price returns, and writes the
results to another CSV. It does **not** choose stocks, recommend trades, or
connect to a broker.

## 1. Prepare price data

The input CSV needs a `Date` column in `YYYY-MM-DD` format and a `Close` column.
For example:

```csv
Date,Close
2024-01-02,100
2024-01-03,102
```

`sample_prices.csv` contains fictional example values so you can run the
program immediately. They are not actual market data.

For research, obtain data from a source whose terms permit your intended use.
Use adjusted prices when available to account for corporate actions such as
splits and dividends; specify the correct input column with `--price-column`.
For example, if your file has an `Adj Close` column:

```powershell
python .\analyze_returns.py .\your_prices.csv --price-column "Adj Close" --output .\returns.csv
```

## 2. Run the example

In a terminal, change to this folder and run:

```powershell
python .\analyze_returns.py .\sample_prices.csv --output .\sample_returns.csv
```

The script prints the period and total price return, and writes one row per
date to `sample_returns.csv`. The first daily return is blank because there is
no previous observation. Dates are sorted before calculation; duplicate dates,
invalid dates, and non-positive prices are rejected.

The calculated returns do not include brokerage, taxes or levies, bid-ask
spread, slippage, or the timing of an actual trade. They are not a backtest or
a prediction of future results.

## 3. Run the tests

No third-party packages are needed. From this folder:

```powershell
python -m unittest -v
```

## 4. Compare buy-and-hold with a moving-average rule

`simulate_strategies.py` is a small historical, single-stock simulator. It
compares a buy-and-hold portfolio with a long-only short/long simple moving
average (SMA) crossover. The default SMA windows are 20 and 50 trading
observations, respectively; they are example settings, not recommended or
optimized values.

Run it with a CSV containing at least 51 valid `Date` / `Close` rows:

```powershell
python .\simulate_strategies.py .\your_prices.csv --output-dir .\backtest_output
```

For a different column or test settings:

```powershell
python .\simulate_strategies.py .\your_prices.csv --price-column "Close" --short-window 20 --long-window 50 --initial-cash 100000 --fee-rate 0.001 --output-dir .\backtest_output
```

The SMA strategy buys when the short average crosses above the long average
and sells when it crosses below. A signal is calculated only after a day's
close and is filled at the next available day's close, since this starter reads
closing prices only. This is a deliberately simple simulation convention, not
a promise that an actual order could fill at that price. It simulates whole
shares, one stock, long-only positions, and cash between positions; the
proportional fee rate is illustrative and defaults to 0.1% per filled order.

The output folder contains:

- `equity.csv`: daily strategy and buy-and-hold cash, shares, and marked value.
- `trades.csv`: simulated signal and fill dates, orders, costs, and status.
- `summary.json`: total and annualized return, maximum drawdown, trade counts,
  and the simulation assumptions.

Annualized return is left blank (`null`) when the test period is shorter than
one year because extrapolating a few days into a full year can be misleading.

This is a learning backtest, not a trading recommendation or a prediction.
Price-only data does not model dividends, splits, taxes, exchange levies,
bid-ask spread, market impact, partial fills, or outages. Adjusted prices can
help account for corporate actions in return analysis, but they are not
necessarily prices at which an order could actually execute. Results can be
misleading due to data quality, survivorship bias, look-ahead bias, or
overfitting. Compare multiple chronological periods and inspect the trade and
equity files; do not connect this script to a broker or use its output as
evidence of future profits.
