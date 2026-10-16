"""
Tiered Electricity (EB) Bill Calculation Engine
Computes progressive tiered tariffs, slab breakdown, fixed charges, and efficiency thresholds.
"""
from typing import Dict, Any, List


# Standard progressive tariff structures
TARIFF_STRUCTURES = {
    "domestic": {
        "fixed_charge": 5.0,  # Fixed monthly meter/connection fee ($)
        "slabs": [
            {"min": 0, "max": 100, "rate": 0.0, "label": "0 - 100 units (Subsidized)"},
            {"min": 100, "max": 200, "rate": 2.25, "label": "101 - 200 units"},
            {"min": 200, "max": 500, "rate": 4.50, "label": "201 - 500 units"},
            {"min": 500, "max": float("inf"), "rate": 6.75, "label": "500+ units (Peak Tier)"},
        ]
    },
    "commercial": {
        "fixed_charge": 15.0,
        "slabs": [
            {"min": 0, "max": 150, "rate": 5.00, "label": "0 - 150 units"},
            {"min": 150, "max": 400, "rate": 7.50, "label": "151 - 400 units"},
            {"min": 400, "max": float("inf"), "rate": 9.80, "label": "400+ units (Commercial Peak)"},
        ]
    }
}


def calculate_eb_bill(
    units_consumed: float,
    category: str = "domestic",
    solar_generation: float = 0.0
) -> Dict[str, Any]:
    """
    Computes progressive tiered electricity bill and slab distribution.
    """
    cat = category.lower() if category.lower() in TARIFF_STRUCTURES else "domestic"
    structure = TARIFF_STRUCTURES[cat]
    
    gross_units = max(0.0, float(units_consumed))
    solar_credit = max(0.0, float(solar_generation))
    net_units = max(0.0, gross_units - solar_credit)

    fixed_charge = structure["fixed_charge"]
    energy_charge = 0.0
    slab_breakdown: List[Dict[str, Any]] = []

    remaining_units = net_units
    units_to_next_tier = 0.0
    current_tier_label = ""

    for slab in structure["slabs"]:
        slab_capacity = slab["max"] - slab["min"]
        if remaining_units > 0:
            units_in_slab = min(remaining_units, slab_capacity)
            charge_in_slab = units_in_slab * slab["rate"]
            energy_charge += charge_in_slab
            remaining_units -= units_in_slab
            current_tier_label = slab["label"]
            
            slab_breakdown.append({
                "label": slab["label"],
                "rate": slab["rate"],
                "units": round(units_in_slab, 1),
                "cost": round(charge_in_slab, 2)
            })
            
            # If we are inside this slab, calculate how many units until next slab
            if remaining_units == 0 and slab["max"] != float("inf"):
                units_to_next_tier = round(slab["max"] - net_units, 1)
        else:
            slab_breakdown.append({
                "label": slab["label"],
                "rate": slab["rate"],
                "units": 0.0,
                "cost": 0.0
            })

    total_bill = fixed_charge + energy_charge

    return {
        "gross_units": gross_units,
        "solar_generation": solar_credit,
        "net_units": net_units,
        "category": cat.capitalize(),
        "fixed_charge": round(fixed_charge, 2),
        "energy_charge": round(energy_charge, 2),
        "total_bill": round(total_bill, 2),
        "current_tier": current_tier_label,
        "units_to_next_tier": units_to_next_tier,
        "slabs": slab_breakdown
    }
