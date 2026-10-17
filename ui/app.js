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
const aiModelSelect = document.getElementById("aiModelSelect");
const applyAIModelButton = document.getElementById("applyAIModelButton");
const aiModelSelectionStatus = document.getElementById("aiModelSelectionStatus");

// Existing NEW button stays in the conversation header.
const newConversationButton = document.getElementById("newConversationButton");

// Conversation drawer elements.
const conversationDrawer = document.getElementById("conversationDrawer");
const conversationDrawerBackdrop = document.getElementById("conversationDrawerBackdrop");
const conversationList = document.getElementById("conversationList");
const conversationCount = document.getElementById("conversationCount");
const conversationDrawerStatus = document.getElementById("conversationDrawerStatus");
const closeConversationDrawerButton = document.getElementById("closeConversationDrawerButton");
const conversationNavLink = document.querySelector('.nav-item[href="#conversation"]');

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
let aiModelSelectionDirty = false;
let aiModelSelectionSaving = false;
let lastVoiceEventId = 0;
let lastVoiceResponseId = 0;
let taskStartedAt = null;
let activeConversationId = null;
let conversationListReady = false;
let conversationActionInProgress = false;
let conversationDrawerOpen = false;
let conversationRequestId = 0;
let conversationListRequestId = 0;
let conversationDrawerReturnFocus = null;

// ==================================================
// MESSAGE SYSTEM
// ==================================================

function appendInlineMarkdown(parent, source) {
    const tokenPattern = /(`[^`\n]+`|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\*[^*\n]+\*|_[^_\n]+_|\[[^\]]+\]\([^)]+\))/g;
    let cursor = 0;

    for (const match of source.matchAll(tokenPattern)) {
        parent.appendChild(document.createTextNode(source.slice(cursor, match.index)));

        const token = match[0];
        let element;

        if (token.startsWith("`")) {
            element = document.createElement("code");
            element.textContent = token.slice(1, -1);
        } else if (token.startsWith("**") || token.startsWith("__")) {
            element = document.createElement("strong");
            appendInlineMarkdown(element, token.slice(2, -2));
        } else if (token.startsWith("~~")) {
            element = document.createElement("del");
            appendInlineMarkdown(element, token.slice(2, -2));
        } else if (token.startsWith("*") || token.startsWith("_")) {
            element = document.createElement("em");
            appendInlineMarkdown(element, token.slice(1, -1));
        } else {
            const link = token.match(/^\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)$/);
            let destination = null;

            try {
                if (link) destination = new URL(link[2], window.location.href);
            } catch {
                destination = null;
            }

            if (
                !link ||
                !destination ||
                !["https:", "http:", "mailto:"].includes(destination.protocol)
            ) {
                parent.appendChild(document.createTextNode(token));
                cursor = match.index + token.length;
                continue;
            }

            element = document.createElement("a");
            element.href = destination.href;
            element.target = "_blank";
            element.rel = "noopener noreferrer";
            appendInlineMarkdown(element, link[1]);
        }

        parent.appendChild(element);
        cursor = match.index + token.length;
    }

    parent.appendChild(document.createTextNode(source.slice(cursor)));
}

function renderMarkdown(target, value) {
    const lines = String(value ?? "").replace(/\r\n?/g, "\n").split("\n");
    let index = 0;

    while (index < lines.length) {
        if (!lines[index].trim()) {
            index += 1;
            continue;
        }

        const fence = lines[index].match(/^\s*```(?:[\w+-]+)?\s*$/);

        if (fence) {
            index += 1;
            const codeLines = [];

            while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
                codeLines.push(lines[index]);
                index += 1;
            }

            if (index < lines.length) index += 1;

            const pre = document.createElement("pre");
            const code = document.createElement("code");
            code.textContent = codeLines.join("\n");
            pre.appendChild(code);
            target.appendChild(pre);
            continue;
        }

        const heading = lines[index].match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);

        if (heading) {
            const element = document.createElement(`h${Math.min(4, heading[1].length + 1)}`);
            appendInlineMarkdown(element, heading[2]);
            target.appendChild(element);
            index += 1;
            continue;
        }

        const listItem = lines[index].match(/^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$/);

        if (listItem) {
            const ordered = /^\s*\d+[.)]/.test(lines[index]);
            const list = document.createElement(ordered ? "ol" : "ul");

            while (index < lines.length) {
                const item = lines[index].match(/^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$/);

                if (!item || /^\s*\d+[.)]/.test(lines[index]) !== ordered) break;

                const li = document.createElement("li");
                appendInlineMarkdown(li, item[1]);
                list.appendChild(li);
                index += 1;
            }

            target.appendChild(list);
            continue;
        }

        if (/^\s*>\s?/.test(lines[index])) {
            const quote = document.createElement("blockquote");

            while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
                const paragraph = document.createElement("p");
                appendInlineMarkdown(paragraph, lines[index].replace(/^\s*>\s?/, ""));
                quote.appendChild(paragraph);
                index += 1;
            }

            target.appendChild(quote);
            continue;
        }

        const paragraph = document.createElement("p");
        const paragraphLines = [];

        while (
            index < lines.length &&
            lines[index].trim() &&
            !/^\s{0,3}(?:#{1,6}\s|```)/.test(lines[index]) &&
            !/^\s*(?:[-*+]\s+|\d+[.)]\s+|>)/.test(lines[index])
        ) {
            paragraphLines.push(lines[index]);
            index += 1;
        }

        appendInlineMarkdown(paragraph, paragraphLines.join(" "));
        target.appendChild(paragraph);
    }
}

