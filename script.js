/* ============================================================
 * TNEB (TANGEDCO) Bi-Monthly Electricity Bill Calculator
 * ------------------------------------------------------------
 * Slab algorithm (telescopic):
 *   Consumption is split across progressive slabs. Each slab
 *   covers [from, to) units; units falling inside a slab are
 *   charged at that slab's rate. For domestic connections the
 *   first 100 units are free (government subsidy) when total
 *   consumption is <= 500 units; above 500 units the free
 *   benefit is withdrawn and all units are billed.
 * ============================================================ */

"use strict";

/* ---------- i18n dictionary ---------- */
const I18N = {
  en: {
    title: "TNEB Bill Calculator",
    subtitle: "TANGEDCO Bi-Monthly Electricity Bill Estimator",
    inputDetails: "Connection Details",
    tariffCategory: "Tariff Category",
    domestic: "Domestic (LT-1A)",
    commercial: "Commercial (LT-2A)",
    common: "Common Supply (Apartments)",
    phase: "Connection Phase",
    singlePhase: "1-Phase",
    threePhase: "3-Phase",
    inputMode: "Input Mode",
    directUnits: "Direct Units",
    meterReadings: "Meter Readings",
    contractedLoad: "Contracted Load (kW)",
    unitsConsumed: "Units Consumed (kWh, bi-monthly)",
    prevReading: "Previous Meter Reading",
    currReading: "Current Meter Reading",
    calculate: "Calculate Bill",
    slabInsights: "Slab Insights",
    whatIf: "What-If: adjust units",
    billReceipt: "Bill Receipt",
    totalUnits: "Total Units Consumed",
    freeUnits: "Government Subsidy (Free Units)",
    slabRange: "Slab Range",
    unitsInSlab: "Units",
    rate: "Rate (₹/unit)",
    subtotal: "Subtotal (₹)",
    energyCharges: "Energy Charges",
    subsidy: "Subsidy Discount (100 free units)",
    fixedCharges: "Fixed Charges",
    meterCharges: "Meter / Other Charges",
    totalPayable: "Total Payable Amount",
    copyBreakdown: "Copy Breakdown",
    downloadPdf: "Download / Print PDF",
    history: "Recent Calculations",
    disclaimer: "Indicative estimate based on TNERC tariff order. Verify with your official TANGEDCO bill.",
    errNumeric: "Please enter valid non-negative numbers.",
    errReading: "Current reading cannot be less than previous reading.",
    errUnits: "Please enter consumed units.",
    copied: "Breakdown copied to clipboard!",
    noHistory: "No calculations yet.",
    slabCaption: (u, slab) => `You are in the ${slab} slab at ${u} units.`,
    alertMsg: (gap, threshold, saving) =>
      `⚠️ You are ${gap} units away from crossing the ${threshold}-unit threshold. Staying under ${threshold} units will save you ~₹${saving} on higher slab penalties.`,
    whatIfResult: (u, cost) => `At ${u} units → estimated bill ₹${cost}`,
    freeBadge: (n) => `${n} units FREE`,
    unitsWord: "units"
  },
  ta: {
    title: "TNEB மின் கட்டண கணிப்பான்",
    subtitle: "TANGEDCO இருமாத மின்னளவி மதிப்பீடு",
    inputDetails: "இணைப்பு விவரங்கள்",
    tariffCategory: "கட்டண வகை",
    domestic: "வீட்டு உபயோகம் (LT-1A)",
    commercial: "வணிகம் (LT-2A)",
    common: "பொது விநியோகம் (அடுக்குமாடி)",
    phase: "இணைப்பு கட்டம்",
    singlePhase: "ஒற்றை கட்டம்",
    threePhase: "முக்கட்டம்",
    inputMode: "உள்ளீட்டு முறை",
    directUnits: "நேரடி யூனிட்டுகள்",
    meterReadings: "மீட்டர் அளவீடுகள்",
    contractedLoad: "ஒப்பந்த சுமை (kW)",
    unitsConsumed: "நுகர்ந்த யூனிட்டுகள் (kWh, இருமாதம்)",
    prevReading: "முந்தைய மீட்டர் அளவீடு",
    currReading: "தற்போதைய மீட்டர் அளவீடு",
    calculate: "கட்டணம் கணக்கிடு",
    slabInsights: "ஸ்லாப் நுண்ணறிவு",
    whatIf: "What-If: யூனிட்டுகளை மாற்றவும்",
    billReceipt: "மின் கட்டண ரசீது",
    totalUnits: "மொத்த யூனிட்டுகள்",
    freeUnits: "அரசு மானியம் (இலவச யூனிட்டுகள்)",
    slabRange: "ஸ்லாப் வரம்பு",
    unitsInSlab: "யூனிட்டுகள்",
    rate: "விலை (₹/யூனிட்)",
    subtotal: "துணை மொத்தம் (₹)",
    energyCharges: "மின் கட்டணம்",
    subsidy: "மானிய தள்ளுபடி (100 இலவச யூனிட்டுகள்)",
    fixedCharges: "நிலையான கட்டணம்",
    meterCharges: "மீட்டர் / பிற கட்டணம்",
    totalPayable: "செலுத்த வேண்டிய தொகை",
    copyBreakdown: "விவரத்தை நகலெடு",
    downloadPdf: "PDF பதிவிறக்கம் / அச்சு",
    history: "சமீபத்திய கணக்கீடுகள்",
    disclaimer: "TNERC கட்டண உத்தரவின் அடிப்படையில் தோராயமான மதிப்பீடு. அதிகாரப்பூர்வ TANGEDCO பில்லுடன் சரிபார்க்கவும்.",
    errNumeric: "சரியான எதிர்மறை அல்லாத எண்களை உள்ளிடவும்.",
    errReading: "தற்போதைய அளவீடு முந்தைய அளவீட்டை விட குறைவாக இருக்க முடியாது.",
    errUnits: "நுகர்ந்த யூனிட்டுகளை உள்ளிடவும்.",
    copied: "விவரம் நகலெடுக்கப்பட்டது!",
    noHistory: "இன்னும் கணக்கீடுகள் இல்லை.",
    slabCaption: (u, slab) => `${u} யூனிட்டுகளில் நீங்கள் ${slab} ஸ்லாப்பில் உள்ளீர்கள்.`,
    alertMsg: (gap, threshold, saving) =>
      `⚠️ ${threshold}-யூனிட் வரம்பை கடக்க இன்னும் ${gap} யூனிட்டுகள் உள்ளன. ${threshold} யூனிட்டுகளுக்குள் இருந்தால் ~₹${saving} சேமிக்கலாம்.`,
    whatIfResult: (u, cost) => `${u} யூனிட்டுகளில் → மதிப்பிடப்பட்ட பில் ₹${cost}`,
    freeBadge: (n) => `${n} யூனிட்டுகள் இலவசம்`,
    unitsWord: "யூனிட்டுகள்"
  }
};

