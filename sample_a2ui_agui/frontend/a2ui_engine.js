/**
 * A2UI (Agent-to-User Interface) Engine
 * Implements declarative flat adjacency list parsing, RFC 6901 JSON pointer data binding,
 * and trusted native component registry.
 */
class A2UIEngine {
    constructor() {
        this.surfaces = {}; // surfaceId -> { title, rootId, componentsMap, dataModel, boundElements, onStateChange }
    }

    createSurface(surfaceId, title, rootComponentId) {
        this.surfaces[surfaceId] = {
            surfaceId,
            title,
            rootComponentId,
            componentsMap: new Map(),
            dataModel: {},
            boundElements: new Map(), // pointerPath -> [{ el, format, prop }]
            container: null,
            onStateChange: null
        };
    }

    updateComponents(surfaceId, componentsList) {
        const surface = this.surfaces[surfaceId];
        if (!surface) return;

        componentsList.forEach(item => {
            surface.componentsMap.set(item.id, item.component);
        });
    }

    updateDataModel(surfaceId, newDataModel) {
        const surface = this.surfaces[surfaceId];
        if (!surface) return;

        surface.dataModel = JSON.parse(JSON.stringify(newDataModel));
        if (surface.dataModel.currency) {
            surface.currencySymbol = surface.dataModel.currency;
        } else if (surface.dataModel.loan && surface.dataModel.loan.currency) {
            surface.currencySymbol = surface.dataModel.loan.currency;
        }
        this.refreshBoundMetrics(surfaceId);
    }

    /**
     * Resolves RFC 6901 JSON pointer (e.g. "/loan/amount") from data model.
     */
    getValueByPointer(dataModel, path) {
        if (!path || !path.startsWith("/")) return null;
        const tokens = path.slice(1).split("/");
        let curr = dataModel;
        for (const token of tokens) {
            if (curr == null || typeof curr !== "object") return null;
            curr = curr[token];
        }
        return curr;
    }

    setValueByPointer(dataModel, path, value) {
        if (!path || !path.startsWith("/")) return;
        const tokens = path.slice(1).split("/");
        let curr = dataModel;
        for (let i = 0; i < tokens.length - 1; i++) {
            const token = tokens[i];
            if (!(token in curr) || typeof curr[token] !== "object") {
                curr[token] = {};
            }
            curr = curr[token];
        }
        curr[tokens[tokens.length - 1]] = value;
    }

    formatValue(val, format, unit = "", currency = null) {
        if (val === null || val === undefined) return "--";
        const num = parseFloat(val);
        if (isNaN(num)) return String(val) + (unit ? " " + unit : "");

        if (format === "currency") {
            const sym = currency || "$";
            return sym + num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        } else if (format === "percent") {
            return num.toFixed(2) + "%";
        } else if (format === "integer") {
            return Math.round(num).toLocaleString() + (unit ? " " + unit : "");
        } else if (format === "decimal") {
            return num.toFixed(2) + (unit ? " " + unit : "");
        }
        return num.toLocaleString() + (unit ? " " + unit : "");
    }

