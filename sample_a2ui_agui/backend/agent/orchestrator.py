"""
Agent Orchestrator & A2UI Generator
Uses Google GenAI SDK (Gemini) to process prompts, converse naturally with human language,
and dynamically synthesize A2UI component surfaces streamed over AG-UI protocol events.
"""
import os
import re
import uuid
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple

from ..protocol.agui_events import (
    AGUIEvent, RunStartedEvent, RunFinishedEvent,
    TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent,
    ToolCallStartEvent, ToolCallEndEvent, CustomEvent
)
from ..tools.loan_calc import calculate_loan_emi, calculate_tenure_from_emi
from ..tools.eb_bill_calc import calculate_eb_bill
from ..tools.budget_calc import calculate_budget

# Try importing google-genai
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


SYSTEM_PROMPT = """You are OmniCalc Agent, an intelligent financial and utility conversational assistant equipped with an interactive A2UI (Agent-to-User Interface) canvas.

Your goals:
1. Converse naturally, helpfully, and conversationally in clear Markdown.
2. If the user asks conceptual or informational questions (e.g. "What is an amortization schedule?", "Explain reducing balance vs flat rate", "How does solar net metering work?"), explain thoroughly in conversational prose. Do NOT reset the UI if they are just asking questions.
3. If the user wants to calculate, adjust, or view a calculator (Home Loan, Electricity Bill, or Budget Planner), provide a natural conversational explanation with the key results, AND append an action block at the very end of your response on a new line:

```a2ui_action
{"action": "create", "surface": "loan" | "eb" | "budget", "params": {"amount": 500000, "rate": 7.5, "tenure": 20, "prepayment": 200, "units": 450, "category": "domestic", "solar": 50, "income": 6000, "needs_pct": 50, "wants_pct": 30, "savings_pct": 20}}
```

If the user is just asking a question without requesting a calculator change, omit the action block or specify `{"action": "none", "surface": "none"}`.
"""


