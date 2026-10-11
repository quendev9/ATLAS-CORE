
const input = document.getElementById("commandInput");
const sendButton = document.getElementById("sendButton");
const messages = document.getElementById("messages");
const hud = document.querySelector(".hud");
const expandChatButton = document.getElementById("expandChatButton");

const voiceSessionStartButton = document.getElementById("voiceSessionStart");
const voiceSessionStopButton = document.getElementById("voiceSessionStop");
const voiceToggle = document.getElementById("voiceToggle");
const stopSpeakingButton = document.getElementById("stopSpeakingButton");
const conversationState = document.querySelector(".conversation-state");
const toggleLeftPanelButton = document.getElementById("toggleLeftPanel");
const toggleRightPanelButton = document.getElementById("toggleRightPanel");
const toggleSidePanelsButton = document.getElementById("toggleSidePanels");

// ==================================================
// HUD STATE
// ==================================================

let requestInProgress = false;
let voiceEnabled = true;
let voiceAvailable = false;
let voiceControlRequestInProgress = false;
let lastVoiceEventId = 0;
let lastVoiceResponseId = 0;

// ==================================================
// MESSAGE SYSTEM
// ==================================================

function addMessage(sender, text) {
    if (!messages) return;

    const message = document.createElement("div");
    message.className = "message";

    const senderElement = document.createElement("div");
    senderElement.className = "message-label";
    senderElement.textContent = sender;

    const textElement = document.createElement("div");
    textElement.className = "message-text";
    textElement.textContent = String(text ?? "");

    message.appendChild(senderElement);
    message.appendChild(textElement);

    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
}

function setConversationState(state) {
    if (conversationState) {
        conversationState.textContent = String(state).toUpperCase();
        conversationState.dataset.state = String(state).toLowerCase();
    }

    setText("conversationStatus", String(state).toUpperCase());
}

function setButtonBusy(button, busy, busyText, normalText) {
    if (!button) return;

    button.disabled = busy;
    button.setAttribute("aria-busy", String(busy));

    if (busyText && normalText) {
        button.textContent = busy ? busyText : normalText;
    }
}

// ==================================================
// API HELPER
// ==================================================

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        cache: "no-store",
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...(options.headers || {})
        }
    });

    let data;

    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        throw new Error(
            data.error || `Request failed (${response.status})`
        );
    }

    return data;
}

// ==================================================
// CHAT
// ==================================================

async function sendCommand(command) {
    requestInProgress = true;
    setConversationState("PROCESSING");

    try {
        const data = await apiRequest("/api/chat", {
            method: "POST",
            body: JSON.stringify({ message: command })
        });

        const answer = data.response ?? "ATLAS returned an empty response.";

        addMessage("ATLAS", answer);

        // Read chat replies aloud when voice output is enabled.
        if (voiceEnabled && answer.trim()) {
            speakResponse(answer);
        }

        return answer;
    } catch (error) {
        console.error("ATLAS API ERROR:", error);

        addMessage(
            "SYSTEM",
            "ATLAS Core connection error: " + error.message
        );

        setConversationState("ERROR");
        return null;
    } finally {
        requestInProgress = false;
        updateHUDStatus();
    }
}

function handleCommand() {
    if (!input || !sendButton || requestInProgress) return;

    const command = input.value.trim();
    if (!command) return;

    addMessage("YOU", command);
    input.value = "";

    sendButton.disabled = true;

    sendCommand(command).finally(() => {
        sendButton.disabled = false;
        input.focus();
    });
}

if (sendButton) {
    sendButton.addEventListener("click", handleCommand);
}

if (input) {
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            handleCommand();
        }
    });
}

// ==================================================
// CHAT EXPAND / COLLAPSE
// ==================================================

if (expandChatButton && hud) {
    expandChatButton.addEventListener("click", () => {
        const expanded = hud.classList.toggle("chat-expanded");

        expandChatButton.textContent = expanded ? "COLLAPSE" : "EXPAND";

        if (input) input.focus();
    });
}

// ==================================================
// CONTINUOUS VOICE SESSION
// ==================================================

async function startVoiceSession() {
    if (!voiceSessionStartButton || voiceControlRequestInProgress) return;

    voiceControlRequestInProgress = true;
    setButtonBusy(
        voiceSessionStartButton,
        true,
        "STARTING...",
        "START VOICE SESSION"
    );
    setConversationState("STARTING");

    try {
        const data = await apiRequest("/api/voice/session/start", {
            method: "POST",
            body: JSON.stringify({})
        });

        addMessage("SYSTEM", data.message || "Voice session started.");
    } catch (error) {
        console.error("ATLAS VOICE SESSION ERROR:", error);
        addMessage("SYSTEM", "Could not start voice session: " + error.message);
        setConversationState("ERROR");
    } finally {
        voiceControlRequestInProgress = false;
        setButtonBusy(
            voiceSessionStartButton,
            false,
            "STARTING...",
            "START VOICE SESSION"
        );
        updateHUDStatus();
    }
}