    /**
     * Re-evaluates local formulas for immediate 60fps responsiveness before backend responds.
     */
    evaluateLocalFormulas(surfaceId) {
        const surface = this.surfaces[surfaceId];
        if (!surface) return;
        const m = surface.dataModel;

        if (surfaceId === "home-loan-calculator" && m.loan) {
            const P = parseFloat(m.loan.amount) || 0;
            const r = (parseFloat(m.loan.rate) || 0) / 100 / 12;
            const n = (parseFloat(m.loan.tenure) || 0) * 12;
            const prepay = parseFloat(m.loan.prepayment) || 0;

            if (P > 0 && n > 0) {
                let emi = 0;
                if (r === 0) {
                    emi = P / n;
                } else {
                    const factor = Math.pow(1 + r, n);
                    emi = (P * r * factor) / (factor - 1);
                }
                m.loan.emi = Math.round(emi);
                const totalPayment = emi * n;
                m.loan.total_payment = Math.round(totalPayment);
                m.loan.total_interest = Math.max(0, Math.round(totalPayment - P));
            }
        } else if (surfaceId === "eb-bill-calculator" && m.eb) {
            const units = Math.max(0, parseFloat(m.eb.units) || 0);
            const solar = Math.max(0, parseFloat(m.eb.solar) || 0);
            const net = Math.max(0, units - solar);
            const isCommercial = m.eb.category === "commercial";

            let fixed = isCommercial ? 15 : 5;
            let energy = 0;

            if (isCommercial) {
                if (net <= 150) energy = net * 5.0;
                else if (net <= 400) energy = 150 * 5.0 + (net - 150) * 7.5;
                else energy = 150 * 5.0 + 250 * 7.5 + (net - 400) * 9.8;
            } else {
                if (net <= 100) energy = 0;
                else if (net <= 200) energy = (net - 100) * 2.25;
                else if (net <= 500) energy = 100 * 2.25 + (net - 200) * 4.5;
                else energy = 100 * 2.25 + 300 * 4.5 + (net - 500) * 6.75;
            }

            m.eb.fixed_charge = fixed;
            m.eb.energy_charge = Math.round(energy);
            m.eb.total_bill = Math.round(fixed + energy);
        } else if (surfaceId === "budget-planner" && m.budget) {
            const income = parseFloat(m.budget.income) || 0;
            const nPct = parseFloat(m.budget.needs_pct) || 50;
            const wPct = parseFloat(m.budget.wants_pct) || 30;
            const sPct = parseFloat(m.budget.savings_pct) || 20;

            m.budget.needs_val = Math.round(income * (nPct / 100));
            m.budget.wants_val = Math.round(income * (wPct / 100));
            m.budget.savings_val = Math.round(income * (sPct / 100));
        }

        this.refreshBoundMetrics(surfaceId);
    }

    refreshBoundMetrics(surfaceId) {
        const surface = this.surfaces[surfaceId];
        if (!surface) return;

        surface.boundElements.forEach((bindings, path) => {
            const val = this.getValueByPointer(surface.dataModel, path);
            bindings.forEach(binding => {
                if (binding.prop === "textContent") {
                    binding.el.textContent = this.formatValue(val, binding.format, binding.unit, surface.currencySymbol);
                } else if (binding.prop === "value") {
                    if (binding.el.value != val) binding.el.value = val;
                }
            });
        });
    }

    /**
     * Recursively renders the component tree starting from rootId.
     */
    renderSurface(surfaceId, containerEl, onStateChange) {
        const surface = this.surfaces[surfaceId];
        if (!surface) return;

        surface.container = containerEl;
        surface.onStateChange = onStateChange;
        surface.boundElements.clear();
        containerEl.innerHTML = "";

        const rootDom = this._renderComponentNode(surfaceId, surface.rootComponentId);
        if (rootDom) {
            containerEl.appendChild(rootDom);
        }
        this.refreshBoundMetrics(surfaceId);
    }

    _renderComponentNode(surfaceId, componentId) {
        const surface = this.surfaces[surfaceId];
        const compObj = surface.componentsMap.get(componentId);
        if (!compObj) return null;

        const compType = Object.keys(compObj)[0];
        const props = compObj[compType];

        switch (compType) {
            case "Card":
                return this._renderCard(surfaceId, props);
            case "Row":
                return this._renderRow(surfaceId, props);
            case "Column":
                return this._renderColumn(surfaceId, props);
            case "Metric":
                return this._renderMetric(surfaceId, props);
            case "Slider":
                return this._renderSlider(surfaceId, props);
            case "ChoicePicker":
                return this._renderChoicePicker(surfaceId, props);
            case "Divider":
                return this._renderDivider();
            case "Alert":
                return this._renderAlert(props);
            default:
                console.warn(`Unsupported A2UI component type: ${compType}`);
                return null;
        }
    }