function addMessage(sender, text) {
    if (!messages) return;

    // Remove the empty-state message when the first real message arrives.
    messages.querySelector(".empty-conversation")?.remove();

    const message = document.createElement("div");
    message.className = "message";

    const senderElement = document.createElement("div");
    senderElement.className = "message-label";
    senderElement.textContent = sender;

    const textElement = document.createElement("div");
    textElement.className = "message-text";
    renderMarkdown(textElement, text);

    message.append(senderElement, textElement);
    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
}

function showEmptyConversation() {
    if (!messages) return;

    messages.replaceChildren();

    const empty = document.createElement("p");
    empty.className = "empty-conversation";
    empty.textContent = "No messages yet. Start a conversation below.";
    messages.appendChild(empty);
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
        document.createTextNode(
            now.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit"
            })
        )
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

    coreOrb.setAttribute(
        "aria-label",
        `LEWIS assistant ${labels[state] || labels.idle}`
    );

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
        throw new Error(data.error || `Request failed (${response.status})`);
    }

    return data;
}

function syncConversationControls() {
    const busy =
        requestInProgress ||
        voiceSessionActive ||
        Boolean(voiceSessionOperation) ||
        conversationActionInProgress;

    if (newConversationButton) {
        newConversationButton.disabled = busy || !conversationListReady;
    }

    if (conversationDrawer) {
        conversationDrawer.setAttribute(
            "aria-busy",
            String(conversationActionInProgress)
        );
    }

    conversationList?.querySelectorAll(
        ".conversation-list-open, .conversation-rename-button, " +
        ".conversation-delete-button, .conversation-rename-input, " +
        ".conversation-rename-save, .conversation-rename-cancel"
    ).forEach((control) => {
        control.disabled = busy;
    });
}

function setConversationDrawerStatus(message, isError = false) {
    if (!conversationDrawerStatus) return;

    conversationDrawerStatus.textContent = message || "";
    conversationDrawerStatus.dataset.state = isError ? "error" : "normal";
}

function openConversationDrawer() {
    if (!conversationDrawer) {
        // The drawer markup has not been added yet.
        addMessage("SYSTEM", "The conversation drawer is not present in ui/index.html yet.");
        return;
    }

    conversationDrawerReturnFocus = document.activeElement;
    conversationDrawerOpen = true;
    conversationDrawer.hidden = false;
    conversationDrawer.setAttribute("aria-hidden", "false");
    conversationDrawer.removeAttribute("inert");

    if (conversationDrawerBackdrop) {
        conversationDrawerBackdrop.hidden = false;
    }

    document.body.classList.add("conversation-drawer-open");

    if (conversationNavLink) {
        conversationNavLink.setAttribute("aria-expanded", "true");
    }

    setConversationDrawerStatus("");
    closeConversationDrawerButton?.focus();

    refreshConversationList(activeConversationId).catch((error) => {
        console.error("LEWIS CONVERSATION LIST ERROR:", error);
        setConversationDrawerStatus(
            `Could not load conversations: ${error.message}`,
            true
        );
    });
}

function closeConversationDrawer() {
    conversationDrawerOpen = false;

    if (conversationDrawer) {
        conversationDrawer.hidden = true;
        conversationDrawer.setAttribute("aria-hidden", "true");
        conversationDrawer.setAttribute("inert", "");
    }

    if (conversationDrawerBackdrop) {
        conversationDrawerBackdrop.hidden = true;
    }

    document.body.classList.remove("conversation-drawer-open");

    if (conversationNavLink) {
        conversationNavLink.setAttribute("aria-expanded", "false");
    }

    const returnFocus = conversationDrawerReturnFocus;
    conversationDrawerReturnFocus = null;
    if (returnFocus instanceof HTMLElement && returnFocus.isConnected) {
        returnFocus.focus();
    } else {
        conversationNavLink?.focus();
    }
}