let lang = "en";
const t = (key) => I18N[lang][key];

/* ---------- State ---------- */
let TARIFF = null;
let phase = "singlePhase";
let inputMode = "units";
let lastResult = null;

/* ---------- DOM helpers ---------- */
const $ = (id) => document.getElementById(id);
const fmt = (n) => "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });

/* ---------- Core calculation ---------- */
/**
 * Telescopic slab calculation.
 * Walks each slab, computes how many of the consumed units fall
 * inside [from, to), multiplies by the slab rate, and accumulates.
 * Returns an itemized breakdown plus totals.
 */
function calculateBill(category, units, phaseKey, loadKW) {
  const cfg = TARIFF[category];
  const breakdown = [];
  let energyCharges = 0;

  if (cfg.flatRate != null) {
    // Common supply: single flat rate for all units
    breakdown.push({ range: `0 – ∞`, units, rate: cfg.flatRate, subtotal: units * cfg.flatRate });
    energyCharges = units * cfg.flatRate;
  } else {
    for (const slab of cfg.slabs) {
      if (units <= slab.from) break;
      const upper = slab.to === null ? units : Math.min(units, slab.to);
      const slabUnits = upper - slab.from;
      if (slabUnits <= 0) continue;
      const subtotal = slabUnits * slab.rate;
      breakdown.push({
        range: `${slab.from} – ${slab.to === null ? "∞" : slab.to}`,
        units: slabUnits,
        rate: slab.rate,
        subtotal
      });
      energyCharges += subtotal;
    }
  }

  // Government subsidy: first 100 domestic units free when total <= 500
  let freeUnits = 0;
  let subsidyDiscount = 0;
  if (category === "domestic" && units > 0 && units <= cfg.freeUnitsMaxConsumption) {
    freeUnits = Math.min(cfg.freeUnits, units);
    // Value of free units = what they'd cost at the first paid slab rate
    const firstPaidRate = cfg.slabs.find((s) => s.rate > 0)?.rate || 0;
    subsidyDiscount = freeUnits * firstPaidRate;
  }

  // Fixed & meter charges
  let fixedCharges = 0;
  if (cfg.fixedChargesPerKW != null) {
    fixedCharges = (loadKW || 0) * cfg.fixedChargesPerKW;
  } else if (cfg.fixedCharges) {
    fixedCharges = cfg.fixedCharges[phaseKey] || 0;
  }
  const meterCharges = cfg.meterCharges || 0;

  const total = Math.max(0, energyCharges - subsidyDiscount + fixedCharges + meterCharges);
  return { category, units, phaseKey, loadKW, breakdown, energyCharges, freeUnits, subsidyDiscount, fixedCharges, meterCharges, total };
}

