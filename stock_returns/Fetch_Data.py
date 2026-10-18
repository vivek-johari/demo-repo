import yfinance as yf

prices = yf.Ticker("RELIANCE.NS").history(
    period="5y",
    interval="1d",
    auto_adjust=False,
)

if prices.empty:
    raise ValueError("No price data was returned. Check the symbol and connection.")

prices.index.name = "Date"
prices.reset_index().to_csv("RELIANCE_5y_daily.csv", index=False)