function displayConversation(conversation) {
    if (!conversation || typeof conversation.id !== "string") return;

    activeConversationId = conversation.id;

    if (!messages) return;

    messages.replaceChildren();

    const history = Array.isArray(conversation.messages)
        ? conversation.messages
        : [];

    if (!history.length) {
        showEmptyConversation();
    } else {
        history.forEach((entry) => {
            const role = String(entry.role || "").toLowerCase();
            const sender =
                role === "user" ? "YOU" :
                role === "assistant" ? "LEWIS" :
                "SYSTEM";

            addMessage(sender, entry.content || "");
        });
    }

    renderConversationListActiveState();
}

function createConversationListItem(conversation) {
    const item = document.createElement("article");
    item.className = "conversation-list-item";

    const mainButton = document.createElement("button");
    mainButton.type = "button";
    mainButton.className = "conversation-list-open";
    mainButton.dataset.conversationId = conversation.id;

    const title = document.createElement("span");
    title.className = "conversation-list-title";
    title.textContent = conversation.title || "New conversation";

    const metadata = document.createElement("small");
    metadata.className = "conversation-list-meta";

    const updatedAt = conversation.updated_at
        ? new Date(conversation.updated_at)
        : null;

    metadata.textContent =
        updatedAt && !Number.isNaN(updatedAt.getTime())
            ? updatedAt.toLocaleString([], {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit"
            })
            : "Saved conversation";

    mainButton.append(title, metadata);
    mainButton.addEventListener("click", () => {
        selectConversationFromDrawer(conversation.id);
    });

    const actions = document.createElement("div");
    actions.className = "conversation-list-actions";

    const renameButton = document.createElement("button");
    renameButton.type = "button";
    renameButton.className = "conversation-rename-button";
    renameButton.textContent = "RENAME";
    renameButton.title = `Rename ${title.textContent}`;
    renameButton.addEventListener("click", () => {
        openConversationRenameEditor(conversation, item, mainButton, actions);
    });

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "conversation-delete-button";
    deleteButton.textContent = "DELETE";
    deleteButton.title = `Delete ${title.textContent}`;
    deleteButton.addEventListener("click", () => {
        deleteConversationFromDrawer(conversation);
    });

    actions.append(renameButton, deleteButton);
    item.append(mainButton, actions);

    if (conversation.id === activeConversationId) {
        item.classList.add("active");
        mainButton.setAttribute("aria-current", "true");
    }

    return item;
}

function renderConversationList(conversations) {
    if (!conversationList) return;

    if (conversationCount) {
        conversationCount.textContent = `${conversations.length} SAVED`;
    }

    conversationList.replaceChildren();

    if (!conversations.length) {
        const empty = document.createElement("p");
        empty.className = "conversation-list-empty";
        empty.textContent = "No saved conversations yet.";
        conversationList.appendChild(empty);
        return;
    }

    conversations.forEach((conversation) => {
        conversationList.appendChild(createConversationListItem(conversation));
    });
}

function renderConversationListActiveState() {
    if (!conversationList) return;

    conversationList.querySelectorAll(".conversation-list-item").forEach((item) => {
        const button = item.querySelector(".conversation-list-open");
        const active = button?.dataset.conversationId === activeConversationId;

        item.classList.toggle("active", Boolean(active));

        if (button) {
            if (active) {
                button.setAttribute("aria-current", "true");
            } else {
                button.removeAttribute("aria-current");
            }
        }
    });
}

async function refreshConversationList(selectedId = null) {
    const listRequestId = ++conversationListRequestId;
    const data = await apiRequest("/api/conversations");

    if (listRequestId !== conversationListRequestId) return;

    if (!Array.isArray(data.conversations)) {
        throw new Error("The server returned an invalid conversation list.");
    }

    const ordered = [...data.conversations].sort((left, right) =>
        String(right.updated_at || "").localeCompare(
            String(left.updated_at || "")
        )
    );

    renderConversationList(ordered);
    conversationListReady = true;
    syncConversationControls();

    const targetId = selectedId || data.active_id || activeConversationId;

    if (!targetId) {
        activeConversationId = null;
        showEmptyConversation();
        renderConversationListActiveState();
        return;
    }

    // A response from an earlier refresh must not overwrite a newer selection.
    const requestId = ++conversationRequestId;

    const response = await apiRequest(
        `/api/conversations/${encodeURIComponent(targetId)}`
    );

    if (
        requestId !== conversationRequestId ||
        listRequestId !== conversationListRequestId
    ) return;

    displayConversation(response.conversation);
}

