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

- `allocate`: Exhaustive search allocator based on Cont-Kukanov pseudocode.
- `compute_cost`: Calculates total cost for an allocation including fees, rebates, under/overfill penalties, and queue risk.
- `load_venues`: Converts raw orderbook data to snapshot format with fee and rebate settings.
- `take_the_best`, `TWAP`, `VWAP`: Baseline allocation methods.
- `run_backtest`: Executes backtest loop with the optimal allocator.
- `grid_search`: Searches for best parameters (`lambda_over`, `lambda_under`, `theta_queue`).
- `main`: Prepares data, runs grid search and baselines, saves JSON results, and plots cumulative cost (`results.png`).

## Tunable Parameters

```python
# These parameters can be freely modified in `main` to adapt to new scenarios or datasets.
lambda_over_grid = [0.0001, 0.001, 0.01, 0.05, 0.1]
lambda_under_grid = [0.0001, 0.001, 0.01, 0.05, 0.1]
theta_queue_grid = [0.0001, 0.001, 0.01, 0.05, 0.1]

order_size = 5000
fee = 0.003
rebate = 0.0015
# Fee and rebate are key market characteristics and directly impact expected execution cost.
# I set `fee = 0.003` and `rebate = 0.0015` to simulate typical maker/taker fees observed in U.S. equity markets.
# Including them as parameters allows the allocator to better reflect cross-venue cost differences when placing orders.

```

### Why Are Small Penalty Parameters Selected?

During backtesting, I found the grid search tends to select very small values for `lambda_over`, `lambda_under`, and `theta_queue`. This may reflects the current model structure and data characteristics:

- The allocator enforces exact fills (sum of allocation equals order size), which makes overfill and underfill penalties rarely triggered.
- The market snapshots usually offer sufficient ask sizes, so underfills are uncommon.
- The queue-risk penalty (`theta_queue`) is modeled in a simplified way without actual queue depth modeling, resulting in limited impact on cost calculations.

Therefore, in this setting, smaller penalty parameters naturally lead to slightly lower expected costs. 

## Output

The script prints a JSON object containing:

- Best parameters for Cont-Kukanov
- Total cost and average price for Cont-Kukanov and all baselines
- Savings in basis points (bps) against all baselines
- `results.png` plot showing cumulative cost comparison


## Potential Improvements for Fill Realism

While the current backtest assumes perfect and proportional fills based on displayed liquidity, real-world trading involves more uncertainty and dynamics. To improve fill realism and make the allocator more practical, the following enhancements could be considered:

### Smarter Parameter Search

- The current grid search is simple and exhaustive.
- A **stochastic approximation algorithm** (as proposed in the original Cont & Kukanov paper) could be used for faster, more adaptive tuning. This would allow dynamic learning of optimal parameters based on historical performance.

### Modeling Additional Market Variables

- **Hidden liquidity probability**  
  Not all available liquidity is visible. Modeling hidden orders could impact fill assumptions.

- **Queue position modeling**  
  Limit orders placed deep in the queue are less likely to fill. Introducing queue depth estimates would improve realism.

- **Order expiry and modification dynamics**  
  In reality, orders are often amended or canceled during execution.

### Advanced Allocator Logic

- **Online learning or reinforcement learning (RL) based adaptive allocator**  
  Adjust order placement strategy dynamically based on observed execution performance.

- **Queue position simulation with expected fill modeling**  
  Assume other traders are ahead in the queue and adjust estimated fillable shares accordingly.


## Reference
Cont, R., & Kukanov, A. (2014). Optimal order placement in limit order markets. arXiv preprint arXiv:1210.1625v4. https://doi.org/10.48550/arXiv.1210.1625