if (voiceSessionStartButton) {
    voiceSessionStartButton.addEventListener("click", startVoiceSession);
}

async function stopVoiceSession() {
    if (!voiceSessionStopButton || voiceControlRequestInProgress) return;

    voiceControlRequestInProgress = true;
    setButtonBusy(
        voiceSessionStopButton,
        true,
        "STOPPING...",
        "STOP VOICE SESSION"
    );
    setConversationState("STOPPING");

    try {
        const data = await apiRequest("/api/voice/session/stop", {
            method: "POST",
            body: JSON.stringify({})
        });
        addMessage("SYSTEM", data.message || "Voice session stopping.");
    } catch (error) {
        console.error("ATLAS VOICE SESSION STOP ERROR:", error);
        addMessage("SYSTEM", "Could not stop voice session: " + error.message);
        setConversationState("ERROR");
    } finally {
        voiceControlRequestInProgress = false;
        setButtonBusy(
            voiceSessionStopButton,
            false,
            "STOPPING...",
            "STOP VOICE SESSION"
        );
        updateHUDStatus();
    }
}

if (voiceSessionStopButton) {
    voiceSessionStopButton.addEventListener("click", stopVoiceSession);
}

// ==================================================
// VOICE OUTPUT — FISH AUDIO / FALLBACK
// ==================================================

async function speakResponse(text) {
    if (!voiceEnabled || !voiceAvailable || !text || !text.trim()) return;

    try {
        await apiRequest("/api/voice/speak", {
            method: "POST",
            body: JSON.stringify({ text })
        });
    } catch (error) {
        console.error("ATLAS VOICE OUTPUT ERROR:", error);

        addMessage(
            "SYSTEM",
            "Speech output could not start: " + error.message
        );
    }
}

async function stopSpeaking() {
    try {
        const data = await apiRequest("/api/voice/stop", {
            method: "POST",
            body: JSON.stringify({})
        });

        if (data.message) {
            addMessage("SYSTEM", data.message);
        }
    } catch (error) {
        console.error("ATLAS STOP SPEECH ERROR:", error);
        addMessage("SYSTEM", "Could not stop speech: " + error.message);
    }
}

if (stopSpeakingButton) {
    stopSpeakingButton.addEventListener("click", stopSpeaking);
}

// ==================================================
// VOICE OUTPUT SETTING
// ==================================================

async function setVoiceEnabled(enabled) {
    try {
        const data = await apiRequest("/api/voice/settings", {
            method: "POST",
            body: JSON.stringify({ enabled })
        });

        voiceEnabled = typeof data.voice_enabled === "boolean"
            ? data.voice_enabled
            : enabled;

        if (voiceToggle) {
            voiceToggle.checked = voiceEnabled;
            voiceToggle.setAttribute("aria-checked", String(voiceEnabled));
        }

        addMessage(
            "SYSTEM",
            voiceEnabled ? "Spoken responses enabled." : "Spoken responses disabled."
        );
    } catch (error) {
        console.error("ATLAS VOICE SETTINGS ERROR:", error);

        if (voiceToggle) {
            voiceToggle.checked = voiceEnabled;
        }

        addMessage("SYSTEM", "Could not change voice settings: " + error.message);
    }
}

if (voiceToggle) {
    voiceToggle.checked = voiceEnabled;

    voiceToggle.addEventListener("change", () => {
        setVoiceEnabled(voiceToggle.checked);
    });
}

// ==================================================
// HUD HELPERS
// ==================================================

function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}

function setMeter(id, percentage) {
    const element = document.getElementById(id);
    if (!element) return;

    const numericPercentage = Number(percentage);
    if (!Number.isFinite(numericPercentage)) return;

    const safePercentage = Math.max(0, Math.min(100, numericPercentage));
    element.style.width = `${safePercentage}%`;
}

// ==================================================
// LIVE HUD TELEMETRY
// ==================================================