async function createConversationFromHUD() {
    if (
        !newConversationButton ||
        newConversationButton.disabled ||
        conversationActionInProgress
    ) {
        return;
    }

    conversationActionInProgress = true;
    syncConversationControls();

    try {
        const data = await apiRequest("/api/conversations", {
            method: "POST",
            body: JSON.stringify({})
        });

        const conversationId = data.conversation?.id;
        if (!conversationId) {
            throw new Error("The server did not return the new conversation ID.");
        }

        await refreshConversationList(conversationId);
        closeConversationDrawer();
        input?.focus();
    } catch (error) {
        console.error("LEWIS CONVERSATION CREATE ERROR:", error);
        setConversationDrawerStatus(
            `Could not create a conversation: ${error.message}`,
            true
        );
        addMessage("SYSTEM", `Could not create a conversation: ${error.message}`);
    } finally {
        conversationActionInProgress = false;
        syncConversationControls();
    }
}

async function selectConversationFromDrawer(selectedId) {
    if (
        !selectedId ||
        selectedId === activeConversationId ||
        conversationActionInProgress
    ) {
        if (selectedId === activeConversationId) closeConversationDrawer();
        return;
    }

    if (requestInProgress) {
        setConversationDrawerStatus(
            "Wait for the current message to finish before switching conversations.",
            true
        );
        return;
    }

    conversationActionInProgress = true;
    syncConversationControls();
    setConversationDrawerStatus("Opening conversation...");

    try {
        const data = await apiRequest("/api/conversations/select", {
            method: "POST",
            body: JSON.stringify({ id: selectedId })
        });

        if (!data.conversation) {
            throw new Error("The server did not return the selected conversation.");
        }

        // Invalidate outstanding conversation fetches before rendering this one.
        conversationRequestId += 1;
        displayConversation(data.conversation);
        await refreshConversationList(selectedId);
        closeConversationDrawer();
        input?.focus();
    } catch (error) {
        console.error("LEWIS CONVERSATION SELECT ERROR:", error);
        setConversationDrawerStatus(
            `Could not open that conversation: ${error.message}`,
            true
        );
    } finally {
        conversationActionInProgress = false;
        syncConversationControls();
    }
}

function openConversationRenameEditor(conversation, item, mainButton, actions) {
    if (conversationActionInProgress || requestInProgress) return;

    const editor = document.createElement("form");
    editor.className = "conversation-rename-editor";

    const titleInput = document.createElement("input");
    titleInput.className = "conversation-rename-input";
    titleInput.type = "text";
    titleInput.maxLength = 120;
    titleInput.value = String(conversation.title || "New conversation");
    titleInput.setAttribute("aria-label", "Conversation title");
    titleInput.required = true;

    const saveButton = document.createElement("button");
    saveButton.className = "conversation-rename-save";
    saveButton.type = "submit";
    saveButton.textContent = "SAVE";

    const cancelButton = document.createElement("button");
    cancelButton.className = "conversation-rename-cancel";
    cancelButton.type = "button";
    cancelButton.textContent = "CANCEL";

    editor.append(titleInput, saveButton, cancelButton);
    mainButton.hidden = true;
    actions.hidden = true;
    item.insertBefore(editor, mainButton);

    const closeEditor = () => {
        editor.remove();
        mainButton.hidden = false;
        actions.hidden = false;
    };

    cancelButton.addEventListener("click", () => {
        closeEditor();
        setConversationDrawerStatus("");
        mainButton.focus();
    });

    editor.addEventListener("submit", async (event) => {
        event.preventDefault();

        const title = titleInput.value.trim();
        if (!title) {
            titleInput.setCustomValidity("A conversation title cannot be empty.");
            titleInput.reportValidity();
            return;
        }

        titleInput.setCustomValidity("");
        if (title.length > 120) {
            setConversationDrawerStatus(
                "Conversation titles must be 120 characters or fewer.",
                true
            );
            titleInput.focus();
            return;
        }

        if (title === String(conversation.title || "New conversation")) {
            closeEditor();
            setConversationDrawerStatus("");
            return;
        }

        conversationActionInProgress = true;
        syncConversationControls();
        setConversationDrawerStatus("Saving title...");

        try {
            const data = await apiRequest("/api/conversations/rename", {
                method: "POST",
                body: JSON.stringify({ id: conversation.id, title })
            });

            if (!data.conversation || data.conversation.id !== conversation.id) {
                throw new Error("The server did not confirm the renamed conversation.");
            }

            await refreshConversationList(activeConversationId);
            setConversationDrawerStatus("Conversation title updated.");
        } catch (error) {
            console.error("LEWIS CONVERSATION RENAME ERROR:", error);
            setConversationDrawerStatus(
                `Could not rename conversation: ${error.message}`,
                true
            );
        } finally {
            conversationActionInProgress = false;
            syncConversationControls();
        }
    });

    titleInput.focus();
    titleInput.select();
}