    _renderCard(surfaceId, props) {
        const card = document.createElement("div");
        const variantClasses = {
            elevated: "bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-slate-200/80 dark:border-slate-700/80 p-6 backdrop-blur-sm",
            outlined: "bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-5",
            default: "bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5"
        };
        card.className = variantClasses[props.variant] || variantClasses.default;

        if (props.title) {
            const header = document.createElement("div");
            header.className = "mb-4 border-b border-slate-100 dark:border-slate-700/50 pb-3";
            const h3 = document.createElement("h3");
            h3.className = "text-xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2";
            h3.innerHTML = `<span class="w-2.5 h-2.5 rounded-full bg-indigo-500"></span> ${props.title}`;
            header.appendChild(h3);

            if (props.subtitle) {
                const sub = document.createElement("p");
                sub.className = "text-xs text-slate-500 dark:text-slate-400 mt-1";
                sub.textContent = props.subtitle;
                header.appendChild(sub);
            }
            card.appendChild(header);
        }

        const body = document.createElement("div");
        body.className = "flex flex-col gap-4";

        if (props.children && props.children.explicitList) {
            props.children.explicitList.forEach(childId => {
                const childDom = this._renderComponentNode(surfaceId, childId);
                if (childDom) body.appendChild(childDom);
            });
        }

        card.appendChild(body);
        return card;
    }

    _renderRow(surfaceId, props) {
        const row = document.createElement("div");
        const justifyClass = props.justify === "between" ? "justify-between" : "justify-start";
        row.className = `flex flex-wrap items-center ${justifyClass} gap-3`;

        if (props.children && props.children.explicitList) {
            props.children.explicitList.forEach(childId => {
                const childDom = this._renderComponentNode(surfaceId, childId);
                if (childDom) row.appendChild(childDom);
            });
        }
        return row;
    }

    _renderColumn(surfaceId, props) {
        const col = document.createElement("div");
        col.className = "flex flex-col gap-4 w-full";

        if (props.children && props.children.explicitList) {
            props.children.explicitList.forEach(childId => {
                const childDom = this._renderComponentNode(surfaceId, childId);
                if (childDom) col.appendChild(childDom);
            });
        }
        return col;
    }

    _renderMetric(surfaceId, props) {
        const wrapper = document.createElement("div");
        const colorStyles = {
            indigo: "bg-indigo-50/80 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800/60 text-indigo-700 dark:text-indigo-300",
            rose: "bg-rose-50/80 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-300",
            emerald: "bg-emerald-50/80 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/60 text-emerald-700 dark:text-emerald-300",
            amber: "bg-amber-50/80 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60 text-amber-700 dark:text-amber-300",
            blue: "bg-blue-50/80 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800/60 text-blue-700 dark:text-blue-300"
        };
        const colorClass = colorStyles[props.color] || colorStyles.indigo;

        wrapper.className = `flex-1 min-w-[150px] p-4 rounded-xl border ${colorClass} transition-all shadow-sm`;

        const label = document.createElement("div");
        label.className = "text-xs font-semibold uppercase tracking-wider opacity-80";
        label.textContent = props.label;
        wrapper.appendChild(label);

        const valEl = document.createElement("div");
        valEl.className = "text-2xl font-extrabold tracking-tight mt-1";
        wrapper.appendChild(valEl);

        if (props.subtext) {
            const sub = document.createElement("div");
            sub.className = "text-[11px] opacity-75 mt-1";
            sub.textContent = props.subtext;
            wrapper.appendChild(sub);
        }

        // Register binding
        this._bindElement(surfaceId, props.valuePath, valEl, "textContent", props.format, props.unit);
        return wrapper;
    }

