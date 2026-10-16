/**
 * AG-UI Protocol Client
 * Consumes Server-Sent Events (SSE) stream adhering to the AG-UI specification.
 */
class AGUIClient {
    constructor(baseUrl = "") {
        this.baseUrl = baseUrl;
        this.eventSource = null;
        this.listeners = {
            runStarted: [],
            textMessageStart: [],
            textMessageContent: [],
            textMessageEnd: [],
            toolCallStart: [],
            toolCallEnd: [],
            customEvent: [],
            runFinished: [],
            runError: []
        };
    }

    on(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event].push(callback);
        }
    }

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(cb => cb(data));
        }
    }

    /**
     * Initiates an agent stream run using Server-Sent Events.
     */
    startStream(prompt) {
        if (this.eventSource) {
            this.eventSource.close();
        }

        const url = `${this.baseUrl}/api/agent/stream?prompt=${encodeURIComponent(prompt)}`;
        this.eventSource = new EventSource(url);

        this.eventSource.addEventListener("RunStartedEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("runStarted", data);
        });

        this.eventSource.addEventListener("TextMessageStartEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("textMessageStart", data);
        });

        this.eventSource.addEventListener("TextMessageContentEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("textMessageContent", data);
        });

        this.eventSource.addEventListener("TextMessageEndEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("textMessageEnd", data);
        });

        this.eventSource.addEventListener("ToolCallStartEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("toolCallStart", data);
        });

        this.eventSource.addEventListener("ToolCallEndEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("toolCallEnd", data);
        });

        this.eventSource.addEventListener("CustomEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("customEvent", data);
        });

        this.eventSource.addEventListener("RunFinishedEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("runFinished", data);
            this.eventSource.close();
        });

        this.eventSource.addEventListener("RunErrorEvent", (e) => {
            const data = JSON.parse(e.data);
            this.emit("runError", data);
            this.eventSource.close();
        });

        this.eventSource.onerror = (err) => {
            this.emit("runError", { error_message: "Connection lost or stream interrupted." });
            if (this.eventSource) this.eventSource.close();
        };
    }

    /**
     * Dispatches state changes back to the agent backend (bidirectional AG-UI sync).
     */
    async sendStateDelta(surfaceId, dataModel) {
        try {
            const res = await fetch(`${this.baseUrl}/api/agent/state-delta`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ surfaceId, dataModel })
            });
            return await res.json();
        } catch (e) {
            console.error("Failed to send state delta:", e);
            return null;
        }
    }
}
