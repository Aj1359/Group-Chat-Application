let socket = null;
let username = "";


// ========================================
// LOCAL STORAGE
// ========================================

function saveUsername() {

    localStorage.setItem(
        "chatUsername",
        username
    );

}


function getSavedUsername() {

    return localStorage.getItem(
        "chatUsername"
    );

}


// ========================================
// JOIN
// ========================================

function joinChat() {

    username =
        document.getElementById("username")
        .value
        .trim();

    if (username === "") {

        alert("Please enter your username");

        return;
    }

    saveUsername();

    connectToServer();
}


// ========================================
// CONNECT
// ========================================

function connectToServer() {

    const serverIP = "10.50.10.168";

    socket =
        new WebSocket(
            `ws://${serverIP}:8765`
        );


    socket.onopen = function() {

        console.log("Connected");

        socket.send(
            JSON.stringify({
                type: "join",
                username: username
            })
        );

        document.getElementById(
            "login"
        ).style.display = "none";

        document.getElementById(
            "chat"
        ).style.display = "flex";

        document.getElementById(
            "leaveButton"
        ).style.display = "block";

        document.getElementById(
            "connectionStatus"
        ).textContent =
            "● Connected";

        document.getElementById(
            "connectionStatus"
        ).className =
            "connected";

        document.getElementById(
            "message"
        ).focus();
    };


    socket.onmessage = function(event) {

        const data =
            JSON.parse(event.data);


        // HISTORY
        if (data.type === "history") {

            loadHistory(
                data.messages
            );
        }


        // SYSTEM EVENT
        else if (data.type === "system") {

            addSystemMessage(
                data.message
            );
        }


        // NORMAL MESSAGE
        else if (data.type === "message") {

            addChatMessage(
                data.username,
                data.message
            );
        }


        // USERS
        else if (data.type === "users") {

            updateUsers(
                data.users,
                data.count
            );
        }
    };


    socket.onclose = function() {

        document.getElementById(
            "connectionStatus"
        ).textContent =
            "● Disconnected";

        document.getElementById(
            "connectionStatus"
        ).className =
            "disconnected";
    };


    socket.onerror = function(error) {

        console.log(
            "WebSocket error:",
            error
        );
    };
}


// ========================================
// LOAD HISTORY
// ========================================

function loadHistory(messages) {

    const container =
        document.getElementById(
            "messages"
        );

    // Completely rebuild the chat
    container.innerHTML = "";


    messages.forEach(function(data) {

        if (data.type === "message") {

            addChatMessage(
                data.username,
                data.message,
                false
            );
        }

        else if (data.type === "system") {

            addSystemMessage(
                data.message,
                false
            );
        }

    });


    scrollToBottom();
}


// ========================================
// SYSTEM NOTIFICATION
// ========================================

function addSystemMessage(
    message,
    scroll = true
) {

    const messages =
        document.getElementById(
            "messages"
        );

    const element =
        document.createElement(
            "div"
        );

    element.className =
        "system-message";

    element.textContent =
        message;

    messages.appendChild(
        element
    );


    if (scroll) {
        scrollToBottom();
    }
}


// ========================================
// CHAT MESSAGE
// ========================================

function addChatMessage(
    sender,
    message,
    scroll = true
) {

    const messages =
        document.getElementById(
            "messages"
        );

    const element =
        document.createElement(
            "div"
        );


    // Own messages get dark bubble
    // Other messages get light bubble

    if (sender === username) {

        element.className =
            "chat-message own-message";

    }

    else {

        element.className =
            "chat-message other-message";
    }


    const name =
        document.createElement(
            "span"
        );

    name.className =
        "username";

    name.textContent =
        sender;


    const text =
        document.createElement(
            "span"
        );

    text.className =
        "message-text";

    text.textContent =
        message;


    element.appendChild(
        name
    );

    element.appendChild(
        text
    );


    messages.appendChild(
        element
    );


    if (scroll) {
        scrollToBottom();
    }
}


// ========================================
// USERS
// ========================================

function updateUsers(
    users,
    count
) {

    const userCount =
        document.getElementById(
            "userCount"
        );

    const usersList =
        document.getElementById(
            "usersList"
        );


    userCount.textContent =
        count === 1
            ? "1 user online"
            : `${count} users online`;


    usersList.innerHTML = "";


    users.forEach(function(user) {

        const element =
            document.createElement(
                "div"
            );

        element.className =
            "user";


        const dot =
            document.createElement(
                "span"
            );

        dot.className =
            "user-dot";


        const name =
            document.createElement(
                "span"
            );

        name.textContent =
            user;


        element.appendChild(
            dot
        );

        element.appendChild(
            name
        );


        usersList.appendChild(
            element
        );

    });
}


// ========================================
// SEND
// ========================================

function sendMessage() {

    const input =
        document.getElementById(
            "message"
        );

    const message =
        input.value.trim();


    if (
        message === "" ||
        socket === null ||
        socket.readyState !== WebSocket.OPEN
    ) {

        return;
    }


    socket.send(
        JSON.stringify({
            type: "message",
            message: message
        })
    );


    input.value = "";

    input.focus();
}


// ========================================
// LEAVE
// ========================================

function leaveChat() {

    if (
        socket &&
        socket.readyState === WebSocket.OPEN
    ) {

        socket.send(
            JSON.stringify({
                type: "leave"
            })
        );

        socket.close();
    }


    localStorage.removeItem(
        "chatUsername"
    );


    username = "";

    socket = null;


    document.getElementById(
        "messages"
    ).innerHTML = "";


    document.getElementById(
        "chat"
    ).style.display = "none";


    document.getElementById(
        "login"
    ).style.display = "flex";


    document.getElementById(
        "leaveButton"
    ).style.display = "none";


    document.getElementById(
        "connectionStatus"
    ).textContent =
        "● Disconnected";


    document.getElementById(
        "connectionStatus"
    ).className =
        "disconnected";


    document.getElementById(
        "username"
    ).value = "";
}


// ========================================
// ENTER KEY
// ========================================

function handleKey(event) {

    if (event.key === "Enter") {

        sendMessage();
    }
}


// ========================================
// AUTO SCROLL
// ========================================

function scrollToBottom() {

    const messages =
        document.getElementById(
            "messages"
        );

    messages.scrollTop =
        messages.scrollHeight;
}


// ========================================
// PAGE LOAD
// ========================================

window.onload = function() {

    const savedUsername =
        getSavedUsername();


    if (savedUsername) {

        username =
            savedUsername;

        connectToServer();
    }
};