async function updateHUDStatus() {
    try {
        const data = await apiRequest("/api/status");

        // CORE
        setText("coreStatus", data.core || "UNKNOWN");

        // AI
        setText("aiStatus", data.ai || "UNKNOWN");

        // MEMORY
        setText("memoryStatus", data.memory || "UNKNOWN");

        // TOOLS
        setText("toolsStatus", data.tools || "UNKNOWN");

        // MEMORY COUNT
        if (typeof data.memory_count === "number") {
            setText("memoryCount", data.memory_count);
        }

        // CPU
        if (data.system) {
            const cpu = Number(data.system.cpu);

            if (Number.isFinite(cpu)) {
                setText("cpuValue", `${cpu.toFixed(1)}%`);
                setMeter("cpuMeter", cpu);
            }

            // RAM
            const ram = Number(data.system.ram);

            if (Number.isFinite(ram)) {
                setText("ramValue", `${ram.toFixed(1)}%`);
                setMeter("ramMeter", ram);
            }
        }

        // CORE DISPLAY
        setText("coreValue", data.core || "UNKNOWN");

        // VOICE STATUS
        const activity = String(data.activity || "READY").toUpperCase();
        setConversationState(activity);

        voiceAvailable = Boolean(data.voice_available);
        const voiceSessionActive = Boolean(data.voice_session_active);

        if (voiceSessionStartButton) {
            voiceSessionStartButton.disabled = !voiceAvailable ||
                voiceSessionActive ||
                Boolean(data.speaking) ||
                voiceControlRequestInProgress;
            voiceSessionStartButton.title = voiceAvailable
                ? "Start a continuous voice session"
                : "Voice dependencies are unavailable. Check the server terminal.";
        }

        if (voiceSessionStopButton) {
            voiceSessionStopButton.disabled = !voiceSessionActive ||
                Boolean(data.voice_session_stopping) ||
                voiceControlRequestInProgress;
        }

        if (stopSpeakingButton) {
            stopSpeakingButton.disabled = !Boolean(data.speaking);
        }

        if (voiceToggle && typeof data.voice_enabled === "boolean") {
            voiceEnabled = data.voice_enabled;
            voiceToggle.checked = voiceEnabled;
        }

        const voiceEventId = Number(data.voice_event_id) || 0;
        if (voiceEventId > lastVoiceEventId && data.last_transcript) {
            lastVoiceEventId = voiceEventId;
            addMessage("YOU (VOICE)", data.last_transcript);
        }

        const voiceResponseId = Number(data.voice_response_id) || 0;
        if (voiceResponseId > lastVoiceResponseId && data.last_response) {
            lastVoiceResponseId = voiceResponseId;
            addMessage("ATLAS", data.last_response);
        }

        if (data.last_error) {
            setText("voiceError", data.last_error);
        } else {
            setText("voiceError", "");
        }

        document.body.classList.remove("atlas-offline");
    } catch (error) {
        console.error("ATLAS STATUS ERROR:", error);

        setText("coreStatus", "OFFLINE");
        setText("aiStatus", "OFFLINE");
        setText("memoryStatus", "OFFLINE");
        setText("toolsStatus", "OFFLINE");
        setText("coreValue", "OFFLINE");
        setConversationState("OFFLINE");

        document.body.classList.add("atlas-offline");
    }
}

// ==================================================
// PANEL CONTROLS
// ==================================================

function syncPanelButtons() {
    if (!hud) return;

    const leftVisible = !hud.classList.contains("left-panel-collapsed");
    const rightVisible = !hud.classList.contains("right-panel-collapsed");

    if (toggleLeftPanelButton) {
        toggleLeftPanelButton.setAttribute("aria-expanded", String(leftVisible));
    }
    if (toggleRightPanelButton) {
        toggleRightPanelButton.setAttribute("aria-expanded", String(rightVisible));
    }
    if (toggleSidePanelsButton) {
        toggleSidePanelsButton.setAttribute(
            "aria-expanded",
            String(leftVisible || rightVisible)
        );
    }
}

if (hud && toggleLeftPanelButton) {
    toggleLeftPanelButton.addEventListener("click", () => {
        hud.classList.toggle("left-panel-collapsed");
        syncPanelButtons();
    });
}

if (hud && toggleRightPanelButton) {
    toggleRightPanelButton.addEventListener("click", () => {
        hud.classList.toggle("right-panel-collapsed");
        syncPanelButtons();
    });
}

if (hud && toggleSidePanelsButton) {
    toggleSidePanelsButton.addEventListener("click", () => {
        const panelsVisible = !hud.classList.contains("left-panel-collapsed") ||
            !hud.classList.contains("right-panel-collapsed");
        hud.classList.toggle("left-panel-collapsed", panelsVisible);
        hud.classList.toggle("right-panel-collapsed", panelsVisible);
        syncPanelButtons();
    });
}

syncPanelButtons();

// ==================================================
// LIVE SYSTEM LOG
// ==================================================

async function updateSystemLog() {
    const logContainer = document.querySelector(".system-log");
    if (!logContainer) return;

    try {
        const data = await apiRequest("/api/logs");

        if (!Array.isArray(data.logs)) {
            console.warn("ATLAS SYSTEM LOG: invalid log format.");
            return;
        }

        logContainer.replaceChildren();

        data.logs.slice(-6).forEach((entry) => {
            const line = document.createElement("div");
            line.className = "system-log-entry";
            line.textContent = `${entry.time}  ${entry.message}`;
            logContainer.appendChild(line);
        });
    } catch (error) {
        console.error("ATLAS LOG ERROR:", error);
    }
}

// ==================================================
// START LIVE SYSTEMS
// ==================================================

updateHUDStatus();
updateSystemLog();

setInterval(updateHUDStatus, 1000);
setInterval(updateSystemLog, 1000);

// ==================================================
// INITIAL MESSAGE
// ==================================================

addMessage("SYSTEM", "ATLAS HUD interface initialized.");