async function deleteConversationFromDrawer(conversation) {
    if (conversationActionInProgress || requestInProgress) {
        if (requestInProgress) {
            setConversationDrawerStatus(
                "Wait for the current message to finish before deleting a conversation.",
                true
            );
        }
        return;
    }

    const title = String(conversation.title || "New conversation");
    const confirmed = window.confirm(
        `Delete "${title}" and its conversation history?\n\n` +
        "This cannot be undone. LEWIS's long-term memory will not be deleted."
    );

    if (!confirmed) return;

    conversationActionInProgress = true;
    syncConversationControls();
    setConversationDrawerStatus("Deleting conversation...");

    try {
        const data = await apiRequest("/api/conversations/delete", {
            method: "POST",
            body: JSON.stringify({ id: conversation.id })
        });

        const nextActiveId =
            data.active_conversation_id ||
            data.conversation?.id ||
            null;

        // Prevent any older request from rendering a conversation that was deleted.
        conversationRequestId += 1;

        if (conversation.id === activeConversationId) {
            activeConversationId = null;

            if (nextActiveId) {
                await refreshConversationList(nextActiveId);
            } else {
                await refreshConversationList(null);
            }
        } else {
            await refreshConversationList(activeConversationId);
        }

        setConversationDrawerStatus("Conversation deleted. Long-term memory was preserved.");
    } catch (error) {
        console.error("LEWIS CONVERSATION DELETE ERROR:", error);
        setConversationDrawerStatus(
            `Could not delete conversation: ${error.message}`,
            true
        );
    } finally {
        conversationActionInProgress = false;
        syncConversationControls();
    }
}

// ==================================================
// CONVERSATION DRAWER EVENTS
// ==================================================

if (conversationNavLink) {
    conversationNavLink.setAttribute("aria-controls", "conversationDrawer");
    conversationNavLink.setAttribute("aria-expanded", "false");

    conversationNavLink.addEventListener("click", (event) => {
        event.preventDefault();
        openConversationDrawer();
    });
}

closeConversationDrawerButton?.addEventListener(
    "click",
    closeConversationDrawer
);

conversationDrawerBackdrop?.addEventListener(
    "click",
    closeConversationDrawer
);

