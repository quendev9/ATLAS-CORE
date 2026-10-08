const input = document.getElementById("commandInput");
const sendButton = document.getElementById("sendButton");
const messages = document.getElementById("messages");
const hud = document.querySelector(".hud");
const expandChatButton = document.getElementById("expandChatButton");


// ==================================================
// MESSAGE SYSTEM
// ==================================================

function addMessage(sender, text) {
    const message = document.createElement("div");
    message.className = "message";

    const senderElement = document.createElement("div");
    senderElement.className = "message-label";
    senderElement.textContent = sender;

    const textElement = document.createElement("div");
    textElement.className = "message-text";
    textElement.textContent = text;

    message.appendChild(senderElement);
    message.appendChild(textElement);

    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
}


// ==================================================
// CHAT
// ==================================================

async function sendCommand(command) {
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: command
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "ATLAS request failed."
            );
        }

        addMessage("ATLAS", data.response);

    } catch (error) {
        console.error("ATLAS API ERROR:", error);

        addMessage(
            "SYSTEM",
            "ATLAS Core connection error: " + error.message
        );
    }
}


function handleCommand() {
    const command = input.value.trim();

    if (!command) {
        return;
    }

    addMessage("YOU", command);

    input.value = "";

    sendButton.disabled = true;

    sendCommand(command).finally(() => {
        sendButton.disabled = false;
        input.focus();
    });
}


sendButton.addEventListener("click", handleCommand);


input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleCommand();
    }
});


// ==================================================
// CHAT EXPAND / COLLAPSE
// ==================================================

if (expandChatButton) {
    expandChatButton.addEventListener("click", () => {
        const expanded = hud.classList.toggle("chat-expanded");

        expandChatButton.textContent =
            expanded ? "COLLAPSE" : "EXPAND";

        input.focus();
    });
}


// ==================================================
// HUD HELPER FUNCTIONS
// ==================================================

function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}


function setMeter(id, percentage) {
    const element = document.getElementById(id);

    if (!element) {
        return;
    }

    const numericPercentage = Number(percentage);

    if (!Number.isFinite(numericPercentage)) {
        return;
    }

    const safePercentage = Math.max(
        0,
        Math.min(100, numericPercentage)
    );

    element.style.width = `${safePercentage}%`;
}


// ==================================================
// LIVE HUD TELEMETRY
// ==================================================

async function updateHUDStatus() {
    try {
        const response = await fetch("/api/status", {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(
                `Status request failed (${response.status})`
            );
        }

        const data = await response.json();

        console.log("ATLAS STATUS:", data);


        // ------------------------------------------
        // CORE STATUS
        // ------------------------------------------

        setText(
            "coreStatus",
            data.core || "UNKNOWN"
        );


        // ------------------------------------------
        // AI STATUS
        // ------------------------------------------

        setText(
            "aiStatus",
            data.ai || "UNKNOWN"
        );


        // ------------------------------------------
        // MEMORY STATUS
        // ------------------------------------------

        setText(
            "memoryStatus",
            data.memory || "UNKNOWN"
        );


        // ------------------------------------------
        // TOOLS STATUS
        // ------------------------------------------

        setText(
            "toolsStatus",
            data.tools || "UNKNOWN"
        );


        // ------------------------------------------
        // MEMORY COUNT
        // ------------------------------------------

        if (
            typeof data.memory_count === "number"
        ) {
            setText(
                "memoryCount",
                data.memory_count
            );
        }


        // ------------------------------------------
        // CPU
        // ------------------------------------------

        if (data.system) {
            const cpu = Number(data.system.cpu);

            if (Number.isFinite(cpu)) {
                setText(
                    "cpuValue",
                    `${cpu.toFixed(1)}%`
                );

                setMeter(
                    "cpuMeter",
                    cpu
                );
            }
        }


        // ------------------------------------------
        // RAM
        // ------------------------------------------

        if (data.system) {
            const ram = Number(data.system.ram);

            if (Number.isFinite(ram)) {
                setText(
                    "ramValue",
                    `${ram.toFixed(1)}%`
                );

                setMeter(
                    "ramMeter",
                    ram
                );
            }
        }


        // ------------------------------------------
        // CORE DISPLAY
        // ------------------------------------------
        // We do not invent a fake percentage here.
        // The Core currently exposes a real status,
        // not a CPU/activity percentage.

        setText(
            "coreValue",
            data.core || "UNKNOWN"
        );


        // ------------------------------------------
        // CONNECTION STATE
        // ------------------------------------------

        document.body.classList.remove(
            "atlas-offline"
        );

    } catch (error) {
        console.error(
            "ATLAS STATUS ERROR:",
            error
        );

        // ------------------------------------------
        // BACKEND OFFLINE
        // ------------------------------------------

        setText(
            "coreStatus",
            "OFFLINE"
        );

        setText(
            "aiStatus",
            "OFFLINE"
        );

        setText(
            "memoryStatus",
            "OFFLINE"
        );

        setText(
            "toolsStatus",
            "OFFLINE"
        );

        setText(
            "coreValue",
            "OFFLINE"
        );

        document.body.classList.add(
            "atlas-offline"
        );
    }
}


// ==================================================
// START LIVE TELEMETRY
// ==================================================

updateHUDStatus();

setInterval(
    updateHUDStatus,
    1000
);


// ==================================================
// INITIAL SYSTEM MESSAGE
// ==================================================

addMessage(
    "SYSTEM",
    "ATLAS HUD interface initialized."
);