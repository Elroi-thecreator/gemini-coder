"""
Agent Orchestrator & A2UI Generator
Uses Google GenAI SDK (Gemini) to process prompts and synthesize A2UI component surfaces
streamed over AG-UI protocol events.
"""
import os
import uuid
import time
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional

from ..protocol.agui_events import (
    AGUIEvent, RunStartedEvent, RunFinishedEvent,
    TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent,
    ToolCallStartEvent, ToolCallEndEvent, CustomEvent
)
from ..tools.loan_calc import calculate_loan_emi
from ..tools.eb_bill_calc import calculate_eb_bill
from ..tools.budget_calc import calculate_budget

# Try importing google-genai
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class OmniCalcAgent:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if HAS_GENAI and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini Client: {e}")

    async def stream_run(self, prompt: str, run_id: Optional[str] = None) -> AsyncGenerator[AGUIEvent, None]:
        """
        Executes an agent run for a user query and yields AG-UI SSE protocol events.
        """
        run_id = run_id or str(uuid.uuid4())
        msg_id = str(uuid.uuid4())

        # 1. Emit RunStartedEvent
        yield RunStartedEvent(run_id=run_id, agent_id="omni-calc-agent", prompt=prompt)
        await asyncio.sleep(0.05)

        # 2. Emit TextMessageStartEvent
        yield TextMessageStartEvent(message_id=msg_id)

        prompt_lower = prompt.lower()

        # Classify intent
        if any(w in prompt_lower for w in ["home loan", "mortgage", "emi", "housing loan", "loan"]):
            intent = "loan"
        elif any(w in prompt_lower for w in ["eb", "electricity", "power bill", "tariff", "kwh", "units"]):
            intent = "eb"
        elif any(w in prompt_lower for w in ["budget", "planner", "50/30/20", "savings", "expense"]):
            intent = "budget"
        else:
            intent = "loan"  # default showcase

        # 3. Stream text explanation
        if intent == "loan":
            intro_text = (
                "I've configured an interactive **Home Loan EMI Calculator** for you below. "
                "You can drag the loan amount, interest rate, and tenure sliders to observe how your monthly payment "
                "and overall interest change. Try adding a prepayment to see how quickly you can become debt-free!"
            )
        elif intent == "eb":
            intro_text = (
                "Here is your **Tiered Electricity (EB) Bill Estimator**. "
                "Adjust the units consumed slider to see your slab-by-slab charges, fixed connection fees, "
                "and solar net-metering credits in real-time."
            )
        else:
            intro_text = (
                "I have generated a **50/30/20 Smart Budget Planner** surface for you. "
                "Specify your take-home pay and modify the allocation sliders to balance essential needs, "
                "lifestyle spending, and wealth accumulation."
            )

        # Stream text chunks
        for word in intro_text.split(" "):
            yield TextMessageContentEvent(message_id=msg_id, delta=word + " ")
            await asyncio.sleep(0.02)

        yield TextMessageEndEvent(message_id=msg_id)

        # 4. Notify tool call
        tool_id = str(uuid.uuid4())
        tool_name = f"synthesize_{intent}_surface"
        yield ToolCallStartEvent(tool_call_id=tool_id, tool_name=tool_name)
        await asyncio.sleep(0.05)

        # 5. Build A2UI Declarative Payloads
        if intent == "loan":
            surface_id = "home-loan-calculator"
            surface_title = "Home Loan & Mortgage EMI Calculator"
            components, data_model = self._build_loan_surface()
        elif intent == "eb":
            surface_id = "eb-bill-calculator"
            surface_title = "Tiered Electricity (EB) Bill Calculator"
            components, data_model = self._build_eb_surface()
        else:
            surface_id = "budget-planner"
            surface_title = "50/30/20 Budget Planner & Health Audit"
            components, data_model = self._build_budget_surface()

        yield ToolCallEndEvent(tool_call_id=tool_id, tool_name=tool_name, result={"status": "success"})

        # 6. Stream A2UI CustomEvents over AG-UI pipe
        # a2ui:createSurface
        yield CustomEvent(
            custom_type="a2ui:createSurface",
            data={
                "surfaceId": surface_id,
                "title": surface_title,
                "rootComponentId": "root-card"
            }
        )

        # a2ui:updateComponents
        yield CustomEvent(
            custom_type="a2ui:updateComponents",
            data={
                "surfaceId": surface_id,
                "components": components
            }
        )

        # a2ui:updateDataModel
        yield CustomEvent(
            custom_type="a2ui:updateDataModel",
            data={
                "surfaceId": surface_id,
                "dataModel": data_model
            }
        )

        # 7. Complete run
        yield RunFinishedEvent(run_id=run_id, status="completed")

    def _build_loan_surface(self) -> (List[Dict[str, Any]], Dict[str, Any]):
        calc = calculate_loan_emi(400000, 6.5, 30, 0)
        data_model = {
            "loan": {
                "amount": 400000,
                "rate": 6.5,
                "tenure": 30,
                "prepayment": 0,
                "emi": calc["base_emi"],
                "total_interest": calc["baseline_interest"],
                "total_payment": calc["baseline_total_payment"]
            }
        }

        components = [
            {
                "id": "root-card",
                "component": {
                    "Card": {
                        "title": "Home Loan EMI Calculator",
                        "subtitle": "Interactive reducing-balance mortgage and prepayment simulator",
                        "children": {"explicitList": ["metrics-row", "divider-1", "controls-col", "divider-2", "prepayment-card"]},
                        "variant": "elevated"
                    }
                }
            },
            {
                "id": "metrics-row",
                "component": {
                    "Row": {
                        "children": {"explicitList": ["metric-emi", "metric-interest", "metric-total"]},
                        "justify": "between"
                    }
                }
            },
            {
                "id": "metric-emi",
                "component": {
                    "Metric": {
                        "label": "Monthly EMI",
                        "valuePath": "/loan/emi",
                        "format": "currency",
                        "subtext": "Principal + Interest per month",
                        "color": "indigo"
                    }
                }
            },
            {
                "id": "metric-interest",
                "component": {
                    "Metric": {
                        "label": "Total Interest",
                        "valuePath": "/loan/total_interest",
                        "format": "currency",
                        "subtext": "Interest paid over tenure",
                        "color": "rose"
                    }
                }
            },
            {
                "id": "metric-total",
                "component": {
                    "Metric": {
                        "label": "Total Repayment",
                        "valuePath": "/loan/total_payment",
                        "format": "currency",
                        "subtext": "Principal + Total Interest",
                        "color": "emerald"
                    }
                }
            },
            {"id": "divider-1", "component": {"Divider": {}}},
            {
                "id": "controls-col",
                "component": {
                    "Column": {
                        "children": {"explicitList": ["slider-amount", "slider-rate", "slider-tenure"]},
                        "gap": 4
                    }
                }
            },
            {
                "id": "slider-amount",
                "component": {
                    "Slider": {
                        "label": "Loan Amount ($)",
                        "min": 50000,
                        "max": 1500000,
                        "step": 10000,
                        "valuePath": "/loan/amount",
                        "format": "currency"
                    }
                }
            },
            {
                "id": "slider-rate",
                "component": {
                    "Slider": {
                        "label": "Interest Rate (%)",
                        "min": 1.0,
                        "max": 15.0,
                        "step": 0.1,
                        "valuePath": "/loan/rate",
                        "format": "percent",
                        "unit": "%"
                    }
                }
            },
            {
                "id": "slider-tenure",
                "component": {
                    "Slider": {
                        "label": "Tenure (Years)",
                        "min": 5,
                        "max": 30,
                        "step": 1,
                        "valuePath": "/loan/tenure",
                        "format": "integer",
                        "unit": " Years"
                    }
                }
            },
            {"id": "divider-2", "component": {"Divider": {}}},
            {
                "id": "prepayment-card",
                "component": {
                    "Card": {
                        "title": "Accelerated Prepayment Optimizer",
                        "subtitle": "Test how extra payments reduce your payoff date",
                        "children": {"explicitList": ["slider-prepayment"]},
                        "variant": "outlined"
                    }
                }
            },
            {
                "id": "slider-prepayment",
                "component": {
                    "Slider": {
                        "label": "Monthly Prepayment ($)",
                        "min": 0,
                        "max": 2000,
                        "step": 50,
                        "valuePath": "/loan/prepayment",
                        "format": "currency"
                    }
                }
            }
        ]

        return components, data_model

    def _build_eb_surface(self) -> (List[Dict[str, Any]], Dict[str, Any]):
        calc = calculate_eb_bill(350, "domestic", 0)
        data_model = {
            "eb": {
                "units": 350,
                "category": "domestic",
                "solar": 0,
                "fixed_charge": calc["fixed_charge"],
                "energy_charge": calc["energy_charge"],
                "total_bill": calc["total_bill"],
                "tier": calc["current_tier"]
            }
        }

        components = [
            {
                "id": "root-card",
                "component": {
                    "Card": {
                        "title": "Tiered Electricity (EB) Bill Calculator",
                        "subtitle": "Progressive tariff slab estimator with solar net-metering",
                        "children": {"explicitList": ["metrics-row", "divider-1", "controls-col", "divider-2", "solar-card"]},
                        "variant": "elevated"
                    }
                }
            },
            {
                "id": "metrics-row",
                "component": {
                    "Row": {
                        "children": {"explicitList": ["metric-total-bill", "metric-energy", "metric-fixed"]},
                        "justify": "between"
                    }
                }
            },
            {
                "id": "metric-total-bill",
                "component": {
                    "Metric": {
                        "label": "Total Estimated Bill",
                        "valuePath": "/eb/total_bill",
                        "format": "currency",
                        "subtext": "Total amount payable",
                        "color": "amber"
                    }
                }
            },
            {
                "id": "metric-energy",
                "component": {
                    "Metric": {
                        "label": "Energy Charges",
                        "valuePath": "/eb/energy_charge",
                        "format": "currency",
                        "subtext": "Based on progressive slabs",
                        "color": "indigo"
                    }
                }
            },
            {
                "id": "metric-fixed",
                "component": {
                    "Metric": {
                        "label": "Fixed Connection Fee",
                        "valuePath": "/eb/fixed_charge",
                        "format": "currency",
                        "subtext": "Monthly standing charge",
                        "color": "blue"
                    }
                }
            },
            {"id": "divider-1", "component": {"Divider": {}}},
            {
                "id": "controls-col",
                "component": {
                    "Column": {
                        "children": {"explicitList": ["slider-units", "picker-category"]},
                        "gap": 4
                    }
                }
            },
            {
                "id": "slider-units",
                "component": {
                    "Slider": {
                        "label": "Units Consumed (kWh)",
                        "min": 0,
                        "max": 1000,
                        "step": 10,
                        "valuePath": "/eb/units",
                        "unit": " kWh"
                    }
                }
            },
            {
                "id": "picker-category",
                "component": {
                    "ChoicePicker": {
                        "label": "Consumer Tariff Category",
                        "options": [
                            {"label": "Domestic / Residential", "value": "domestic"},
                            {"label": "Commercial / Retail", "value": "commercial"}
                        ],
                        "valuePath": "/eb/category"
                    }
                }
            },
            {"id": "divider-2", "component": {"Divider": {}}},
            {
                "id": "solar-card",
                "component": {
                    "Card": {
                        "title": "Rooftop Solar Offset",
                        "subtitle": "Deduct self-generated green energy credits",
                        "children": {"explicitList": ["slider-solar"]},
                        "variant": "outlined"
                    }
                }
            },
            {
                "id": "slider-solar",
                "component": {
                    "Slider": {
                        "label": "Solar Energy Generated (kWh)",
                        "min": 0,
                        "max": 500,
                        "step": 10,
                        "valuePath": "/eb/solar",
                        "unit": " kWh"
                    }
                }
            }
        ]

        return components, data_model

    def _build_budget_surface(self) -> (List[Dict[str, Any]], Dict[str, Any]):
        calc = calculate_budget(5000, 50, 30, 20)
        data_model = {
            "budget": {
                "income": 5000,
                "needs_pct": 50,
                "wants_pct": 30,
                "savings_pct": 20,
                "needs_val": calc["needs_target"],
                "wants_val": calc["wants_target"],
                "savings_val": calc["savings_target"],
                "status": calc["health_status"]
            }
        }

        components = [
            {
                "id": "root-card",
                "component": {
                    "Card": {
                        "title": "50/30/20 Smart Budget Planner",
                        "subtitle": "Personal finance allocation framework & health audit",
                        "children": {"explicitList": ["metrics-row", "divider-1", "controls-col"]},
                        "variant": "elevated"
                    }
                }
            },
            {
                "id": "metrics-row",
                "component": {
                    "Row": {
                        "children": {"explicitList": ["metric-needs", "metric-wants", "metric-savings"]},
                        "justify": "between"
                    }
                }
            },
            {
                "id": "metric-needs",
                "component": {
                    "Metric": {
                        "label": "Needs (Housing, Food)",
                        "valuePath": "/budget/needs_val",
                        "format": "currency",
                        "subtext": "Target: 50% max",
                        "color": "blue"
                    }
                }
            },
            {
                "id": "metric-wants",
                "component": {
                    "Metric": {
                        "label": "Wants (Dining, Fun)",
                        "valuePath": "/budget/wants_val",
                        "format": "currency",
                        "subtext": "Target: 30% max",
                        "color": "amber"
                    }
                }
            },
            {
                "id": "metric-savings",
                "component": {
                    "Metric": {
                        "label": "Savings & Investments",
                        "valuePath": "/budget/savings_val",
                        "format": "currency",
                        "subtext": "Target: 20% min",
                        "color": "emerald"
                    }
                }
            },
            {"id": "divider-1", "component": {"Divider": {}}},
            {
                "id": "controls-col",
                "component": {
                    "Column": {
                        "children": {"explicitList": ["slider-income", "slider-needs", "slider-wants", "slider-savings"]},
                        "gap": 4
                    }
                }
            },
            {
                "id": "slider-income",
                "component": {
                    "Slider": {
                        "label": "Monthly Take-Home Income ($)",
                        "min": 1000,
                        "max": 30000,
                        "step": 250,
                        "valuePath": "/budget/income",
                        "format": "currency"
                    }
                }
            },
            {
                "id": "slider-needs",
                "component": {
                    "Slider": {
                        "label": "Needs Allocation (%)",
                        "min": 10,
                        "max": 80,
                        "step": 5,
                        "valuePath": "/budget/needs_pct",
                        "unit": "%"
                    }
                }
            },
            {
                "id": "slider-wants",
                "component": {
                    "Slider": {
                        "label": "Wants Allocation (%)",
                        "min": 5,
                        "max": 50,
                        "step": 5,
                        "valuePath": "/budget/wants_pct",
                        "unit": "%"
                    }
                }
            },
            {
                "id": "slider-savings",
                "component": {
                    "Slider": {
                        "label": "Savings Allocation (%)",
                        "min": 5,
                        "max": 50,
                        "step": 5,
                        "valuePath": "/budget/savings_pct",
                        "unit": "%"
                    }
                }
            }
        ]

        return components, data_model