document.addEventListener("keydown", (event) => {
    if (!conversationDrawerOpen) return;

    if (event.key === "Escape") {
        closeConversationDrawer();
        return;
    }

    if (event.key === "Tab" && conversationDrawer) {
        const focusable = Array.from(
            conversationDrawer.querySelectorAll(
                'a[href], button:not([disabled]), input:not([disabled]), ' +
                'select:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )
        ).filter((element) =>
            !element.hidden && element.getClientRects().length > 0
        );

        if (!focusable.length) {
            event.preventDefault();
            conversationDrawer.focus();
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (
            event.shiftKey &&
            (document.activeElement === first ||
                !conversationDrawer.contains(document.activeElement))
        ) {
            event.preventDefault();
            last.focus();
        } else if (
            !event.shiftKey &&
            (document.activeElement === last ||
                !conversationDrawer.contains(document.activeElement))
        ) {
            event.preventDefault();
            first.focus();
        }
    }
});

// ==================================================
// CHAT
// ==================================================

async function sendCommand(command) {
    requestInProgress = true;
    syncConversationControls();
    taskStartedAt = Date.now();
    setConversationState("PROCESSING");

    // Capture the visible conversation for this request. If the user changes
    // conversations while a request is in flight, don't paint the reply into
    // the newly selected conversation.
    const requestConversationId = activeConversationId;

    try {
        const data = await apiRequest("/api/chat", {
            method: "POST",
            body: JSON.stringify({ message: command })
        });

        const answer = data.response ?? "LEWIS returned an empty response.";

        if (requestConversationId === activeConversationId) {
            addMessage("LEWIS", answer);
        }

        if (voiceEnabled && answer.trim()) {
            speakResponse(answer);
        }

        return answer;
    } catch (error) {
        console.error("LEWIS API ERROR:", error);

        if (requestConversationId === activeConversationId) {
            addMessage("SYSTEM", "LEWIS Core connection error: " + error.message);
        }

        setConversationState("ERROR");
        return null;
    } finally {
        requestInProgress = false;
        taskStartedAt = null;
        syncConversationControls();
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

if (newConversationButton) {
    newConversationButton.addEventListener("click", createConversationFromHUD);
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

        if (link.getAttribute("href") === "#modelSettings") {
            const modelSettings = document.getElementById("modelSettings");
            if (modelSettings) modelSettings.open = true;
        }
    });
});

// ==================================================
// CONTINUOUS VOICE SESSION
// ==================================================

function syncVoiceSessionControls() {
    const busy = voiceControlRequestInProgress;

    const quickLabel =
        voiceSessionOperation === "starting" ? "STARTING..." :
        voiceSessionOperation === "stopping" ||
        (voiceSessionActive && voiceSessionStopping) ? "STOPPING..." :
        voiceSessionActive ? "STOP VOICE SESSION" :
        "START VOICE SESSION";

    if (quickVoiceSessionButton) {
        const label = quickVoiceSessionButton.querySelector("strong");
        const description = quickVoiceSessionButton.querySelector("small");

        if (label) label.textContent = quickLabel;

        if (description) {
            description.textContent =
                voiceSessionOperation === "starting"
                    ? "Requesting microphone access..."
                    : voiceSessionOperation === "stopping" || voiceSessionStopping
                        ? "Waiting for the voice session to stop"
                        : voiceSessionActive
                            ? "End live microphone input"
                            : "Enable live microphone input";
        }

        quickVoiceSessionButton.disabled =
            busy ||
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
        voiceSessionStartButton.disabled =
            busy || voiceSessionActive || !voiceAvailable || voiceSpeaking;

        voiceSessionStartButton.textContent =
            voiceSessionOperation === "starting"
                ? "STARTING..."
                : "START VOICE SESSION";

        voiceSessionStartButton.setAttribute("aria-busy", String(busy));
    }

    if (voiceSessionStopButton) {
        voiceSessionStopButton.disabled =
            busy || !voiceSessionActive || voiceSessionStopping;

        voiceSessionStopButton.textContent =
            voiceSessionOperation === "stopping" ||
            (voiceSessionActive && voiceSessionStopping)
                ? "STOPPING..."
                : "STOP VOICE SESSION";

        voiceSessionStopButton.setAttribute("aria-busy", String(busy));
    }
}

async function startVoiceSession() {
    if (
        voiceControlRequestInProgress ||
        voiceSessionActive ||
        !voiceAvailable ||
        voiceSpeaking
    ) {
        return;
    }

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
            throw new Error(
                data.message ||
                "The server did not confirm that the voice session started."
            );
        }

        voiceSessionActive = true;
        voiceSessionStopping = false;
        addMessage("SYSTEM", data.message || "Voice session started.");
    } catch (error) {
        console.error("LEWIS VOICE SESSION ERROR:", error);
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
    if (
        voiceControlRequestInProgress ||
        !voiceSessionActive ||
        voiceSessionStopping
    ) {
        return;
    }

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

        voiceSessionStopping =
            data.voice_session_stopping === true ||
            data.activity === "STOPPING";

        addMessage("SYSTEM", data.message || "Voice session stopping.");
    } catch (error) {
        console.error("LEWIS VOICE SESSION STOP ERROR:", error);
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
        console.error("LEWIS VOICE OUTPUT ERROR:", error);
        addMessage("SYSTEM", "Speech output could not start: " + error.message);
    }
}

async function stopSpeaking() {
    try {
        const data = await apiRequest("/api/voice/stop", {
            method: "POST",
            body: JSON.stringify({})
        });

        if (data.message) addMessage("SYSTEM", data.message);
    } catch (error) {
        console.error("LEWIS STOP SPEECH ERROR:", error);
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
            voiceEnabled
                ? "Spoken responses enabled."
                : "Spoken responses disabled."
        );
    } catch (error) {
        console.error("LEWIS VOICE SETTINGS ERROR:", error);

        if (voiceToggle) voiceToggle.checked = voiceEnabled;

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
    if (element) element.textContent = value;
}

function setMeter(id, percentage) {
    const element = document.getElementById(id);
    if (!element) return;

    const numericPercentage = Number(percentage);
    if (!Number.isFinite(numericPercentage)) return;

    const safePercentage = Math.max(0, Math.min(100, numericPercentage));
    element.style.height = `${safePercentage}%`;
}