/* ---------- Validation ---------- */
function readUnits() {
  const err = $("error-msg");
  err.textContent = "";
  if (inputMode === "units") {
    const raw = $("units").value.trim();
    if (raw === "") { err.textContent = t("errUnits"); return null; }
    const u = Number(raw);
    if (isNaN(u) || u < 0) { err.textContent = t("errNumeric"); return null; }
    return u;
  }
  const prev = Number($("prevReading").value);
  const curr = Number($("currReading").value);
  if ($("prevReading").value.trim() === "" || $("currReading").value.trim() === "" ||
      isNaN(prev) || isNaN(curr) || prev < 0 || curr < 0) {
    err.textContent = t("errNumeric"); return null;
  }
  if (curr < prev) { err.textContent = t("errReading"); return null; }
  return curr - prev;
}

/* ---------- Rendering ---------- */
function renderReceipt(r) {
  $("receipt-card").classList.remove("hidden");
  $("receipt-category").textContent = TARIFF[r.category].label;
  $("r-units").textContent = `${r.units} kWh`;

  const freeRow = $("r-free-row");
  if (r.freeUnits > 0) {
    freeRow.style.display = "flex";
    $("r-free").textContent = t("freeBadge")(r.freeUnits);
  } else freeRow.style.display = "none";

  const tbody = $("slab-tbody");
  tbody.innerHTML = "";
  for (const row of r.breakdown) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${row.range}</td><td>${row.units}</td><td>${row.rate.toFixed(2)}</td><td>${row.subtotal.toFixed(2)}</td>`;
    tbody.appendChild(tr);
  }

  $("r-energy").textContent = fmt(r.energyCharges);
  const subRow = $("r-subsidy-row");
  if (r.subsidyDiscount > 0) {
    subRow.style.display = "flex";
    $("r-subsidy").textContent = "− " + fmt(r.subsidyDiscount);
  } else subRow.style.display = "none";
  $("r-fixed").textContent = fmt(r.fixedCharges);
  $("r-meter").textContent = fmt(r.meterCharges);
  $("r-total").textContent = fmt(r.total);
}

function currentSlabLabel(category, units) {
  const cfg = TARIFF[category];
  if (cfg.flatRate != null) return "flat";
  for (const s of cfg.slabs) {
    if (units <= (s.to === null ? Infinity : s.to)) return `${s.from}–${s.to === null ? "∞" : s.to}`;
  }
  return "∞";
}

function renderInsights(r) {
  $("insight-card").classList.remove("hidden");
  const max = 1200;
  const pct = Math.min(100, (r.units / max) * 100);
  $("progress-marker").style.left = `calc(${pct}% - 2px)`;
  $("slab-caption").textContent = t("slabCaption")(r.units, currentSlabLabel(r.category, r.units));

  // Slab alert: warn when close to the 500-unit domestic threshold
  const banner = $("alert-banner");
  const thresholds = [100, 200, 400, 500, 600];
  const next = thresholds.find((th) => r.units < th && th - r.units <= 50);
  if (r.category === "domestic" && next != null) {
    const gap = next - r.units;
    const costNow = calculateBill(r.category, r.units, r.phaseKey, r.loadKW).total;
    const costOver = calculateBill(r.category, next + 1, r.phaseKey, r.loadKW).total;
    const saving = Math.max(0, Math.round(costOver - costNow));
    banner.textContent = t("alertMsg")(gap, next, saving);
    banner.classList.remove("hidden");
  } else banner.classList.add("hidden");

  // What-If slider
  const slider = $("whatif-slider");
  slider.value = r.units;
  const update = () => {
    const u = Number(slider.value);
    $("whatif-value").textContent = `${u} ${t("unitsWord")}`;
    const sim = calculateBill(r.category, u, r.phaseKey, r.loadKW);
    $("whatif-result").textContent = t("whatIfResult")(u, sim.total.toFixed(2));
  };
  slider.oninput = update;
  update();
}

/* ---------- History (localStorage, last 5) ---------- */
const HIST_KEY = "tneb_history";
function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HIST_KEY)) || []; } catch { return []; }
}
function saveHistory(entry) {
  const h = loadHistory();
  h.unshift(entry);
  localStorage.setItem(HIST_KEY, JSON.stringify(h.slice(0, 5)));
  renderHistory();
}
function renderHistory() {
  const list = $("history-list");
  const h = loadHistory();
  list.innerHTML = "";
  if (!h.length) {
    list.innerHTML = `<li class="history-empty">${t("noHistory")}</li>`;
    return;
  }
  for (const e of h) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${e.date} · ${e.category} · ${e.units} kWh</span><span class="h-amt">${fmt(e.total)}</span>`;
    list.appendChild(li);
  }
}

