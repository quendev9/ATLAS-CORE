
const input = document.getElementById("commandInput");
const sendButton = document.getElementById("sendButton");
const messages = document.getElementById("messages");
const hud = document.querySelector(".hud");
const expandChatButton = document.getElementById("expandChatButton");
const coreOrb = document.getElementById("coreOrb");
const voiceCard = document.querySelector(".voice-card");

const voiceSessionStartButton = document.getElementById("voiceSessionStart");
const voiceSessionStopButton = document.getElementById("voiceSessionStop");
const quickVoiceSessionButton = document.querySelector("[data-voice-toggle]");
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
let voiceOutputAvailable = false;
let voiceControlRequestInProgress = false;
let voiceSessionOperation = null;
let voiceSessionActive = false;
let voiceSessionStopping = false;
let voiceSpeaking = false;
let statusRequestId = 0;
let lastVoiceEventId = 0;
let lastVoiceResponseId = 0;
let taskStartedAt = null;

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

function updateClock() {
    const clock = document.getElementById("systemClock");
    if (!clock) return;

    const now = new Date();
    clock.replaceChildren(
        document.createTextNode(now.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
        }))
    );
    const date = document.createElement("small");
    date.textContent = now.toLocaleDateString([], {
        month: "short",
        day: "numeric",
        year: "numeric"
    });
    clock.appendChild(date);
}

function setOrbState(state) {
    if (!coreOrb) return;

    coreOrb.dataset.state = state;
    const label = document.getElementById("orbStatusLabel");
    const labels = {
        idle: "STANDBY",
        listening: "LISTENING",
        thinking: "PROCESSING",
        speaking: "SPEAKING",
        "tool-execution": "TOOL EXECUTION"
    };
    coreOrb.setAttribute("aria-label", `ATLAS assistant ${labels[state] || labels.idle.toLowerCase()}`);
    if (label) label.textContent = labels[state] || labels.idle;
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
    taskStartedAt = Date.now();
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
        taskStartedAt = null;
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
        expandChatButton.setAttribute("aria-expanded", String(expanded));

        if (input) input.focus();
    });
}

document.querySelectorAll(".action-card[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
        if (!input) return;
        input.value = button.dataset.prompt || "";
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
    });
});

if (quickVoiceSessionButton) {
    quickVoiceSessionButton.addEventListener("click", () => {
        if (voiceSessionActive) {
            stopVoiceSession();
        } else {
            startVoiceSession();
        }
    });
}

document.querySelectorAll(".nav-item").forEach((link) => {
    link.addEventListener("click", () => {
        const activeLink = document.querySelector(".nav-item.active");
        if (activeLink) activeLink.removeAttribute("aria-current");
        document.querySelector(".nav-item.active")?.classList.remove("active");
        link.classList.add("active");
        link.setAttribute("aria-current", "page");

        if (link.getAttribute("href") === "#voiceSettings") {
            const voiceSettings = document.getElementById("voiceSettings");
            if (voiceSettings) voiceSettings.open = true;
        }
    });
});

// ==================================================
// CONTINUOUS VOICE SESSION
// ==================================================

