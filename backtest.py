#!/usr/bin/env python
# coding: utf-8

# In[79]:


# ---------------------
# Created by Yunyan, 05/03/2025
# ---------------------

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from itertools import product
import json

# Static Cont-Kukanov split across N venues (single snapshot)

# Inputs
#   order_size  – target shares to buy (e.g. 5_000)
#   venues      – list of objects, one per venue, each with:
#                 .ask  .ask_size  .fee  .rebate
#   λ_over      – cost penalty per extra share bought
#   λ_under     – cost penalty per unfilled share
#   θ_queue     – queue-risk penalty (linear in total mis-execution)
#
# Outputs
#   best_split  – list[int]  shares sent to each venue (len == N)
#   best_cost   – float      total expected cost of that split

# ---------------------
# Compute Cost
# ---------------------
def compute_cost(split, venues, order_size, lambda_over, lambda_under, theta_queue):
    """
    Compute total cost of executing a given split of orders across venues.

    Cost includes:
    - execution cost (price * quantity + fee)
    - rebates for unfilled orders
    - penalties for underfill / overfill
    - queue risk penalty for unfilled or extra filled shares
    """
    executed = 0
    cash_spent = 0
    for i in range(len(venues)):
        exe = min(split[i], venues[i]['ask_size'])
        executed += exe
        cash_spent += exe * (venues[i]['ask'] + venues[i]['fee'])
        maker_rebate = max(split[i] - exe, 0) * venues[i]['rebate']
        cash_spent -= maker_rebate
    underfill = max(order_size - executed, 0)
    overfill = max(executed - order_size, 0)
    risk_pen = theta_queue * (underfill + overfill)
    cost_pen = lambda_under * underfill + lambda_over * overfill
    return cash_spent + risk_pen + cost_pen

# ---------------------
# Allocate
# ---------------------
def allocate(order_size, venues, lambda_over, lambda_under, theta_queue):
    """
    Allocate order using exhaustive search to minimize total expected cost.

    Each allocation considers:
    - venue ask prices and available size
    - penalties for under/overfill
    - queue risk penalty
    """
    step = 100
    splits = [[]]
    for v in range(len(venues)):
        new_splits = []
        for alloc in splits:
            used = sum(alloc)
            max_v = min(order_size - used, venues[v]['ask_size'])
            for q in range(0, max_v + 1, step):
                new_splits.append(alloc + [q])
        splits = new_splits
    best_cost = float('inf')
    best_split = None
    for alloc in splits:
        if sum(alloc) != order_size:
            continue
        cost = compute_cost(alloc, venues, order_size, lambda_over, lambda_under, theta_queue)
        if cost < best_cost:
            best_cost = cost
            best_split = alloc
    return best_split, best_cost

# ---------------------
# Load venues snapshot
# ---------------------
def load_venues(df, fee, rebate):
    """
    Process raw message feed into venue snapshots.

    Each snapshot is a list of venues (dict), including:
    - ask price
    - ask size
    - fixed fee and rebate
    """
    snapshots = []
    for ts, snapshot in df.groupby('ts_event'):
        venues = []
        for _, row in snapshot.iterrows():
            venue = {
                'ask': row['ask_px_00'],
                'ask_size': row['ask_sz_00'],
                'fee': fee,
                'rebate': rebate
            }
            venues.append(venue)
        snapshots.append(venues)
    return snapshots

# ---------------------
# Baseline: Best Ask
# ---------------------
def take_the_best(snapshots, order_size):
    """
    Baseline: Always buy from the venue with best ask price.

    Execute greedily from best ask until order is filled.
    """
    total_cost, total_bought = 0, 0
    cum_cost = []
    for venues in snapshots:
        best_venue = min(venues, key=lambda x: x['ask'])
        fill = min(order_size - total_bought, best_venue['ask_size'])
        total_cost += fill * best_venue['ask']
        total_bought += fill
        cum_cost.append(total_cost)
        if total_bought >= order_size:
            break
    avg_price = total_cost / total_bought if total_bought > 0 else None
    return total_cost, avg_price, cum_cost