class OmniCalcAgent:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        self._init_client()

    def _init_client(self):
        key = os.getenv("GEMINI_API_KEY")
        if HAS_GENAI and key:
            try:
                self.client = genai.Client(api_key=key)
                self.api_key = key
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini Client: {e}")
                self.client = None

    def _get_client(self):
        current_key = os.getenv("GEMINI_API_KEY")
        if current_key != self.api_key or (current_key and not self.client):
            self._init_client()
        return self.client

    async def stream_run(self, prompt: str, run_id: Optional[str] = None) -> AsyncGenerator[AGUIEvent, None]:
        """
        Executes an agent run for a user query and yields AG-UI SSE protocol events.
        """
        run_id = run_id or str(uuid.uuid4())
        msg_id = str(uuid.uuid4())

        # 1. Emit RunStartedEvent
        yield RunStartedEvent(run_id=run_id, agent_id="omni-calc-agent", prompt=prompt)
        await asyncio.sleep(0.02)

        # 2. Emit TextMessageStartEvent
        yield TextMessageStartEvent(message_id=msg_id)

        client = self._get_client()
        action_data = None

        if client:
            # === Online Mode with Gemini API ===
            try:
                full_response = ""
                # Use gemini-2.5-flash with fallback
                stream = await client.aio.models.generate_content_stream(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.7,
                    )
                )

                action_buffer = ""
                in_action_block = False

                async for chunk in stream:
                    text_chunk = chunk.text or ""
                    full_response += text_chunk

                    # Filter out trailing a2ui_action block from the visible chat output
                    if "```a2ui_action" in text_chunk or "```a2ui_action" in full_response:
                        in_action_block = True

                    if not in_action_block:
                        yield TextMessageContentEvent(message_id=msg_id, delta=text_chunk)
                    else:
                        action_buffer += text_chunk

                # Parse action block if present
                m = re.search(r"```a2ui_action\s*(\{.*?\})\s*```", full_response, re.DOTALL)
                if m:
                    try:
                        action_data = json.loads(m.group(1))
                    except Exception as e:
                        print(f"Action parse error: {e}")

            except Exception as e:
                print(f"[Gemini API Error] Falling back to local reasoning: {e}")
                client = None  # trigger fallback below

        if not client:
            # === Intelligent Offline Conversational Reasoning Mode ===
            text_response, action_data = self._smart_conversational_reasoner(prompt)

            # Stream words with natural reading cadence
            words = text_response.split(" ")
            for i, word in enumerate(words):
                delta = word + (" " if i < len(words) - 1 else "")
                yield TextMessageContentEvent(message_id=msg_id, delta=delta)
                await asyncio.sleep(0.015)

        # Complete chat message stream
        yield TextMessageEndEvent(message_id=msg_id)

        # 3. Check if an A2UI Surface should be created or updated
        if action_data and action_data.get("surface") not in (None, "none"):
            surface_type = action_data.get("surface")
            params = action_data.get("params", {})

            tool_id = str(uuid.uuid4())
            tool_name = f"synthesize_{surface_type}_surface"
            yield ToolCallStartEvent(tool_call_id=tool_id, tool_name=tool_name)
            await asyncio.sleep(0.05)

            if surface_type == "loan":
                surface_id = "home-loan-calculator"
                surface_title = "Home Loan & Mortgage EMI Calculator"
                components, data_model = self._build_loan_surface(
                    amount=params.get("amount", 400000),
                    rate=params.get("rate", 6.5),
                    tenure=params.get("tenure", 30),
                    prepay=params.get("prepayment", 0),
                    currency=params.get("currency", "$")
                )
            elif surface_type == "eb":
                surface_id = "eb-bill-calculator"
                surface_title = "Tiered Electricity (EB) Bill Calculator"
                components, data_model = self._build_eb_surface(
                    units=params.get("units", 350),
                    category=params.get("category", "domestic"),
                    solar=params.get("solar", 0)
                )
            elif surface_type == "budget":
                surface_id = "budget-planner"
                surface_title = "50/30/20 Budget Planner & Health Audit"
                components, data_model = self._build_budget_surface(
                    income=params.get("income", 5000),
                    needs_pct=params.get("needs_pct", 50),
                    wants_pct=params.get("wants_pct", 30),
                    savings_pct=params.get("savings_pct", 20)
                )
            else:
                surface_id = None

            if surface_id:
                yield ToolCallEndEvent(tool_call_id=tool_id, tool_name=tool_name, result={"status": "success"})

                # Stream A2UI CustomEvents
                yield CustomEvent(
                    custom_type="a2ui:createSurface",
                    data={
                        "surfaceId": surface_id,
                        "title": surface_title,
                        "rootComponentId": "root-card"
                    }
                )
                yield CustomEvent(
                    custom_type="a2ui:updateComponents",
                    data={
                        "surfaceId": surface_id,
                        "components": components
                    }
                )
                yield CustomEvent(
                    custom_type="a2ui:updateDataModel",
                    data={
                        "surfaceId": surface_id,
                        "dataModel": data_model
                    }
                )

        # 4. Finish Run
        yield RunFinishedEvent(run_id=run_id, status="completed")

    def _smart_conversational_reasoner(self, prompt: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Parses user intent, extracts quantitative parameters, and returns a detailed
        conversational response and action schema when offline.
        """
        p = prompt.strip().lower()

        # 1. Greetings
        if re.search(r"\b(hi|hello|hey|who are you|what can you do|good morning|help)\b", p) and len(p.split()) <= 6:
            text = (
                "Hello! I am **OmniCalc Agent**, an AI assistant designed to converse with you about personal finance and utilities. "
                "I combine natural conversation with **A2UI** interactive calculators on the right.\n\n"
                "Here are some things you can ask me:\n"
                "- *\"Calculate loan for $500,000 at 7.5% for 20 years\"*\n"
                "- *\"What is reducing balance interest vs flat rate?\"*\n"
                "- *\"Estimate my electricity bill for 450 units with 100 kWh solar\"*\n"
                "- *\"Explain how the 50/30/20 budget rule works\"*\n\n"
                "What would you like to explore?"
            )
            return text, {"action": "none", "surface": "none"}

        # 2. Conceptual / Explanatory Questions (Do NOT force or reset UI)
        if any(q in p for q in ["what is emi", "explain emi", "how is emi calculated", "formula for emi"]):
            text = (
                "### Understanding Equated Monthly Installment (EMI)\n\n"
                "An **Equated Monthly Installment (EMI)** is the fixed monthly payment you make to a lender over a set loan term.\n\n"
                "#### The Mathematical Formula:\n"
                "$$\\text{EMI} = \\frac{P \\times r \\times (1+r)^n}{(1+r)^n - 1}$$\n\n"
                "- **$P$ (Principal):** The original loan amount borrowed.\n"
                "- **$r$ (Monthly Interest Rate):** Annual rate divided by $12 \\times 100$.\n"
                "- **$n$ (Tenure in Months):** Number of years $\\times 12$.\n\n"
                "Each EMI payment is split into two components: **interest** (higher in early years) and **principal repayment** (higher in later years). "
                "You can see this in action using the Home Loan Calculator sliders on the right!"
            )
            return text, {"action": "none", "surface": "none"}

        if any(q in p for q in ["amortization", "amortization schedule", "schedule"]):
            text = (
                "### What is an Amortization Schedule?\n\n"
                "An **Amortization Schedule** is a complete chronological table detailing every periodic payment over the lifetime of a loan.\n\n"
                "#### How Each Payment is Structured:\n"
                "1. **Early Years (Interest-Heavy):** Because the outstanding loan balance is largest at the beginning, a substantial portion of your monthly payment goes directly toward interest, with only a small portion chipping away at principal.\n"
                "2. **Later Years (Principal-Heavy):** As the principal steadily shrinks, interest charges diminish each month, accelerating principal repayment until the loan reaches zero.\n\n"
                "💡 **Pro-Tip:** Any extra payment (**prepayment**) made in the early years goes 100% toward principal, skipping years of interest compounding!"
            )
            return text, {"action": "none", "surface": "none"}

        if any(q in p for q in ["reducing balance", "flat rate", "flat vs reducing"]):
            text = (
                "### Reducing Balance vs. Flat Rate Loans\n\n"
                "Understanding the distinction between these two calculation methods is critical for borrowers:\n\n"
                "1. **Reducing Balance (Standard for Mortgages):**\n"
                "   Interest is calculated only on the *outstanding principal* at each monthly cycle. As you pay down debt, interest charges decrease.\n\n"
                "2. **Flat Rate (Often used in predatory loans):**\n"
                "   Interest is calculated on the *full original loan amount* throughout the entire tenure, even when you have paid off 90% of the principal! "
                "   A nominal 8% flat rate is roughly equivalent to a **14%–15% reducing rate**.\n\n"
                "Our OmniCalc Home Loan tool uses the **reducing balance formula** used by transparent regulated lenders."
            )
            return text, {"action": "none", "surface": "none"}

        if any(q in p for q in ["solar", "net meter", "how does solar work", "net metering"]):
            text = (
                "### How Rooftop Solar Net-Metering Works\n\n"
                "**Net Metering** is a billing mechanism that credits solar energy system owners for the electricity they add to the grid.\n\n"
                "- During sunny hours, your panels power your home and export surplus energy back into the grid.\n"
                "- At night, you draw power from the utility grid.\n"
                "- **The Math:** $\\text{Billed Units} = \\max(0, \\text{Gross Consumption} - \\text{Solar Export})$.\n\n"
                "Because electricity tariffs are progressive (tiered into slabs), shaving off the top 100–200 units with solar avoids the most expensive peak brackets!"
            )
            return text, {"action": "none", "surface": "none"}

        if any(q in p for q in ["50/30/20", "50 30 20", "budget rule", "how to budget"]):
            text = (
                "### The 50/30/20 Budgeting Framework\n\n"
                "Popularized by Sen. Elizabeth Warren, this rule categorizes after-tax income into three buckets:\n\n"
                "- **50% Needs:** Non-negotiables essential for survival and employment (Rent/Mortgage, Utilities, Groceries, Insurance, Minimum debt payments).\n"
                "- **30% Wants:** Lifestyle enhancements (Dining out, entertainment, vacations, shopping, streaming subscriptions).\n"
                "- **20% Savings & Debt Repayment:** Emergency fund creation, retirement contributions (401k/IRA/Mutual Funds), and accelerated debt payoff.\n\n"
                "Try adjusting the budget sliders on the right to test your current allocation!"
            )
            return text, {"action": "none", "surface": "none"}

        # 3. Calculation Requests (Extract parameters and generate/update surface)
        # A. Home Loan Calculation
        if any(w in p for w in ["loan", "mortgage", "emi", "housing loan", "borrow", "interest rate"]):
            # Currency detection
            is_indian_currency = bool(re.search(r"\b(lakh|lakhs|lac|lacs|crore|crores|inr|rs|rupee|rupees|₹)\b", p))
            curr_sym = "₹" if is_indian_currency else "$"

            # Extract Amount
            amt = 400000.0
            m_lakh = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakhs?|lac|lacs)", p)
            m_crore = re.search(r"(\d+(?:\.\d+)?)\s*(?:crores?|cr)", p)
            m_k = re.search(r"(\d+(?:\.\d+)?)\s*(?:k|thousand)", p)
            m_num = re.search(r"\$?(\d{1,3}(?:,\d{3})+|\d{4,9})", p)

            if m_crore:
                amt = float(m_crore.group(1)) * 10000000.0
            elif m_lakh:
                amt = float(m_lakh.group(1)) * 100000.0
            elif m_k:
                amt = float(m_k.group(1)) * 1000.0
            elif m_num:
                amt = float(m_num.group(1).replace(",", ""))

            # Extract Rate (e.g. "8.25 as interest", "with 8.25 interest", "rate of 8.25", "at 8.25%", "8.25%")
            rate = 6.5
            m_rate = (
                re.search(r"(?:interest\s*rate|rate|roi|interest)\s*(?:of|is|:)?\s*(\d+(?:\.\d+)?)", p) or
                re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|as\s*interest|interest)", p) or
                re.search(r"(?:at|with)\s*(\d+(?:\.\d+)?)\s*(?:as\s*interest|interest)?", p)
            )
            if m_rate:
                try:
                    val = float(m_rate.group(1))
                    if 0.5 <= val <= 35.0:
                        rate = val
                except ValueError:
                    pass

            # Extract EMI (e.g. "paying 22k as emi", "22k as emi", "emi of 22k", "paying 22000 as emi", "22000 emi")
            monthly_emi = None
            m_emi = (
                re.search(r"(?:paying|pay)?\s*(\d+(?:\.\d+)?)\s*(k|thousand)?\s*(?:as\s*emi|emi)", p) or
                re.search(r"(?:emi|monthly\s*payment)\s*(?:of|is|:)?\s*₹?\$?(\d+(?:\.\d+)?)\s*(k|thousand)?", p)
            )
            if m_emi:
                try:
                    val = float(m_emi.group(1))
                    has_k = (m_emi.lastindex and m_emi.group(2) and "k" in m_emi.group(2).lower()) or ("k" in p[m_emi.start():m_emi.end()+3].lower())
                    if has_k or val < 100:
                        val *= 1000.0
                    monthly_emi = val
                except (ValueError, IndexError):
                    pass

            # Check if user is asking to solve for tenure (e.g. "how many years", "how long", "how many months", "when to complete")
            is_asking_tenure = bool(re.search(r"how\s*many\s*(?:years?|months?)|how\s*long|when\s*(?:will\s*it|to)\s*(?:take\s*to\s*)?(?:complete|finish|pay\s*off)", p))

            if is_asking_tenure and monthly_emi:
                # Solve for tenure given Principal, Rate, and EMI!
                tenure_calc = calculate_tenure_from_emi(amt, rate, monthly_emi)

                if "error" in tenure_calc:
                    text = f"⚠️ **Cannot Calculate Tenure:** {tenure_calc['error']}"
                    return text, {"action": "none", "surface": "none"}

                years = tenure_calc["years"]
                months = tenure_calc["rem_months"]
                total_months = tenure_calc["total_months"]
                tot_interest = tenure_calc["total_interest"]
                tot_payment = tenure_calc["total_payment"]
                saved_vs_20 = tenure_calc["interest_saved_vs_20yr"]

                tenure_display = f"**{years} years and {months} months**" if months > 0 else f"**{years} years**"
                tenure_years_num = max(1, round(total_months / 12))

                text = (
                    f"For a home loan of **{curr_sym}{amt:,.0f}** at **{rate:.2f}% interest rate** paying **{curr_sym}{monthly_emi:,.0f}/month as EMI**:\n\n"
                    f"🎯 **Time Required to Complete:** {tenure_display} (~{int(round(total_months))} months total)\n\n"
                    f"- **Monthly EMI:** **{curr_sym}{monthly_emi:,.0f}**\n"
                    f"- **Total Interest Payable:** **{curr_sym}{tot_interest:,.0f}**\n"
                    f"- **Total Repayment Amount:** **{curr_sym}{tot_payment:,.0f}**\n\n"
                    f"💡 **Tenure Advantage:** By paying {curr_sym}{monthly_emi:,.0f}/month, you pay off your loan in under {years + 1} years, "
                    f"saving over **{curr_sym}{saved_vs_20:,.0f} in interest** compared to a standard 20-year mortgage!\n\n"
                    f"I've updated the interactive controls on the right to match your exact {tenure_display} payoff schedule."
                )

                return text, {
                    "action": "create",
                    "surface": "loan",
                    "params": {"amount": amt, "rate": rate, "tenure": tenure_years_num, "prepayment": 0, "currency": curr_sym}
                }

            # Standard Forward EMI Calculation
            tenure = 30.0
            m_tenure = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", p)
            if m_tenure:
                tenure = float(m_tenure.group(1))

            prepay = 0.0
            m_prepay = re.search(r"(?:prepay\w*|extra)\s*(?:of\s*)?\$?(\d+(?:,\d+)*(?:\.\d+)?)", p)
            if m_prepay:
                prepay = float(m_prepay.group(1).replace(",", ""))

            calc = calculate_loan_emi(amt, rate, tenure, prepay)

            text = (
                f"I've calculated your loan for **{curr_sym}{amt:,.0f}** at **{rate:.2f}% interest** over **{int(tenure)} years**:\n\n"
                f"- **Monthly EMI:** **{curr_sym}{calc['base_emi']:,.0f}** / month\n"
                f"- **Total Interest Payable:** **{curr_sym}{calc['baseline_interest']:,.0f}**\n"
                f"- **Total Repayment Amount:** **{curr_sym}{calc['baseline_total_payment']:,.0f}**\n\n"
            )
            if prepay > 0:
                text += (
                    f"💡 **Prepayment Benefit:** Adding a **{curr_sym}{prepay:,.0f}/mo** prepayment saves you "
                    f"**{curr_sym}{calc['interest_saved']:,.0f}** in interest and retires your debt "
                    f"**{calc['tenure_saved_months']} months ({calc['tenure_saved_months'] // 12} yrs) early**!\n\n"
                )

            text += "I have updated the interactive controls on the right so you can adjust the values live."
            return text, {
                "action": "create",
                "surface": "loan",
                "params": {"amount": amt, "rate": rate, "tenure": tenure, "prepayment": prepay, "currency": curr_sym}
            }

        # B. Electricity (EB) Bill Calculation
        if any(w in p for w in ["eb", "electricity", "power", "tariff", "kwh", "units"]):
            units = 350
            m_units = re.search(r"(\d+(?:\.\d+)?)\s*(?:units?|kwh)", p)
            if m_units:
                units = float(m_units.group(1))

            cat = "commercial" if "commercial" in p else "domestic"

            solar = 0
            m_solar = re.search(r"(\d+(?:\.\d+)?)\s*(?:units?|kwh)?\s*(?:solar)", p)
            if m_solar:
                solar = float(m_solar.group(1))

            calc = calculate_eb_bill(units, cat, solar)

            text = (
                f"Here is your **{cat.capitalize()} Electricity Bill Breakdown** for **{units:.0f} units**:\n\n"
                f"- **Total Estimated Bill:** **${calc['total_bill']:,.2f}**\n"
                f"- **Energy Charges:** ${calc['energy_charge']:,.2f}\n"
                f"- **Fixed Meter Fee:** ${calc['fixed_charge']:,.2f}\n"
                f"- **Current Tariff Bracket:** *{calc['current_tier']}*\n\n"
            )
            if solar > 0:
                text += f"☀️ **Solar Offset:** Your {solar:.0f} kWh solar generation reduced net units to {calc['net_units']:.0f} kWh.\n\n"

            text += "I've mounted the Tiered Electricity Calculator on the right for you to explore."
            return text, {
                "action": "create",
                "surface": "eb",
                "params": {"units": units, "category": cat, "solar": solar}
            }

        # C. Budget Planning Calculation
        if any(w in p for w in ["budget", "planner", "income", "take home", "expense", "savings"]):
            income = 5000
            m_inc = re.search(r"(?:income|salary|earn|earning)\s*(?:of\s*)?\$?(\d+(?:,\d+)*(?:\.\d+)?)", p)
            if not m_inc:
                m_inc = re.search(r"\$?(\d{1,3}(?:,\d{3})+|\d{4,9})", p)
            if m_inc:
                income = float(m_inc.group(1).replace(",", ""))

            calc = calculate_budget(income, 50, 30, 20)

            text = (
                f"Here is your **50/30/20 Budget Allocation** for a monthly income of **${income:,.0f}**:\n\n"
                f"- **Needs (50%):** **${calc['needs_target']:,.0f}** (Housing, Groceries, Utilities, Minimum Debt)\n"
                f"- **Wants (30%):** **${calc['wants_target']:,.0f}** (Dining, Shopping, Fun, Vacations)\n"
                f"- **Savings & Debt (20%):** **${calc['savings_target']:,.0f}** (Investments, Emergency Fund)\n\n"
                f"**Financial Health Rating:** *{calc['health_status']}*\n\n"
                "I've loaded the interactive Budget Planner on the right so you can tweak the allocation percentages."
            )
            return text, {
                "action": "create",
                "surface": "budget",
                "params": {"income": income, "needs_pct": 50, "wants_pct": 30, "savings_pct": 20}
            }

        # D. Generic conversational fallback
        text = (
            f"You asked: *\"{prompt}\"*\n\n"
            "I can calculate exact numbers for you or answer questions regarding:\n"
            "1. **Home Loans & Mortgages:** Monthly EMI, total interest, prepayment impact.\n"
            "2. **Tiered Electricity Bills:** Progressive slabs, commercial vs domestic rates, solar offsets.\n"
            "3. **Personal Budgeting:** 50/30/20 income allocation and wealth accumulation.\n\n"
            "Try asking something like: *\"Calculate loan for $450k at 6.8% for 25 years\"* or *\"What is reducing balance interest?\"*"
        )
        return text, {"action": "none", "surface": "none"}

    def _build_loan_surface(
        self,
        amount: float = 400000,
        rate: float = 6.5,
        tenure: float = 30,
        prepay: float = 0,
        currency: str = "$"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        calc = calculate_loan_emi(amount, rate, tenure, prepay)
        max_amount = max(1500000.0, float(amount) * 1.5)
        min_amount = min(50000.0, float(amount) * 0.2)
        step_amount = 10000.0 if amount < 5000000 else 50000.0

        data_model = {
            "loan": {
                "amount": float(amount),
                "rate": float(rate),
                "tenure": float(tenure),
                "prepayment": float(prepay),
                "currency": currency,
                "emi": calc["base_emi"],
                "total_interest": calc["total_interest_paid"],
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
                        "label": f"Loan Amount ({currency})",
                        "min": min_amount,
                        "max": max_amount,
                        "step": step_amount,
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
                        "max": 25.0,
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
                        "min": 1,
                        "max": 35,
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
                        "label": f"Monthly Prepayment ({currency})",
                        "min": 0,
                        "max": max(2000.0, float(amount) * 0.05),
                        "step": 50 if amount < 500000 else 500,
                        "valuePath": "/loan/prepayment",
                        "format": "currency"
                    }
                }
            }
        ]

        return components, data_model

    def _build_eb_surface(
        self,
        units: float = 350,
        category: str = "domestic",
        solar: float = 0
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        calc = calculate_eb_bill(units, category, solar)
        max_units = max(1000.0, float(units) * 1.5)

        data_model = {
            "eb": {
                "units": float(units),
                "category": category,
                "solar": float(solar),
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
                        "max": max_units,
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
                        "max": max(500.0, float(solar) * 2),
                        "step": 10,
                        "valuePath": "/eb/solar",
                        "unit": " kWh"
                    }
                }
            }
        ]

        return components, data_model

    def _build_budget_surface(
        self,
        income: float = 5000,
        needs_pct: float = 50,
        wants_pct: float = 30,
        savings_pct: float = 20
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        calc = calculate_budget(income, needs_pct, wants_pct, savings_pct)
        max_income = max(30000.0, float(income) * 1.5)

        data_model = {
            "budget": {
                "income": float(income),
                "needs_pct": float(needs_pct),
                "wants_pct": float(wants_pct),
                "savings_pct": float(savings_pct),
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
                        "max": max_income,
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