function syncVoiceSessionControls() {
    const busy = voiceControlRequestInProgress;
    const quickLabel = voiceSessionOperation === "starting" ? "STARTING..." :
        voiceSessionOperation === "stopping" ||
            (voiceSessionActive && voiceSessionStopping) ? "STOPPING..." :
            voiceSessionActive ? "STOP VOICE SESSION" : "START VOICE SESSION";

    if (quickVoiceSessionButton) {
        const label = quickVoiceSessionButton.querySelector("strong");
        const description = quickVoiceSessionButton.querySelector("small");
        if (label) label.textContent = quickLabel;
        if (description) {
            description.textContent = voiceSessionOperation === "starting"
                ? "Requesting microphone access..."
                : voiceSessionOperation === "stopping" || voiceSessionStopping
                    ? "Waiting for the voice session to stop"
                    : voiceSessionActive
                        ? "End live microphone input"
                        : "Enable live microphone input";
        }
        quickVoiceSessionButton.disabled = busy ||
            (voiceSessionActive && voiceSessionStopping) ||
            (!voiceSessionActive && (!voiceAvailable || voiceSpeaking));
        quickVoiceSessionButton.setAttribute("aria-busy", String(busy));
        quickVoiceSessionButton.setAttribute("aria-pressed", String(voiceSessionActive));
        quickVoiceSessionButton.title = voiceSessionActive
            ? "Stop the continuous voice session"
            : voiceAvailable
                ? "Start a continuous voice session"
                : "Voice dependencies are unavailable. Check the server terminal.";
    }

    if (voiceSessionStartButton) {
        voiceSessionStartButton.disabled = busy || voiceSessionActive ||
            !voiceAvailable || voiceSpeaking;
        voiceSessionStartButton.textContent =
            voiceSessionOperation === "starting" ? "STARTING..." : "START VOICE SESSION";
        voiceSessionStartButton.setAttribute("aria-busy", String(busy));
    }

    if (voiceSessionStopButton) {
        voiceSessionStopButton.disabled = busy || !voiceSessionActive ||
            voiceSessionStopping;
        voiceSessionStopButton.textContent =
            voiceSessionOperation === "stopping" ||
                (voiceSessionActive && voiceSessionStopping)
                ? "STOPPING..." : "STOP VOICE SESSION";
        voiceSessionStopButton.setAttribute("aria-busy", String(busy));
    }
}

async function startVoiceSession() {
    if (voiceControlRequestInProgress || voiceSessionActive ||
        !voiceAvailable || voiceSpeaking) return;

    voiceControlRequestInProgress = true;
    voiceSessionOperation = "starting";
    syncVoiceSessionControls();
    setConversationState("STARTING");

    try {
        const data = await apiRequest("/api/voice/session/start", {
            method: "POST",
            body: JSON.stringify({})
        });

        if (data.voice_session_active !== true) {
            throw new Error(data.message || "The server did not confirm that the voice session started.");
        }

        voiceSessionActive = true;
        voiceSessionStopping = false;
        addMessage("SYSTEM", data.message || "Voice session started.");
    } catch (error) {
        console.error("ATLAS VOICE SESSION ERROR:", error);
        addMessage("SYSTEM", "Could not start voice session: " + error.message);
        setConversationState("ERROR");
    } finally {
        voiceControlRequestInProgress = false;
        voiceSessionOperation = null;
        syncVoiceSessionControls();
        await updateHUDStatus();
    }
}

if (voiceSessionStartButton) {
    voiceSessionStartButton.addEventListener("click", startVoiceSession);
}

async function stopVoiceSession() {
    if (voiceControlRequestInProgress || !voiceSessionActive ||
        voiceSessionStopping) return;

    voiceControlRequestInProgress = true;
    voiceSessionOperation = "stopping";
    syncVoiceSessionControls();
    setConversationState("STOPPING");

    try {
        const data = await apiRequest("/api/voice/session/stop", {
            method: "POST",
            body: JSON.stringify({})
        });
        if (typeof data.voice_session_active === "boolean") {
            voiceSessionActive = data.voice_session_active;
        }
        voiceSessionStopping = data.voice_session_stopping === true ||
            data.activity === "STOPPING";
        addMessage("SYSTEM", data.message || "Voice session stopping.");
    } catch (error) {
        console.error("ATLAS VOICE SESSION STOP ERROR:", error);
        addMessage("SYSTEM", "Could not stop voice session: " + error.message);
        setConversationState("ERROR");
    } finally {
        voiceControlRequestInProgress = false;
        voiceSessionOperation = null;
        syncVoiceSessionControls();
        await updateHUDStatus();
    }
}

if (voiceSessionStopButton) {
    voiceSessionStopButton.addEventListener("click", stopVoiceSession);
}

// ==================================================
// VOICE OUTPUT — FISH AUDIO / FALLBACK
// ==================================================

async function speakResponse(text) {
    if (!voiceEnabled || !voiceOutputAvailable || !text || !text.trim()) return;

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
    element.style.height = `${safePercentage}%`;
}

