"""
OmniCalc AG-UI & A2UI FastAPI Server
Exposes Server-Sent Events (SSE) stream for AG-UI and reactive state mutation endpoints.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, Query, Request, Body
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load local environment variables from .env
load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .agent.orchestrator import OmniCalcAgent
from .agent.advisory import evaluate_state_delta
from .tools.loan_calc import calculate_loan_emi
from .tools.eb_bill_calc import calculate_eb_bill
from .tools.budget_calc import calculate_budget

app = FastAPI(title="OmniCalc Agent (A2UI + AG-UI)")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = OmniCalcAgent()

# Path to frontend assets
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "has_gemini_key": bool(os.getenv("GEMINI_API_KEY")),
        "agent": "omni-calc-agent",
        "protocol": ["AG-UI", "A2UI"]
    }


@app.get("/api/agent/stream")
async def stream_agent(prompt: str = Query("Calculate home loan EMI for 400k at 6.5% for 30 years")):
    """
    Server-Sent Events endpoint streaming standardized AG-UI events.
    """
    async def event_generator():
        try:
            async for event in agent.stream_run(prompt=prompt):
                yield event.to_sse()
        except Exception as e:
            err_payload = {
                "event": "RunErrorEvent",
                "run_id": "error-run",
                "error_message": str(e)
            }
            yield f"event: RunErrorEvent\ndata: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/agent/state-delta")
async def handle_state_delta(body: Dict[str, Any] = Body(...)):
    """
    Receives an AG-UI StateDeltaEvent when the user interacts with an A2UI widget.
    Evaluates computed fields and triggers the advisory engine.
    """
    surface_id = body.get("surfaceId", "")
    data_model = body.get("dataModel", {})

    # Recompute values based on updated inputs
    updated_model = data_model.copy()

    if surface_id == "home-loan-calculator" or "loan" in updated_model:
        loan = updated_model.get("loan", {})
        amt = float(loan.get("amount", 400000))
        rate = float(loan.get("rate", 6.5))
        tenure = float(loan.get("tenure", 30))
        prepay = float(loan.get("prepayment", 0))

        res = calculate_loan_emi(amt, rate, tenure, prepay)
        loan["emi"] = res["base_emi"]
        loan["total_interest"] = res["total_interest_paid"]
        loan["total_payment"] = res["baseline_total_payment"]
        updated_model["loan"] = loan

    elif surface_id == "eb-bill-calculator" or "eb" in updated_model:
        eb = updated_model.get("eb", {})
        units = float(eb.get("units", 350))
        cat = str(eb.get("category", "domestic"))
        solar = float(eb.get("solar", 0))

        res = calculate_eb_bill(units, cat, solar)
        eb["fixed_charge"] = res["fixed_charge"]
        eb["energy_charge"] = res["energy_charge"]
        eb["total_bill"] = res["total_bill"]
        eb["tier"] = res["current_tier"]
        updated_model["eb"] = eb

    elif surface_id == "budget-planner" or "budget" in updated_model:
        budget = updated_model.get("budget", {})
        income = float(budget.get("income", 5000))
        n_pct = float(budget.get("needs_pct", 50))
        w_pct = float(budget.get("wants_pct", 30))
        s_pct = float(budget.get("savings_pct", 20))

        res = calculate_budget(income, n_pct, w_pct, s_pct)
        budget["needs_val"] = res["needs_target"]
        budget["wants_val"] = res["wants_target"]
        budget["savings_val"] = res["savings_target"]
        budget["status"] = res["health_status"]
        updated_model["budget"] = budget

    # Proactive advice detection
    advisory = evaluate_state_delta(surface_id, updated_model)

    return {
        "status": "success",
        "surfaceId": surface_id,
        "updatedDataModel": updated_model,
        "advisory": advisory
    }


# Mount frontend static directory
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")
