const API_URL = '/api';
let conversationId = 'chat_' + Date.now();

const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const resetButton = document.getElementById('resetButton');

// Initialize - load random intro
loadIntro();

// Initialize
userInput.focus();

async function loadIntro() {
    try {
        const response = await fetch(`${API_URL}/intro`);
        const data = await response.json();
        if (data.intro) {
            addMessage(data.intro, 'bot');
        } else {
            // Fallback
            addMessage("Oh great, another human. What do you want?", 'bot');
        }
    } catch (error) {
        // Fallback if API fails
        addMessage("Oh great, another human. What do you want?", 'bot');
        console.error('Error loading intro:', error);
    }
}

// Send message on button click
sendButton.addEventListener('click', sendMessage);

// Send message on Enter key
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Reset conversation
resetButton.addEventListener('click', resetConversation);

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');
    userInput.value = '';

    // Show typing indicator
    const typingId = showTypingIndicator();

    try {
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId
            })
        });

        const data = await response.json();
        
        // Remove typing indicator
        removeTypingIndicator(typingId);

        // Add bot response
        if (data.response) {
            addMessage(data.response, 'bot');
        } else {
            addMessage("I'm speechless. Literally. There was an error.", 'bot');
        }
    } catch (error) {
        removeTypingIndicator(typingId);
        addMessage("Oops, I broke. How ironic. Check if the server is running.", 'bot');
        console.error('Error:', error);
    }
}

function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const textNode = document.createElement('p');
    textNode.textContent = text;
    contentDiv.appendChild(textNode);

    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    messageDiv.appendChild(contentDiv);
    messageDiv.appendChild(timeDiv);

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message';
    typingDiv.id = 'typing-indicator';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'typing-indicator';
    contentDiv.innerHTML = '<span></span><span></span><span></span>';

    typingDiv.appendChild(contentDiv);
    chatMessages.appendChild(typingDiv);
    scrollToBottom();

    return 'typing-indicator';
}

function removeTypingIndicator(id) {
    const indicator = document.getElementById(id);
    if (indicator) {
        indicator.remove();
    }
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function resetConversation() {
    try {
        await fetch(`${API_URL}/reset`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: conversationId
            })
        });

        // Clear chat messages
        chatMessages.innerHTML = '';
        
        // Generate new conversation ID
        conversationId = 'chat_' + Date.now();

        // Load random intro message
        loadIntro();
    } catch (error) {
        console.error('Error resetting:', error);
    }
}

// Auto-scroll on new messages
const observer = new MutationObserver(scrollToBottom);
observer.observe(chatMessages, { childList: true });

