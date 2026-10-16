"""
Advisory & Proactive State Delta Reasoning Engine
Analyzes user slider adjustments and generates contextual financial and tariff insights.
"""
from typing import Dict, Any, Optional
from ..tools.loan_calc import calculate_loan_emi
from ..tools.eb_bill_calc import calculate_eb_bill
from ..tools.budget_calc import calculate_budget


def evaluate_state_delta(surface_id: str, full_model: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Evaluates the updated data model and returns an advisory insight if noteworthy changes occurred.
    """
    if surface_id == "home-loan-calculator" or "loan" in full_model:
        loan_data = full_model.get("loan", {})
        amount = float(loan_data.get("amount", 300000))
        rate = float(loan_data.get("rate", 6.5))
        tenure = float(loan_data.get("tenure", 30))
        prepay = float(loan_data.get("prepayment", 0))

        calc = calculate_loan_emi(amount, rate, tenure, prepay)
        
        # Check for valuable insights
        if prepay > 0:
            return {
                "title": "Prepayment Impact Detected",
                "message": (
                    f"Adding a ${prepay:,.0f}/month prepayment saves you "
                    f"${calc['interest_saved']:,.0f} in interest and pays off your mortgage "
                    f"{calc['tenure_saved_months']} months ({calc['tenure_saved_months'] // 12} yrs) early!"
                ),
                "severity": "success"
            }
        elif tenure <= 15:
            base_30 = calculate_loan_emi(amount, rate, 30, 0)
            diff_interest = base_30["baseline_interest"] - calc["baseline_interest"]
            return {
                "title": "Shorter Tenure Advantage",
                "message": (
                    f"A 15-year loan saves ${diff_interest:,.0f} in total interest compared to a 30-year term. "
                    f"Monthly EMI is ${calc['base_emi']:,.0f}."
                ),
                "severity": "info"
            }
        elif rate > 8.0:
            return {
                "title": "High Interest Rate Alert",
                "message": "At rates above 8%, total interest paid over 30 years exceeds the original loan amount! Consider refinancing or prepaying.",
                "severity": "warning"
            }

    elif surface_id == "eb-bill-calculator" or "eb" in full_model:
        eb_data = full_model.get("eb", {})
        units = float(eb_data.get("units", 350))
        cat = str(eb_data.get("category", "domestic"))
        solar = float(eb_data.get("solar", 0))

        calc = calculate_eb_bill(units, cat, solar)
        
        if 0 < calc["units_to_next_tier"] <= 30:
            return {
                "title": "Tariff Bracket Warning",
                "message": (
                    f"You are only {calc['units_to_next_tier']} units away from entering the next higher tariff tier. "
                    "Conserving just a few units this cycle can prevent an exponential price jump."
                ),
                "severity": "warning"
            }
        elif solar > 0:
            savings = round(solar * 3.5, 2)
            return {
                "title": "Solar Generation Credit",
                "message": f"Your {solar:.0f} kWh solar generation offsets an estimated ${savings} in electricity bills this month!",
                "severity": "success"
            }

    elif surface_id == "budget-planner" or "budget" in full_model:
        budget_data = full_model.get("budget", {})
        income = float(budget_data.get("income", 5000))
        savings_pct = float(budget_data.get("savings_pct", 20))
        needs_pct = float(budget_data.get("needs_pct", 50))

        if savings_pct < 15:
            return {
                "title": "Low Savings Rate",
                "message": f"Your current savings allocation is {savings_pct:.0f}%. Increasing this to 20% will build a robust 6-month safety net.",
                "severity": "warning"
            }
        elif savings_pct >= 25:
            return {
                "title": "Aggressive Wealth Accumulation",
                "message": f"Allocating {savings_pct:.0f}% towards investments will accelerate your path to financial independence!",
                "severity": "success"
            }

    return None
