"""
Portfolio Risk, Return, and the Limits of Diversification
=========================================================

A self-contained analysis demonstrating how I approach a markets question with
Python: build a small multi-asset portfolio, measure risk and return properly,
and test how much diversification actually helps — including where it stops
helping.

Author: Amit Kumar
Tools: pandas, numpy, matplotlib, yfinance

What this shows:
- Pulling and cleaning real market data
- Computing annualized return, volatility, Sharpe ratio
- Building a correlation matrix and reasoning about diversification
- Simulating the efficient frontier (Monte Carlo) and identifying the
  max-Sharpe and min-variance portfolios
- Interpreting results with appropriate caution, not overclaiming

Run:
    pip install yfinance pandas numpy matplotlib
    python portfolio_analysis.py

Note: yfinance pulls live data, so exact numbers will vary by run date.
The reasoning and method are the point, not any single number.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("Install dependencies first: pip install yfinance pandas numpy matplotlib")


# ----------------------------------------------------------------------
# 1. Configuration
# ----------------------------------------------------------------------
# A deliberately diverse set: US large-cap, US tech, treasuries, gold,
# and an international equity ETF. The point of the mix is to include assets
# that should NOT all move together, so diversification has something to work with.
TICKERS = {
    "SPY": "US Large Cap (S&P 500)",
    "QQQ": "US Tech (Nasdaq 100)",
    "TLT": "Long-Term US Treasuries",
    "GLD": "Gold",
    "EFA": "Developed Intl Equity",
}
START = "2015-01-01"
END = "2024-12-31"
RISK_FREE_RATE = 0.02   # annual, a simplifying assumption — stated, not hidden
TRADING_DAYS = 252
N_PORTFOLIOS = 20_000   # Monte Carlo samples for the frontier


# ----------------------------------------------------------------------
# 2. Data
# ----------------------------------------------------------------------
def load_prices(tickers, start, end):
    """Download adjusted close prices and drop any rows with missing data."""
    raw = yf.download(list(tickers), start=start, end=end, progress=False)
    # yfinance returns a multi-index; take adjusted close
    prices = raw["Close"] if "Close" in raw else raw
    prices = prices.dropna()
    if prices.empty:
        raise SystemExit("No price data returned — check connectivity or tickers.")
    return prices


def daily_returns(prices):
    """Simple daily returns, cleaned."""
    return prices.pct_change().dropna()


# ----------------------------------------------------------------------
# 3. Core risk / return metrics
# ----------------------------------------------------------------------
def annualized_metrics(returns, rf=RISK_FREE_RATE):
    """Return a tidy table of annualized return, volatility, and Sharpe."""
    ann_return = returns.mean() * TRADING_DAYS
    ann_vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = (ann_return - rf) / ann_vol
    table = pd.DataFrame({
        "Annual Return": ann_return,
        "Annual Volatility": ann_vol,
        "Sharpe Ratio": sharpe,
    })
    return table.sort_values("Sharpe Ratio", ascending=False)


# ----------------------------------------------------------------------
# 4. Diversification: the correlation matrix
# ----------------------------------------------------------------------
def correlation_matrix(returns):
    """Correlation tells us how much diversification is actually available.
    Assets with low or negative correlation are what make a portfolio more
    than the sum of its parts."""
    return returns.corr()


# ----------------------------------------------------------------------
# 5. Monte Carlo efficient frontier
# ----------------------------------------------------------------------
def simulate_frontier(returns, n=N_PORTFOLIOS, rf=RISK_FREE_RATE, seed=42):
    """Randomly sample portfolio weights and record risk/return/Sharpe for each.
    This approximates the efficient frontier without an optimizer, which keeps
    the logic transparent and easy to audit."""
    rng = np.random.default_rng(seed)
    mean_daily = returns.mean().values
    cov_daily = returns.cov().values
    n_assets = len(returns.columns)

    results = np.zeros((n, 3))
    weights_record = np.zeros((n, n_assets))

    for i in range(n):
        w = rng.random(n_assets)
        w /= w.sum()                      # weights sum to 1, long-only
        weights_record[i] = w

        port_return = np.dot(w, mean_daily) * TRADING_DAYS
        port_vol = np.sqrt(w @ cov_daily @ w) * np.sqrt(TRADING_DAYS)
        sharpe = (port_return - rf) / port_vol

        results[i] = [port_return, port_vol, sharpe]

    cols = ["Return", "Volatility", "Sharpe"]
    frontier = pd.DataFrame(results, columns=cols)
    return frontier, weights_record


def named_weights(weights, columns):
    return pd.Series(weights, index=columns).sort_values(ascending=False)


# ----------------------------------------------------------------------
# 6. Run + report
# ----------------------------------------------------------------------
def main():
    print("Loading data...")
    prices = load_prices(TICKERS, START, END)
    rets = daily_returns(prices)
    print(f"Loaded {len(prices)} trading days for {len(prices.columns)} assets "
          f"({prices.index.min().date()} to {prices.index.max().date()}).\n")

    # Individual asset metrics
    print("=" * 60)
    print("INDIVIDUAL ASSET METRICS (annualized)")
    print("=" * 60)
    metrics = annualized_metrics(rets)
    metrics.index = [TICKERS.get(t, t) for t in metrics.index]
    print(metrics.round(3).to_string())
    print()

    # Correlation
    print("=" * 60)
    print("CORRELATION MATRIX (the raw material of diversification)")
    print("=" * 60)
    corr = correlation_matrix(rets)
    corr.index = [t for t in corr.index]
    print(corr.round(2).to_string())
    avg_offdiag = corr.values[np.triu_indices_from(corr.values, k=1)].mean()
    print(f"\nAverage pairwise correlation: {avg_offdiag:.2f}")
    print("Lower average correlation => more diversification benefit available.\n")

    # Efficient frontier
    print("=" * 60)
    print("EFFICIENT FRONTIER (Monte Carlo, {:,} portfolios)".format(N_PORTFOLIOS))
    print("=" * 60)
    frontier, weights = simulate_frontier(rets)

    max_sharpe_idx = frontier["Sharpe"].idxmax()
    min_vol_idx = frontier["Volatility"].idxmin()

    print("\nMax-Sharpe portfolio:")
    print(f"  Return {frontier.loc[max_sharpe_idx, 'Return']:.3f} | "
          f"Vol {frontier.loc[max_sharpe_idx, 'Volatility']:.3f} | "
          f"Sharpe {frontier.loc[max_sharpe_idx, 'Sharpe']:.3f}")
    print("  Weights:")
    print(named_weights(weights[max_sharpe_idx], rets.columns).round(3).to_string())

    print("\nMin-variance portfolio:")
    print(f"  Return {frontier.loc[min_vol_idx, 'Return']:.3f} | "
          f"Vol {frontier.loc[min_vol_idx, 'Volatility']:.3f} | "
          f"Sharpe {frontier.loc[min_vol_idx, 'Sharpe']:.3f}")
    print("  Weights:")
    print(named_weights(weights[min_vol_idx], rets.columns).round(3).to_string())

    # Plot
    plt.figure(figsize=(10, 6))
    sc = plt.scatter(frontier["Volatility"], frontier["Return"],
                     c=frontier["Sharpe"], cmap="viridis", s=6, alpha=0.6)
    plt.colorbar(sc, label="Sharpe Ratio")
    plt.scatter(frontier.loc[max_sharpe_idx, "Volatility"],
                frontier.loc[max_sharpe_idx, "Return"],
                marker="*", color="red", s=300, label="Max Sharpe")
    plt.scatter(frontier.loc[min_vol_idx, "Volatility"],
                frontier.loc[min_vol_idx, "Return"],
                marker="*", color="blue", s=300, label="Min Variance")
    plt.xlabel("Annualized Volatility (risk)")
    plt.ylabel("Annualized Return")
    plt.title("Efficient Frontier: Risk vs Return Across 20,000 Portfolios")
    plt.legend()
    plt.tight_layout()
    plt.savefig("efficient_frontier.png", dpi=120)
    print("\nSaved plot: efficient_frontier.png")

    # Interpretation — the judgment layer, stated explicitly
    print("\n" + "=" * 60)
    print("WHAT I CONCLUDE — AND WHAT I DON'T")
    print("=" * 60)
    print("""
What the analysis supports:
  - Combining assets with low/negative correlation (e.g. equities + treasuries
    + gold) produces portfolios with better risk-adjusted return (Sharpe) than
    most single assets. Diversification is real and measurable here.
  - The min-variance and max-Sharpe portfolios are different points: lowest risk
    is not the same as best risk-adjusted return. The 'right' choice depends on
    the investor's objective, not the math alone.

What I would NOT claim:
  - These weights are backward-looking. They optimize the PAST; correlations and
    returns shift, so this is not a recommendation to hold these exact weights.
  - Sharpe assumes returns are well-behaved; it understates tail risk, and
    correlations tend to rise precisely in crises, when diversification is needed
    most. The historical frontier flatters diversification versus a real crash.
  - A fixed risk-free rate and a 10-year window are simplifying choices that
    affect the numbers. They are stated, not hidden.
""")


if __name__ == "__main__":
    main()
