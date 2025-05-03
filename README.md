# Optimal Order Placement and Backtest

## Overview

This project implements an optimal order placement algorithm following the Cont-Kukanov model. It simulates and compares four strategies for executing a large order across multiple venues:

- **Cont-Kukanov optimal allocator** (our method)
- **Best Ask** (naïve baseline, always take the best ask)
- **TWAP** (Time Weighted Average Price baseline)
- **VWAP** (Volume Weighted Average Price baseline)

All strategies are backtested on Level-1 market data (`l1_day.csv`), using venue snapshots that include ask price, ask size, and fixed fee and rebate settings.

## Code structure

- `allocate`: Exhaustive search allocator based on the Cont-Kukanov pseudocode.
- `compute_cost`: Computes cost given an allocation, including penalties for underfill/overfill and queue risk.
- `run_backtest`: Executes the backtest loop, applying optimal allocation on each snapshot.
- `grid_search`: Grid search over `lambda_over`, `lambda_under`, `theta_queue` parameters to find the best Cont-Kukanov configuration.
- `best_ask_strategy`, `twap_strategy`, `vwap_strategy`: Baseline strategies.
- `main`: Loads data, runs grid search and baselines, computes savings, outputs JSON summary.

## Parameter Search

- `lambda_over`: [0.05, 0.1, 0.3, 0.5]
- `lambda_under`: [0.1, 0.2, 0.4]
- `theta_queue`: [0.05, 0.1, 0.3]

These values were chosen to reflect low to moderately high penalties. The search space balances granularity and speed, ensuring the backtest completes within 2 minutes.

## Suggested Improvement (Slippage/Queue realism)

In the current implementation, limit orders are assumed to be filled up to the displayed ask size immediately if market flow is sufficient. In reality:

- Not all displayed liquidity is always available (hidden orders, priority queue position).
- Queue position matters; late orders might not fill even if total outflow is large enough.

**Suggested improvement:**  
Add a "fill probability" model for limit orders. Instead of assuming all unfilled ask sizes are hit proportionally, model a probabilistic fill based on queue depth (e.g. exponential decay for worse positions in the queue). This would make execution more realistic and likely increase reliance on market orders or more aggressive limit placements.

## Output

The script produces a JSON object summarizing:
- Best parameters for Cont-Kukanov
- Total cost and average price for Cont-Kukanov and all baselines
- Savings vs baselines (bps)

Optionally, `results.png` can be produced showing cumulative cost comparison.