function syncAIModelControls(data) {
    if (!aiModelSelect || !Array.isArray(data.ai_models)) return;

    const selection = data.ai_selection || {
        provider: data.ai_provider?.toLowerCase(),
        model: data.ai_model
    };

    aiModelSelect.dataset.activeProvider = selection.provider || "";
    aiModelSelect.dataset.activeModel = selection.model || "";

    if (!aiModelSelectionDirty) {
        const currentOptions = Array.from(aiModelSelect.options);
        const modelOptions = data.ai_models.length
            ? data.ai_models
            : [{ provider: "", name: "No configured AI providers", model: "" }];

        const optionsChanged =
            currentOptions.length !== modelOptions.length ||
            modelOptions.some((entry, index) =>
                currentOptions[index]?.value !== entry.provider ||
                currentOptions[index]?.dataset.model !== entry.model
            );

        if (optionsChanged) {
            const options = modelOptions.map((entry) => {
                const option = document.createElement("option");
                option.value = entry.provider;
                option.dataset.model = entry.model;
                option.textContent = entry.model
                    ? `${entry.name} — ${entry.model}`
                    : entry.name;
                option.disabled = !entry.model;
                return option;
            });

            aiModelSelect.replaceChildren(...options);
        }

        const selectedOption = Array.from(aiModelSelect.options).find(
            (option) =>
                option.value === selection.provider &&
                option.dataset.model === selection.model
        );

        if (selectedOption) selectedOption.selected = true;
    }

    aiModelSelect.disabled = data.ai_models.length === 0;

    const selectedOption = aiModelSelect.selectedOptions[0];
    const isDirty =
        aiModelSelectionDirty &&
        selectedOption &&
        (
            selectedOption.value !== selection.provider ||
            selectedOption.dataset.model !== selection.model
        );

    if (applyAIModelButton) {
        applyAIModelButton.disabled = !isDirty || aiModelSelectionSaving;
    }

    if (!aiModelSelectionDirty && aiModelSelectionStatus) {
        aiModelSelectionStatus.textContent = data.ai_models.length
            ? `Active: ${data.ai_provider} — ${data.ai_model}`
            : "Configure provider credentials to select an AI model.";
    }
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
        syncAIModelControls(data);

        // MEMORY
        setText("memoryStatus", data.memory || "UNKNOWN");

        const memoryStatus = String(data.memory || "UNKNOWN").toUpperCase();

        setText(
            "memoryActivityStatus",
            memoryStatus === "ACTIVE"
                ? "Memory available"
                : memoryStatus === "ERROR"
                    ? "Memory status error"
                    : "Memory unavailable"
        );

        if (typeof data.memory_count === "number") {
            setText("memoryCount", data.memory_count);
        } else {
            setText("memoryCount", "Unavailable");
        }

        // CPU and RAM
        if (data.system) {
            const cpu = Number(data.system.cpu);

            if (Number.isFinite(cpu)) {
                setText("cpuValue", `${cpu.toFixed(1)}%`);
                setMeter("cpuMeter", cpu);
            }

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
        const processing =
            requestInProgress ||
            Boolean(data.processing) ||
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

        setText(
            "taskTitle",
            processing ? "Processing conversation" : "No active tasks"
        );
        setText(
            "taskDescription",
            processing ? "Waiting for LEWIS response" : "Waiting for a request"
        );
        setText(
            "taskDuration",
            taskStartedAt
                ? `${Math.max(0, Math.floor((Date.now() - taskStartedAt) / 1000))}s`
                : "—"
        );
        setText("taskCount", processing ? "1 running" : "0 running");
        setText(
            "footerTaskStatus",
            processing ? "Processing conversation..." : "No active task"
        );
        setText("footerTaskPercent", processing ? "In progress" : "—");

        const taskIndicator = document.getElementById("taskIndicator");
        if (taskIndicator) taskIndicator.dataset.active = String(processing);

        const progressTrack = document.querySelector(".progress-track");
        if (progressTrack) progressTrack.dataset.active = String(processing);

        const taskProgressBar = document.getElementById("taskProgressBar");
        if (taskProgressBar) taskProgressBar.style.width = processing ? "" : "0%";

        voiceAvailable = Boolean(data.voice_available);
        voiceOutputAvailable = Boolean(data.voice_output_available);
        voiceSessionActive = Boolean(data.voice_session_active);
        voiceSessionStopping = Boolean(data.voice_session_stopping);
        voiceSpeaking = speaking;

        syncConversationControls();

        setText(
            "voiceStatus",
            !voiceAvailable
                ? "UNAVAILABLE"
                : speaking
                    ? "SPEAKING"
                    : listening || voiceSessionActive
                        ? "LISTENING"
                        : "INACTIVE"
        );

        setText(
            "voiceCardStatus",
            !voiceAvailable
                ? "UNAVAILABLE"
                : speaking
                    ? "SPEAKING"
                    : listening || voiceSessionActive
                        ? "ACTIVE"
                        : "INACTIVE"
        );

        setText(
            "voiceInputState",
            !voiceAvailable
                ? "Unavailable"
                : listening || voiceSessionActive
                    ? "Active"
                    : "Inactive"
        );

        setText(
            "voiceOutputStatus",
            !voiceOutputAvailable
                ? "Unavailable"
                : data.voice_enabled
                    ? speaking
                        ? "Speaking"
                        : "On"
                    : "Off"
        );

        if (voiceCard) {
            voiceCard.dataset.active = String(
                voiceAvailable && (speaking || listening || voiceSessionActive)
            );
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
            addMessage("LEWIS", data.last_response);
        }

        setText("voiceError", data.last_error || "");

        document.body.classList.toggle("lewis-offline", !coreOnline);
    } catch (error) {
        if (requestId !== statusRequestId) return;

        console.error("LEWIS STATUS ERROR:", error);

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
        setConversationState(requestInProgress ? "PROCESSING" : "OFFLINE");

        if (systemStatusItem) {
            systemStatusItem.dataset.status = "offline";
            const statusText = systemStatusItem.querySelector("strong");
            if (statusText) statusText.textContent = "OFFLINE";
        }

        document.body.classList.add("lewis-offline");
    }
}

