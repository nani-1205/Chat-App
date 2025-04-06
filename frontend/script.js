document.addEventListener('DOMContentLoaded', () => {
    const usernameInput = document.getElementById('username');
    const setUsernameBtn = document.getElementById('setUsernameBtn');
    const usernameSection = document.getElementById('username-section');
    const chatSection = document.getElementById('chat-section');
    const chatLog = document.getElementById('chat-log');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    let username = '';
    let websocket;

    setUsernameBtn.addEventListener('click', () => {
        username = usernameInput.value.trim();
        if (username) {
            usernameSection.style.display = 'none';
            chatSection.style.display = 'block';
            startWebSocket(); // Start WebSocket connection after setting username
        } else {
            alert('Please enter a username.');
        }
    });

    function startWebSocket() {
        websocket = new WebSocket('ws://' + window.location.hostname + ':5000/ws'); // Connect to WebSocket endpoint

        websocket.onopen = () => {
            console.log('WebSocket connection opened');
        };

        websocket.onmessage = (event) => {
            const messageData = JSON.parse(event.data);
            if (messageData.type === 'message') {
                displayMessage(messageData.username, messageData.content, messageData.timestamp);
            }
        };

        websocket.onclose = () => {
            console.log('WebSocket connection closed');
        };

        websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    sendButton.addEventListener('click', sendMessage);

    messageInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });

    function sendMessage() {
        const messageText = messageInput.value.trim();
        if (messageText && websocket.readyState === WebSocket.OPEN) {
            const messagePayload = {
                type: 'message',
                username: username,
                content: messageText
            };
            websocket.send(JSON.stringify(messagePayload));
            messageInput.value = ''; // Clear input field after sending
        }
    }

    function displayMessage(senderUsername, messageContent, timestamp) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');

        const usernameSpan = document.createElement('span');
        usernameSpan.classList.add('username');
        usernameSpan.textContent = senderUsername + ': ';
        messageDiv.appendChild(usernameSpan);

        const contentSpan = document.createElement('span');
        contentSpan.textContent = messageContent;
        messageDiv.appendChild(contentSpan);

        chatLog.appendChild(messageDiv);
        chatLog.scrollTop = chatLog.scrollHeight; // Scroll to bottom for new messages
    }
});