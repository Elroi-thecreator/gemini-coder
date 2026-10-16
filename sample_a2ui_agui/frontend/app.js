/**
 * OmniCalc Application Controller
 * Connects the AG-UI stream consumer and the A2UI rendering engine.
 */
document.addEventListener("DOMContentLoaded", () => {
    const agui = new AGUIClient();
    const a2ui = new A2UIEngine();

    // DOM Elements
    const promptInput = document.getElementById("promptInput");
    const sendBtn = document.getElementById("sendBtn");
    const chatStream = document.getElementById("chatStream");
    const canvasContainer = document.getElementById("canvasContainer");
    const statusIndicator = document.getElementById("statusIndicator");
    const statusText = document.getElementById("statusText");
    const advisorySlot = document.getElementById("advisorySlot");
    const quickChips = document.querySelectorAll(".quick-chip");

    let currentMessageBubble = null;
    let currentMessageText = "";
    let activeSurfaceId = null;
    let stateDebounceTimer = null;

    // Helper: Append a message bubble to chat
    function appendChatBubble(role, initialText = "") {
        const bubble = document.createElement("div");
        const isUser = role === "user";
        bubble.className = `flex gap-3 ${isUser ? "justify-end" : "justify-start"} animate-fade-in`;

        const inner = document.createElement("div");
        inner.className = `max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
                ? "bg-indigo-600 text-white rounded-br-none shadow-md"
                : "bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border border-slate-200/80 dark:border-slate-700/80 rounded-bl-none shadow-sm chat-markdown"
        }`;
        inner.innerHTML = initialText;

        bubble.appendChild(inner);
        chatStream.appendChild(bubble);
        chatStream.scrollTop = chatStream.scrollHeight;
        return inner;
    }

    function setStatus(text, state = "idle") {
        statusText.textContent = text;
        statusIndicator.className = `w-2.5 h-2.5 rounded-full ${
            state === "active" ? "bg-amber-400 animate-ping" : state === "online" ? "bg-emerald-500" : "bg-slate-400"
        }`;
    }

    // AG-UI Protocol Listeners
    agui.on("runStarted", (data) => {
        setStatus("Agent thinking & synthesizing UI...", "active");
    });

    agui.on("textMessageStart", () => {
        currentMessageText = "";
        currentMessageBubble = appendChatBubble("assistant", "");
    });

    agui.on("textMessageContent", (data) => {
        currentMessageText += data.delta;
        if (currentMessageBubble) {
            if (window.marked) {
                currentMessageBubble.innerHTML = marked.parse(currentMessageText);
            } else {
                currentMessageBubble.textContent = currentMessageText;
            }
            chatStream.scrollTop = chatStream.scrollHeight;
        }
    });

    agui.on("textMessageEnd", () => {
        if (currentMessageBubble && window.marked) {
            currentMessageBubble.innerHTML = marked.parse(currentMessageText);
        }
    });

    agui.on("toolCallStart", (data) => {
        const badge = document.createElement("div");
        badge.className = "flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 px-2.5 py-1 rounded-md border border-indigo-200 dark:border-indigo-800/50 my-1 self-start";
        badge.innerHTML = `<span>⚡</span> Tool: <strong>${data.tool_name}</strong>`;
        chatStream.appendChild(badge);
        chatStream.scrollTop = chatStream.scrollHeight;
    });

    agui.on("customEvent", (evt) => {
        const { custom_type, data } = evt;

        if (custom_type === "a2ui:createSurface") {
            activeSurfaceId = data.surfaceId;
            a2ui.createSurface(data.surfaceId, data.title, data.rootComponentId);
            canvasContainer.innerHTML = `
                <div class="flex items-center justify-center p-12 text-slate-400">
                    <span class="animate-pulse">Loading ${data.title}...</span>
                </div>
            `;
        } else if (custom_type === "a2ui:updateComponents") {
            a2ui.updateComponents(data.surfaceId, data.components);
        } else if (custom_type === "a2ui:updateDataModel") {
            a2ui.updateDataModel(data.surfaceId, data.dataModel);

            // Render surface once components and data model are loaded
            if (activeSurfaceId === data.surfaceId) {
                a2ui.renderSurface(data.surfaceId, canvasContainer, handleWidgetStateChange);
            }
        }
    });

    agui.on("runFinished", () => {
        setStatus("Ready", "online");
    });

    agui.on("runError", (err) => {
        setStatus("Error", "idle");
        appendChatBubble("assistant", `<span class="text-rose-500 font-medium">⚠️ Error: ${err.error_message}</span>`);
    });

    // Callback when user drags a slider or selects a choice in A2UI surface
    function handleWidgetStateChange(surfaceId, dataModel) {
        clearTimeout(stateDebounceTimer);

        // Debounce sending to backend (300ms)
        stateDebounceTimer = setTimeout(async () => {
            const resp = await agui.sendStateDelta(surfaceId, dataModel);
            if (resp && resp.status === "success") {
                // If backend provided an advisory insight, display it
                if (resp.advisory) {
                    showAdvisoryAlert(resp.advisory);
                } else {
                    advisorySlot.innerHTML = "";
                }

                // If backend computed additional fields, sync them
                if (resp.updatedDataModel) {
                    a2ui.updateDataModel(surfaceId, resp.updatedDataModel);
                }
            }
        }, 300);
    }

    function showAdvisoryAlert(advisory) {
        advisorySlot.innerHTML = "";
        const alertDom = a2ui._renderAlert(advisory);
        advisorySlot.appendChild(alertDom);
    }

    // Submit user prompt
    function submitPrompt(text) {
        const prompt = text || promptInput.value.trim();
        if (!prompt) return;

        appendChatBubble("user", prompt);
        promptInput.value = "";
        advisorySlot.innerHTML = "";

        // Initiate AG-UI SSE stream
        agui.startStream(prompt);
    }

    sendBtn.addEventListener("click", () => submitPrompt());
    promptInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submitPrompt();
        }
    });

    // Quick chip buttons
    quickChips.forEach(chip => {
        chip.addEventListener("click", () => {
            const prompt = chip.getAttribute("data-prompt");
            submitPrompt(prompt);
        });
    });

    // Check backend health
    fetch("/api/health")
        .then(r => r.json())
        .then(data => {
            setStatus("Ready", "online");
            // Auto-trigger default Home Loan calculator on startup
            submitPrompt("Calculate home loan EMI for 400k at 6.5% for 30 years");
        })
        .catch(() => {
            setStatus("Server offline", "idle");
        });
});
