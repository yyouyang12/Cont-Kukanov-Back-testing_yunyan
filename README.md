# Optimal Order Placement and Backtest

## Overview

This project implements a full pipeline to optimally split and execute a large buy order (5,000 shares) across multiple exchanges using Level-1 order book data (`l1_day.csv`).

We use the optimal allocator introduced by **Cont & Kukanov (“Optimal Order Placement in Limit Order Markets”)**. The router splits a 5,000-share buy order across multiple venues using three risk parameters—`lambda_over`, `lambda_under`, and `theta_queue`—to balance between:

- Execution risk
- Market impact
- Queue risk

We compare this Cont-Kukanov based optimal allocator against three baselines:

- **Take the Best (Best Ask)** (naive take-best price)
- **TWAP** (Time Weighted Average Price)
- **VWAP** (Volume Weighted Average Price)

All strategies are evaluated in terms of total cost and average execution price. All baselines and metrics are computed over the same 9-minute window provided in the data, ensuring fair comparison. A JSON report and cumulative cost plot (`results.png`) are generated.


## Code Structure

### `allocate`

- Exhaustive search allocator
- Implements the Cont-Kukanov pseudocode exactly as described
- Evaluates all valid splits of the target order across venues to find the one with minimal cost

### `compute_cost`

- Evaluates the cost of an order allocation
- Incorporates:
  - Ask prices and fees
  - Penalties for:
    - Overfill (`lambda_over`)
    - Underfill (`lambda_under`)
    - Queue risk (`theta_queue`)
  
### `load_venues(df, fee, rebate)`

- Preprocess the raw Level-1 market data
- For every unique `ts_event` (timestamp), and `publisher_id` (venue), keeps only the first record
- Groups them into **snapshots** that will be fed into all strategies
- Adds customizable `fee` and `rebate` per venue

### `get_buckets`
- Splits Level-1 data into time buckets covering the 9-minute window.

### Baseline strategies

- `take_the_best`: Always fills from the venue with the best ask
- `TWAP`: Splits the order evenly across snapshots
- `VWAP`: Splits the order proportionally to displayed ask size in each snapshot

### `run_backtest`

- Main loop to run Cont-Kukanov allocator against historical venue snapshots
- Simulates fills, accumulates total cost and average price

### `grid_search`

- Searches over grids of `lambda_over`, `lambda_under`, and `theta_queue` to find the best performing parameter set

### `main`

- Loads and process data
- Defines tunable parameters (below)
- Runs Cont-Kukanov model and baselines models
- Computes savings (bps) against baselines
- Outputs final JSON report and saves cumulative cost plot (`results.png`)


## Tunable Parameters

```python
lambda_over_grid = [0.05, 0.1, 0.3, 0.5]
lambda_under_grid = [0.1, 0.2, 0.4]
theta_queue_grid = [0.05, 0.1, 0.3]

order_size = 5000
fee = 0.003
rebate = 0.0015
```

These parameters can be freely modified in `main` to adapt to new scenarios or datasets.


## Output

The script prints a JSON object containing:

- Best parameters for Cont-Kukanov
- Total cost and average price for Cont-Kukanov and all baselines
- Savings in basis points (bps) against all baselines
- `results.png` plot showing cumulative cost comparison


## Suggested Improvements

### Smarter parameter search

Current grid search is simple and exhaustive. A **stochastic approximation algorithm** (as used in the original paper) could be applied for faster and more adaptive tuning.

### Additional variables to improve realism

- Hidden liquidity probability
- Venue execution latency
- Historical venue fill ratios
- Price volatility and spread widening risk
- Market impact modeling
- Queue position modeling
- Order expiry/modification dynamics

### Advanced allocator logic

- Probabilistic fill model for limit orders
- Online learning or RL-based adaptive allocator
- Smarter queue-aware limit order placement

## Reference
Cont, R., & Kukanov, A. (2014). Optimal order placement in limit order markets. arXiv preprint arXiv:1210.1625v4. https://doi.org/10.48550/arXiv.1210.1625