# ---------------------
# Baseline: TWAP
# ---------------------
def TWAP(snapshots, order_size):
    """
    Baseline: Time-Weighted Average Price (TWAP).

    Evenly split order across snapshots in time.
    """
    total_cost, total_bought = 0, 0
    cum_cost = []
    per_snapshot = order_size // len(snapshots)

    for venues in snapshots:
        if total_bought >= order_size:
            break
        best_venue = min(venues, key=lambda x: x['ask'])
        fill = min(per_snapshot, best_venue['ask_size'], order_size - total_bought)
        total_cost += fill * best_venue['ask']
        total_bought += fill
        cum_cost.append(total_cost)

    if total_bought < order_size:
        for venues in snapshots:
            best_venue = min(venues, key=lambda x: x['ask'])
            fill = min(order_size - total_bought, best_venue['ask_size'])
            total_cost += fill * best_venue['ask']
            total_bought += fill
            cum_cost.append(total_cost)
            if total_bought >= order_size:
                break

    avg_price = total_cost / total_bought if total_bought > 0 else None
    return total_cost, avg_price, cum_cost

# ---------------------
# Baseline: VWAP (bucketed)
# ---------------------
def VWAP(snapshots, order_size, bucket_size=60):
    """
    Baseline: Volume-Weighted Average Price (VWAP).

    Split order proportionally according to venue ask size weight.
    """
    total_cost = 0
    total_bought = 0
    cum_cost = []
    
    buckets = [snapshots[i:i + bucket_size] for i in range(0, len(snapshots), bucket_size)]
    
    for bucket in buckets:
        all_venues = []
        for venues in bucket:
            all_venues += venues
        
        total_ask = sum(v['ask_size'] for v in all_venues)
        
        if total_ask == 0:
            continue

        for venue in all_venues:
            share = venue['ask_size'] / total_ask
            to_buy = int(order_size * share)
            fill = min(to_buy, venue['ask_size'], order_size - total_bought)

            total_cost += fill * venue['ask']
            total_bought += fill
            cum_cost.append(total_cost)

            if total_bought >= order_size:
                break
        
        if total_bought >= order_size:
            break

    avg_price = total_cost / total_bought if total_bought > 0 else None
    return total_cost, avg_price, cum_cost


# ---------------------
# Run backtest for Cont-Kukanov
# ---------------------
def run_backtest(snapshots, lambda_over, lambda_under, theta_queue, order_size=5000):
    """
    Run Cont-Kukanov allocator on each snapshot.

    Records cumulative cost for plotting and computes total spent and average price.
    """
    total_cost = 0
    total_bought = 0
    cum_cost = [0]

    for venues in snapshots:
        alloc, _ = allocate(order_size, venues, lambda_over, lambda_under, theta_queue)
        if alloc is None:
            continue

        for i in range(len(venues)):
            fill = min(alloc[i], venues[i]['ask_size'])
            total_bought += fill
            total_cost += fill * venues[i]['ask']

            cum_cost.append(total_cost)

            if total_bought >= order_size:
                break
        if total_bought >= order_size:
            break

    avg_price = total_cost / total_bought if total_bought > 0 else None
    return total_cost, avg_price, cum_cost

# ---------------------
# Grid search
# ---------------------
def grid_search(snapshots, lambda_over_grid, lambda_under_grid, theta_queue_grid, order_size):
    """
    Exhaustive grid search to select the best risk parameter combination.

    Chooses the set that minimizes total cost.
    """
    best_params = None
    best_total_cost = float('inf')
    best_avg_price = None
    best_cum_cost = None

    for lambda_over, lambda_under, theta_queue in product(lambda_over_grid, lambda_under_grid, theta_queue_grid):
        total_cost, avg_price, cum_cost = run_backtest(snapshots, lambda_over, lambda_under, theta_queue, order_size)
        if total_cost < best_total_cost:
            best_total_cost = total_cost
            best_avg_price = avg_price
            best_params = {
                "lambda_over": lambda_over,
                "lambda_under": lambda_under,
                "theta_queue": theta_queue
            }
            best_cum_cost = cum_cost

    return best_params, best_total_cost, best_avg_price, best_cum_cost

