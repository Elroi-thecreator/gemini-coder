"""
Home Loan & Mortgage EMI Calculator Tool
Provides high-precision financial computations, amortization schedules, and prepayment savings.
"""
from typing import Dict, Any, List


def calculate_loan_emi(
    amount: float,
    annual_rate: float,
    tenure_years: float,
    monthly_prepayment: float = 0.0
) -> Dict[str, Any]:
    """
    Computes monthly EMI, total interest, total repayment, and prepayment effects.
    """
    principal = float(amount)
    rate = float(annual_rate)
    tenure = float(tenure_years)
    prepay = float(monthly_prepayment)

    if principal <= 0 or tenure <= 0:
        return {
            "emi": 0.0,
            "total_interest": 0.0,
            "total_payment": 0.0,
            "months_to_pay": 0,
            "interest_saved": 0.0,
            "tenure_saved_months": 0
        }

    monthly_rate = (rate / 100.0) / 12.0
    total_months = int(tenure * 12)

    if monthly_rate == 0:
        base_emi = principal / total_months
    else:
        factor = (1.0 + monthly_rate) ** total_months
        base_emi = principal * monthly_rate * factor / (factor - 1.0)

    # Calculate baseline total interest
    baseline_total_payment = base_emi * total_months
    baseline_total_interest = baseline_total_payment - principal

    # Prepayment simulation
    balance = principal
    actual_months = 0
    total_interest_with_prepay = 0.0

    while balance > 0 and actual_months < total_months * 2:
        actual_months += 1
        interest_charge = balance * monthly_rate
        total_interest_with_prepay += interest_charge
        
        principal_portion = (base_emi - interest_charge) + prepay
        balance -= principal_portion
        if balance <= 0:
            break

    interest_saved = max(0.0, baseline_total_interest - total_interest_with_prepay)
    tenure_saved = max(0, total_months - actual_months)

    return {
        "amount": principal,
        "rate": rate,
        "tenure_years": tenure,
        "base_emi": round(base_emi, 2),
        "total_months": total_months,
        "baseline_interest": round(baseline_total_interest, 2),
        "baseline_total_payment": round(baseline_total_payment, 2),
        "monthly_prepayment": prepay,
        "actual_months": actual_months,
        "total_interest_paid": round(total_interest_with_prepay if prepay > 0 else baseline_total_interest, 2),
        "interest_saved": round(interest_saved, 2),
        "tenure_saved_months": tenure_saved,
    }


def calculate_tenure_from_emi(
    amount: float,
    annual_rate: float,
    monthly_emi: float
) -> Dict[str, Any]:
    """
    Inverse EMI calculation: Solves for the total number of months and years
    required to pay off a loan given principal, interest rate, and monthly EMI.
    """
    import math

    principal = float(amount)
    rate = float(annual_rate)
    emi = float(monthly_emi)

    if principal <= 0 or emi <= 0 or rate <= 0:
        return {"error": "Principal, interest rate, and monthly EMI must be positive."}

    monthly_rate = (rate / 100.0) / 12.0
    monthly_interest = principal * monthly_rate

    if emi <= monthly_interest:
        return {
            "error": (
                f"Monthly EMI ({emi:,.0f}) is less than or equal to monthly interest ({monthly_interest:,.0f}). "
                "The loan balance will never reduce. Please enter an EMI higher than the monthly interest charge."
            ),
            "monthly_interest": round(monthly_interest, 2)
        }

    ratio = (principal * monthly_rate) / emi
    total_months = -math.log(1.0 - ratio) / math.log(1.0 + monthly_rate)
    years = int(total_months // 12)
    rem_months = int(round(total_months % 12))
    if rem_months == 12:
        years += 1
        rem_months = 0

    total_payment = total_months * emi
    total_interest = total_payment - principal

    # Baseline 20-year comparison
    r_20 = calculate_loan_emi(principal, rate, 20, 0)
    interest_saved_vs_20yr = max(0.0, r_20["baseline_interest"] - total_interest)

    return {
        "amount": principal,
        "rate": rate,
        "monthly_emi": emi,
        "total_months": round(total_months, 1),
        "years": years,
        "rem_months": rem_months,
        "total_payment": round(total_payment, 2),
        "total_interest": round(total_interest, 2),
        "interest_saved_vs_20yr": round(interest_saved_vs_20yr, 2)
    }