if (aiModelSelect) {
    aiModelSelect.addEventListener("change", () => {
        const selectedOption = aiModelSelect.selectedOptions[0];

        aiModelSelectionDirty = Boolean(
            selectedOption &&
            (
                selectedOption.value !== aiModelSelect.dataset.activeProvider ||
                selectedOption.dataset.model !== aiModelSelect.dataset.activeModel
            )
        );

        if (aiModelSelectionDirty && aiModelSelectionStatus) {
            aiModelSelectionStatus.textContent = "Selection not applied.";
        }

        syncAIModelControls({
            ai_models: Array.from(aiModelSelect.options).map((option) => ({
                provider: option.value,
                model: option.dataset.model,
                name: option.textContent.split(" — ", 1)[0]
            })),
            ai_selection: {
                provider: aiModelSelect.dataset.activeProvider,
                model: aiModelSelect.dataset.activeModel
            }
        });
    });
}

if (applyAIModelButton) {
    applyAIModelButton.addEventListener("click", async () => {
        const option = aiModelSelect?.selectedOptions[0];

        if (!option || !option.dataset.model || aiModelSelectionSaving) return;

        aiModelSelectionSaving = true;
        applyAIModelButton.disabled = true;

        if (aiModelSelectionStatus) {
            aiModelSelectionStatus.textContent = "Applying selection...";
        }

        try {
            await apiRequest("/api/ai/model", {
                method: "POST",
                body: JSON.stringify({
                    provider: option.value,
                    model: option.dataset.model
                })
            });

            aiModelSelectionDirty = false;

            if (aiModelSelectionStatus) {
                aiModelSelectionStatus.textContent = "Selection applied.";
            }

            await updateHUDStatus();
        } catch (error) {
            console.error("LEWIS AI MODEL SELECTION ERROR:", error);

            if (aiModelSelectionStatus) {
                aiModelSelectionStatus.textContent =
                    `Could not apply selection: ${error.message}`;
            }
        } finally {
            aiModelSelectionSaving = false;
            syncAIModelControlsFromCurrent();
        }
    });
}

function syncAIModelControlsFromCurrent() {
    if (!aiModelSelect || !applyAIModelButton) return;

    const activeOption = Array.from(aiModelSelect.options).find(
        (option) =>
            option.value === aiModelSelect.dataset.activeProvider &&
            option.dataset.model === aiModelSelect.dataset.activeModel
    );

    const selectedOption = aiModelSelect.selectedOptions[0];

    const isDirty = selectedOption && (
        selectedOption.value !== activeOption?.value ||
        selectedOption.dataset.model !== activeOption?.dataset.model
    );

    applyAIModelButton.disabled = !isDirty || aiModelSelectionSaving;
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
        const bothHidden =
            hud.classList.contains("left-panel-collapsed") &&
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
            console.warn("LEWIS SYSTEM LOG: invalid log format.");
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
        console.error("LEWIS LOG ERROR:", error);
    }
}

// ==================================================
// START LIVE SYSTEMS
// ==================================================

syncVoiceSessionControls();
syncConversationControls();

refreshConversationList().catch((error) => {
    console.error("LEWIS CONVERSATION LOAD ERROR:", error);
    addMessage(
        "SYSTEM",
        `Conversation history could not be loaded: ${error.message}`
    );
});

updateHUDStatus();
updateSystemLog();
updateClock();

setInterval(updateHUDStatus, 1000);
setInterval(updateSystemLog, 1000);
setInterval(updateClock, 30_000);

// ==================================================
// INITIAL MESSAGE
// ==================================================

addMessage("SYSTEM", "LEWIS HUD interface initialized.");