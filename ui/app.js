// =========================================================
// ATLAS HUD - APPLICATION LOGIC
// =========================================================


// ---------------------------------------------------------
// ELEMENTS
// ---------------------------------------------------------

const input =
    document.getElementById("commandInput");

const sendButton =
    document.getElementById("sendButton");

const messages =
    document.getElementById("messages");

const hud =
    document.querySelector(".hud");

const expandChatButton =
    document.getElementById("expandChatButton");


// ---------------------------------------------------------
// ADD MESSAGE
// ---------------------------------------------------------

function addMessage(sender, text) {

    const message =
        document.createElement("div");

    message.className =
        "message";


    const senderElement =
        document.createElement("div");

    senderElement.className =
        "message-label";

    senderElement.textContent =
        sender;


    const textElement =
        document.createElement("div");

    textElement.className =
        "message-text";

    textElement.textContent =
        text;


    message.appendChild(
        senderElement
    );

    message.appendChild(
        textElement
    );


    messages.appendChild(
        message
    );


    messages.scrollTop =
        messages.scrollHeight;
}


// ---------------------------------------------------------
// SEND COMMAND TO ATLAS CORE
// ---------------------------------------------------------

async function sendCommand(command) {

    try {

        const response =
            await fetch(
                "/api/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        message: command
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "ATLAS request failed."
            );
        }


        addMessage(
            "ATLAS",
            data.response
        );


    } catch (error) {

        console.error(
            "ATLAS API ERROR:",
            error
        );


        addMessage(
            "SYSTEM",
            "ATLAS Core connection error: " +
            error.message
        );
    }
}


// ---------------------------------------------------------
// HANDLE COMMAND
// ---------------------------------------------------------

function handleCommand() {

    const command =
        input.value.trim();


    if (!command) {
        return;
    }


    addMessage(
        "YOU",
        command
    );


    input.value = "";


    sendButton.disabled =
        true;


    sendCommand(command)
        .finally(() => {

            sendButton.disabled =
                false;

            input.focus();

        });
}


// ---------------------------------------------------------
// SEND BUTTON
// ---------------------------------------------------------

sendButton.addEventListener(
    "click",
    handleCommand
);


// ---------------------------------------------------------
// ENTER KEY
// ---------------------------------------------------------

input.addEventListener(
    "keydown",
    (event) => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            handleCommand();
        }
    }
);


// ---------------------------------------------------------
// CHAT EXPAND / COLLAPSE
// ---------------------------------------------------------

if (expandChatButton) {

    expandChatButton.addEventListener(
        "click",
        () => {

            const expanded =
                hud.classList.toggle(
                    "chat-expanded"
                );


            if (expanded) {

                expandChatButton.textContent =
                    "COLLAPSE";

            } else {

                expandChatButton.textContent =
                    "EXPAND";

            }


            input.focus();

        }
    );
}


// ---------------------------------------------------------
// INITIAL MESSAGE
// ---------------------------------------------------------

addMessage(
    "SYSTEM",
    "ATLAS HUD interface initialized."
);