    _renderSlider(surfaceId, props) {
        const surface = this.surfaces[surfaceId];
        const container = document.createElement("div");
        container.className = "flex flex-col gap-1.5 p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 transition";

        const header = document.createElement("div");
        header.className = "flex justify-between items-center";

        const label = document.createElement("label");
        label.className = "text-sm font-semibold text-slate-700 dark:text-slate-300";
        label.textContent = props.label;
        header.appendChild(label);

        const valBadge = document.createElement("span");
        valBadge.className = "text-sm font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2.5 py-0.5 rounded-full border border-indigo-200 dark:border-indigo-800";
        header.appendChild(valBadge);
        container.appendChild(header);

        const slider = document.createElement("input");
        slider.type = "range";
        slider.min = props.min;
        slider.max = props.max;
        slider.step = props.step || 1;
        slider.className = "w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-600";

        const initVal = this.getValueByPointer(surface.dataModel, props.valuePath) || props.min;
        slider.value = initVal;
        valBadge.textContent = this.formatValue(initVal, props.format, props.unit, surface.currencySymbol);

        slider.addEventListener("input", (e) => {
            const num = parseFloat(e.target.value);
            valBadge.textContent = this.formatValue(num, props.format, props.unit, surface.currencySymbol);
            this.setValueByPointer(surface.dataModel, props.valuePath, num);
            
            // 1. Instant 60fps local formula calculation
            this.evaluateLocalFormulas(surfaceId);

            // 2. Trigger debounced sync to backend
            if (surface.onStateChange) {
                surface.onStateChange(surfaceId, surface.dataModel);
            }
        });

        container.appendChild(slider);

        // Register bindings
        this._bindElement(surfaceId, props.valuePath, valBadge, "textContent", props.format, props.unit);
        this._bindElement(surfaceId, props.valuePath, slider, "value");

        return container;
    }

    _renderChoicePicker(surfaceId, props) {
        const surface = this.surfaces[surfaceId];
        const container = document.createElement("div");
        container.className = "flex flex-col gap-2 p-3";

        const label = document.createElement("label");
        label.className = "text-sm font-semibold text-slate-700 dark:text-slate-300";
        label.textContent = props.label;
        container.appendChild(label);

        const group = document.createElement("div");
        group.className = "flex gap-2 p-1 bg-slate-100 dark:bg-slate-700/60 rounded-xl";

        const currentVal = this.getValueByPointer(surface.dataModel, props.valuePath);

        props.options.forEach(opt => {
            const btn = document.createElement("button");
            const isSelected = opt.value === currentVal;
            btn.className = `flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition ${
                isSelected
                    ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm border border-slate-200/60 dark:border-slate-700"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
            }`;
            btn.textContent = opt.label;

            btn.addEventListener("click", () => {
                this.setValueByPointer(surface.dataModel, props.valuePath, opt.value);
                this.evaluateLocalFormulas(surfaceId);
                // Re-render choice buttons
                group.querySelectorAll("button").forEach(b => {
                    b.className = "flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition text-slate-600 dark:text-slate-400 hover:text-slate-900";
                });
                btn.className = "flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm border border-slate-200/60 dark:border-slate-700";

                if (surface.onStateChange) {
                    surface.onStateChange(surfaceId, surface.dataModel);
                }
            });

            group.appendChild(btn);
        });

        container.appendChild(group);
        return container;
    }

    _renderDivider() {
        const hr = document.createElement("hr");
        hr.className = "border-t border-slate-200 dark:border-slate-700/60 my-1";
        return hr;
    }

    _renderAlert(props) {
        const alert = document.createElement("div");
        const severityStyles = {
            info: "bg-blue-50 dark:bg-blue-950/40 border-blue-200 text-blue-800 dark:text-blue-200",
            warning: "bg-amber-50 dark:bg-amber-950/40 border-amber-200 text-amber-800 dark:text-amber-200",
            success: "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 text-emerald-800 dark:text-emerald-200",
            error: "bg-rose-50 dark:bg-rose-950/40 border-rose-200 text-rose-800 dark:text-rose-200"
        };
        const sClass = severityStyles[props.severity] || severityStyles.info;

        alert.className = `p-4 rounded-xl border ${sClass} text-sm flex flex-col gap-1 shadow-sm transition-all animate-fade-in`;

        const title = document.createElement("div");
        title.className = "font-bold flex items-center gap-1.5";
        title.innerHTML = `<span>💡</span> ${props.title}`;
        alert.appendChild(title);

        const msg = document.createElement("div");
        msg.className = "text-xs opacity-90 leading-relaxed";
        msg.textContent = props.message;
        alert.appendChild(msg);

        return alert;
    }

    _bindElement(surfaceId, pointerPath, el, prop, format, unit) {
        const surface = this.surfaces[surfaceId];
        if (!surface.boundElements.has(pointerPath)) {
            surface.boundElements.set(pointerPath, []);
        }
        surface.boundElements.get(pointerPath).push({ el, prop, format, unit });
    }
}