# ---------------------
# Main
# ---------------------
def main():
    # load data
    df = pd.read_csv("./l1_day.csv")
    df = df.drop_duplicates(subset=["ts_event", "publisher_id"], keep="first")
    df = df.sort_values("ts_event")

    # parameters
    order_size = 5000
    fee, rebate = 0.003, 0.0015
    # the first search
    # lambda_over_grid = [0.05, 0.1, 0.3, 0.5]
    # lambda_under_grid = [0.1, 0.2, 0.4]
    # theta_queue_grid = [0.05, 0.1, 0.3]
    # search based on the result of the first search
    lambda_over_grid = [0.0001, 0.001, 0.01, 0.05, 0.1]
    lambda_under_grid = [0.0001, 0.001, 0.01, 0.05, 0.1]
    theta_queue_grid = [0.0001, 0.001, 0.01, 0.05, 0.1]


    # snapshots
    snapshots = load_venues(df, fee, rebate)
    bucket_snapshots = snapshots[:540]  # Use 9min window

    # four models
    best_params, our_total_cost, our_avg_price, our_cum_cost = grid_search(bucket_snapshots, lambda_over_grid, lambda_under_grid, theta_queue_grid, order_size)
    best_ask_cost, best_ask_price, best_ask_cum = take_the_best(bucket_snapshots, order_size)
    twap_cost, twap_price, twap_cum = TWAP(bucket_snapshots, order_size)
    vwap_cost, vwap_price, vwap_cum = VWAP(bucket_snapshots, order_size)

    # saving
    savings_vs_best_ask = (best_ask_price - our_avg_price) / best_ask_price * 10000 if best_ask_price else None
    savings_vs_twap = (twap_price - our_avg_price) / twap_price * 10000 if twap_price else None
    savings_vs_vwap = (vwap_price - our_avg_price) / vwap_price * 10000 if vwap_price else None

    # plot
    plt.figure(figsize=(10, 6)) 

    plt.plot(range(len(our_cum_cost)), our_cum_cost, label='Cont-Kukanov')
    plt.plot(range(len(best_ask_cum)), best_ask_cum, label="Best Ask")
    plt.plot(range(len(twap_cum)), twap_cum, label="TWAP")
    plt.plot(range(len(vwap_cum)), vwap_cum, label="VWAP")
    plt.xlabel("Shares Bought", fontsize=12)
    plt.ylabel("Cumulative Cost", fontsize=12)
    plt.title("Cumulative Cost vs Shares Bought (9-min Window)", fontsize=14, fontweight='bold')
    plt.legend(title="Execution Strategies", fontsize=10, title_fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout() 
    plt.savefig("results.png", dpi=300) 
    plt.show()


    output = {
        "best_parameters": best_params,
        "our_strategy": {"total_cash_spent": our_total_cost, "average_fill_price": our_avg_price},
        "best_ask": {"total_cash_spent": best_ask_cost, "average_fill_price": best_ask_price},
        "twap": {"total_cash_spent": twap_cost, "average_fill_price": twap_price},
        "vwap": {"total_cash_spent": vwap_cost, "average_fill_price": vwap_price},
        "savings_vs_best_ask": savings_vs_best_ask,
        "savings_vs_twap": savings_vs_twap,
        "savings_vs_vwap": savings_vs_vwap
    }

    print(json.dumps(output, indent=4))

if __name__ == "__main__":
    main()