// ==================================================
// LIVE HUD TELEMETRY
// ==================================================

async function updateHUDStatus() {
    const requestId = ++statusRequestId;

    try {
        const data = await apiRequest("/api/status");
        if (requestId !== statusRequestId) return;

        const coreOnline = String(data.core || "").toUpperCase() === "ONLINE";

        // CORE
        const systemStatusItem = document.getElementById("systemStatusItem");
        if (systemStatusItem) {
            systemStatusItem.dataset.status = coreOnline ? "online" : "offline";
            const statusText = systemStatusItem.querySelector("strong");
            if (statusText) statusText.textContent = data.core || "UNKNOWN";
        }

        // AI
        setText("aiStatus", data.ai || "UNKNOWN");
        setText("aiProviderName", data.ai_provider || "Unavailable");
        setText("providerCardName", data.ai_provider || "Unavailable");
        setText("providerCardModel", data.ai_model || "Model not reported");
        setText("providerCardStatus", data.ai || "UNKNOWN");

        // MEMORY
        setText("memoryStatus", data.memory || "UNKNOWN");
        const memoryStatus = String(data.memory || "UNKNOWN").toUpperCase();
        setText(
            "memoryActivityStatus",
            memoryStatus === "ACTIVE" ? "Memory available" :
                memoryStatus === "ERROR" ? "Memory status error" :
                    "Memory unavailable"
        );
        // MEMORY COUNT
        if (typeof data.memory_count === "number") {
            setText("memoryCount", data.memory_count);
        } else {
            setText("memoryCount", "Unavailable");
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
        const listening = Boolean(data.listening);
        const speaking = Boolean(data.speaking);
        const processing = requestInProgress || Boolean(data.processing) ||
            activity === "PROCESSING";
        let orbState = "idle";

        if (speaking) {
            orbState = "speaking";
        } else if (listening) {
            orbState = "listening";
        } else if (processing) {
            orbState = "thinking";
        } else if (activity === "TOOL EXECUTION") {
            orbState = "tool-execution";
        }
        setOrbState(orbState);
        setConversationState(processing ? "PROCESSING" : activity);
        setText("taskTitle", processing ? "Processing conversation" : "No active tasks");
        setText("taskDescription", processing ? "Waiting for ATLAS response" : "Waiting for a request");
        setText("taskDuration", taskStartedAt
            ? `${Math.max(0, Math.floor((Date.now() - taskStartedAt) / 1000))}s`
            : "—");
        setText("taskCount", processing ? "1 running" : "0 running");
        setText("footerTaskStatus", processing ? "Processing conversation..." : "No active task");
        setText("footerTaskPercent", processing ? "In progress" : "—");
        const taskIndicator = document.getElementById("taskIndicator");
        if (taskIndicator) taskIndicator.dataset.active = String(processing);
        const taskProgressBar = document.getElementById("taskProgressBar");
        const progressTrack = document.querySelector(".progress-track");
        if (progressTrack) progressTrack.dataset.active = String(processing);
        if (taskProgressBar) taskProgressBar.style.width = processing ? "" : "0%";

        voiceAvailable = Boolean(data.voice_available);
        voiceOutputAvailable = Boolean(data.voice_output_available);
        voiceSessionActive = Boolean(data.voice_session_active);
        voiceSessionStopping = Boolean(data.voice_session_stopping);
        voiceSpeaking = speaking;
        setText(
            "voiceStatus",
            !voiceAvailable ? "UNAVAILABLE" : speaking ? "SPEAKING" :
                listening || voiceSessionActive ? "LISTENING" : "INACTIVE"
        );
        setText(
            "voiceCardStatus",
            !voiceAvailable ? "UNAVAILABLE" : speaking ? "SPEAKING" :
                listening || voiceSessionActive ? "ACTIVE" : "INACTIVE"
        );
        setText("voiceInputState", !voiceAvailable ? "Unavailable" :
            listening || voiceSessionActive ? "Active" : "Inactive");
        setText(
            "voiceOutputStatus",
            !voiceOutputAvailable ? "Unavailable" :
                data.voice_enabled ? (speaking ? "Speaking" : "On") : "Off"
        );
        if (voiceCard) {
            voiceCard.dataset.active = String(voiceAvailable && (speaking || listening || voiceSessionActive));
        }

        syncVoiceSessionControls();

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

        document.body.classList.toggle("atlas-offline", !coreOnline);
    } catch (error) {
        if (requestId !== statusRequestId) return;

        console.error("ATLAS STATUS ERROR:", error);

        setText("coreStatus", "OFFLINE");
        setText("aiStatus", "OFFLINE");
        setText("aiProviderName", "Unavailable");
        setText("providerCardName", "Unavailable");
        setText("providerCardStatus", "OFFLINE");
        setText("memoryStatus", "OFFLINE");
        setText("memoryCount", "Unavailable");
        setText("coreValue", "OFFLINE");
        setText("voiceStatus", "UNAVAILABLE");
        setText("voiceCardStatus", "UNAVAILABLE");
        setText("voiceInputState", "Unavailable");
        voiceAvailable = false;
        voiceOutputAvailable = false;
        voiceSpeaking = false;
        syncVoiceSessionControls();
        setText("memoryActivityStatus", "Status unavailable");
        setText("cpuValue", "Unavailable");
        setText("ramValue", "Unavailable");
        setMeter("cpuMeter", 0);
        setMeter("ramMeter", 0);
        setText("taskTitle", "Status unavailable");
        setText("taskDescription", "Cannot verify active tasks");
        setText("taskDuration", "—");
        setText("taskCount", "Unavailable");
        setText("footerTaskStatus", "Status unavailable");
        setText("footerTaskPercent", "—");
        const taskIndicator = document.getElementById("taskIndicator");
        if (taskIndicator) taskIndicator.dataset.active = "false";
        const progressTrack = document.querySelector(".progress-track");
        if (progressTrack) progressTrack.dataset.active = "false";
        const taskProgressBar = document.getElementById("taskProgressBar");
        if (taskProgressBar) taskProgressBar.style.width = "0%";
        if (voiceCard) voiceCard.dataset.active = "false";
        setOrbState("idle");
        const systemStatusItem = document.getElementById("systemStatusItem");
        if (systemStatusItem) {
            systemStatusItem.dataset.status = "offline";
            const statusText = systemStatusItem.querySelector("strong");
            if (statusText) statusText.textContent = "OFFLINE";
        }
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
        const bothHidden = hud.classList.contains("left-panel-collapsed") &&
            hud.classList.contains("right-panel-collapsed");

        if (bothHidden) {
            hud.classList.remove("left-panel-collapsed", "right-panel-collapsed");
        } else {
            hud.classList.add("left-panel-collapsed", "right-panel-collapsed");
        }

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

        const recentLogs = data.logs.slice(-4);
        setText("notificationCount", recentLogs.length);
        if (!recentLogs.length) {
            const empty = document.createElement("span");
            empty.className = "empty-log";
            empty.textContent = "No recent system events";
            logContainer.appendChild(empty);
            return;
        }

        recentLogs.forEach((entry) => {
            const line = document.createElement("div");
            line.className = "system-log-entry";
            const message = document.createElement("span");
            message.textContent = String(entry.message || "System event");
            const time = document.createElement("time");
            time.textContent = String(entry.time || "");
            line.append(message, time);
            logContainer.appendChild(line);
        });
    } catch (error) {
        console.error("ATLAS LOG ERROR:", error);
    }
}

// ==================================================
// START LIVE SYSTEMS
// ==================================================

syncVoiceSessionControls();
updateHUDStatus();
updateSystemLog();
updateClock();

setInterval(updateHUDStatus, 1000);
setInterval(updateSystemLog, 1000);
setInterval(updateClock, 30_000);

// ==================================================
// INITIAL MESSAGE
// ==================================================

addMessage("SYSTEM", "ATLAS HUD interface initialized.");
