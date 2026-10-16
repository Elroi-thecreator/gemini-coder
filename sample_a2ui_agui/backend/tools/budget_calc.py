"""
Budget Planner & 50/30/20 Allocation Engine
Computes budget categories, variances, and financial health benchmarks.
"""
from typing import Dict, Any


def calculate_budget(
    monthly_income: float,
    needs_pct: float = 50.0,
    wants_pct: float = 30.0,
    savings_pct: float = 20.0,
    current_expenses: float = 0.0
) -> Dict[str, Any]:
    """
    Computes 50/30/20 target amounts and surplus/deficit metrics.
    """
    income = max(0.0, float(monthly_income))
    n_pct = max(0.0, float(needs_pct))
    w_pct = max(0.0, float(wants_pct))
    s_pct = max(0.0, float(savings_pct))

    needs_target = round(income * (n_pct / 100.0), 2)
    wants_target = round(income * (w_pct / 100.0), 2)
    savings_target = round(income * (s_pct / 100.0), 2)

    total_allocated = needs_target + wants_target + savings_target
    unallocated = round(income - total_allocated, 2)
    surplus_deficit = round(income - current_expenses, 2) if current_expenses > 0 else 0.0

    # Financial health status
    if s_pct >= 20.0 and n_pct <= 50.0:
        health_status = "Excellent - Balanced Growth"
        health_color = "emerald"
    elif s_pct >= 10.0:
        health_status = "Moderate - Room to Optimize"
        health_color = "amber"
    else:
        health_status = "At Risk - Savings Below Safe Margin"
        health_color = "rose"

    return {
        "monthly_income": income,
        "needs_pct": n_pct,
        "wants_pct": w_pct,
        "savings_pct": s_pct,
        "needs_target": needs_target,
        "wants_target": wants_target,
        "savings_target": savings_target,
        "unallocated": unallocated,
        "surplus_deficit": surplus_deficit,
        "health_status": health_status,
        "health_color": health_color,
    }