/* ---------- Copy / Print ---------- */
function copyBreakdown() {
  if (!lastResult) return;
  const r = lastResult;
  const lines = [
    `TNEB Bill Estimate — ${TARIFF[r.category].label}`,
    `Units: ${r.units} kWh`,
    ...r.breakdown.map((b) => `  ${b.range}: ${b.units} units × ₹${b.rate} = ₹${b.subtotal.toFixed(2)}`),
    `Energy Charges: ${fmt(r.energyCharges)}`,
    r.subsidyDiscount > 0 ? `Subsidy: −${fmt(r.subsidyDiscount)}` : null,
    `Fixed Charges: ${fmt(r.fixedCharges)}`,
    `Meter Charges: ${fmt(r.meterCharges)}`,
    `TOTAL PAYABLE: ${fmt(r.total)}`
  ].filter(Boolean).join("\n");
  navigator.clipboard.writeText(lines).then(() => alert(t("copied")));
}

/* ---------- i18n apply ---------- */
function applyLang() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (typeof I18N[lang][key] === "string") el.textContent = I18N[lang][key];
  });
  $("btn-en").classList.toggle("active", lang === "en");
  $("btn-ta").classList.toggle("active", lang === "ta");
  renderHistory();
  if (lastResult) { renderReceipt(lastResult); renderInsights(lastResult); }
}

/* ---------- Event wiring ---------- */
function setPhase(p) {
  phase = p;
  $("phase-1").classList.toggle("active", p === "singlePhase");
  $("phase-3").classList.toggle("active", p === "threePhase");
}
function setMode(m) {
  inputMode = m;
  $("mode-units").classList.toggle("active", m === "units");
  $("mode-meter").classList.toggle("active", m === "meter");
  $("units-input-group").style.display = m === "units" ? "grid" : "none";
  $("meter-input-group").style.display = m === "meter" ? "grid" : "none";
}

async function init() {
  TARIFF = await (await fetch("tariff.json")).json();

  $("phase-1").onclick = () => setPhase("singlePhase");
  $("phase-3").onclick = () => setPhase("threePhase");
  $("mode-units").onclick = () => setMode("units");
  $("mode-meter").onclick = () => setMode("meter");
  $("btn-en").onclick = () => { lang = "en"; applyLang(); };
  $("btn-ta").onclick = () => { lang = "ta"; applyLang(); };
  $("copy-btn").onclick = copyBreakdown;
  $("print-btn").onclick = () => window.print();

  $("category").onchange = (e) => {
    $("load-field").style.display = e.target.value === "commercial" ? "block" : "none";
  };

  $("calc-btn").onclick = () => {
    const units = readUnits();
    if (units === null) return;
    const category = $("category").value;
    const loadKW = category === "commercial" ? Number($("load").value) || 0 : 0;
    if (category === "commercial" && loadKW < 0) {
      $("error-msg").textContent = t("errNumeric"); return;
    }
    lastResult = calculateBill(category, units, phase, loadKW);
    renderReceipt(lastResult);
    renderInsights(lastResult);
    saveHistory({
      date: new Date().toLocaleDateString(lang === "ta" ? "ta-IN" : "en-IN"),
      category: TARIFF[category].label,
      units,
      total: lastResult.total.toFixed(2)
    });
    $("receipt-card").scrollIntoView({ behavior: "smooth", block: "start" });
  };

  renderHistory();
}

init();
