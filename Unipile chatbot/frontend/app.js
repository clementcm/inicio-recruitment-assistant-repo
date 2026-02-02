
const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const sessionList = document.getElementById('session-list');
const newChatBtn = document.getElementById('new-chat-btn');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings');


let messages = [];
let currentSessionId = null;
let settings = {};

// Load settings from localStorage
function loadSettings() {
    const saved = localStorage.getItem('chatSettings');
    if (saved) {
        settings = JSON.parse(saved);
    }
}

// Save settings to localStorage
function saveSettings() {
    localStorage.setItem('chatSettings', JSON.stringify(settings));
}


// Settings modal UI handled in shared.js

async function switchSession(id) {
    try {
        currentSessionId = id;
        const res = await authFetch(`/api/sessions/${id}`);
        if (!res.ok) return;
        const history = await res.json();

        // Update client state
        messages = history;

        // Clear and re-render history
        chatHistory.innerHTML = '';
        messages.forEach(m => appendMessage(m.role, m.content));

        loadSessions();
    } catch (e) { console.error("Switch failed", e); }
}

async function loadSessions() {
    try {
        const res = await authFetch('/api/sessions');
        const sessions = await res.json();
        if (sessionList) {
            sessionList.innerHTML = '';
            sessions.reverse().forEach(s => {
                const item = document.createElement('div');
                item.className = `session-item ${s.id === currentSessionId ? 'active' : ''}`;
                item.textContent = s.title;
                item.title = s.title;
                item.onclick = () => switchSession(s.id);
                sessionList.appendChild(item);
            });
        }
    } catch (e) { console.error("Failed to load sessions", e); }
}

if (newChatBtn) {
    newChatBtn.onclick = () => {
        currentSessionId = null;
        messages = [];
        chatHistory.innerHTML = `
            <div class="message system">
                <div class="content">
                    Hello! I'm your Inicio Recruiter Assistant. I can help you find and rank top talent based on your specific requirements.
                    <br><br>
                    To get started, simply tell me about the role you're hiring for. You can include:
                    <ul>
                        <li><strong>Job Title</strong> (e.g., Senior Java Developer)</li>
                        <li><strong>Key Skills & Expertise</strong> (e.g., Python, AWS, Project Management)</li>
                        <li><strong>Preferred Location</strong> (e.g., New York, Remote, Europe)</li>
                    </ul>
                </div>
            </div>
        `;
        loadSessions();
    };
}

function appendMessage(role, text, isTool = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';
    // Use marked.js for rich rendering
    contentDiv.innerHTML = marked.parse(text);

    msgDiv.appendChild(contentDiv);
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // Add User Message
    appendMessage('user', text);
    userInput.value = '';
    userInput.disabled = true;
    sendBtn.disabled = true;

    if (!currentSessionId) {
        currentSessionId = crypto.randomUUID();
    }

    messages.push({ role: 'user', content: text });

    try {
        showThinking(); // Show indicator before request

        const response = await authFetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: messages,
                session_id: currentSessionId,
                verify_json: document.getElementById('verify-json-toggle').checked
            })
        });

        if (!response.ok) throw new Error('Network error');

        removeThinking(); // Remove indicator when response starts

        // Create Assistant Message container
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant';
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        msgDiv.appendChild(contentDiv);
        chatHistory.appendChild(msgDiv);

        // Force initial render
        chatHistory.scrollTop = chatHistory.scrollHeight;

        // Reading the stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantText = "";
        let lastUpdateTime = 0;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            console.log("DEBUG: Received chunk:", chunk);
            assistantText += chunk;

            // Throttle updates to every 50ms for smoother rendering
            const now = Date.now();
            if (now - lastUpdateTime > 50 || done) {
                lastUpdateTime = now;
                console.log("DEBUG: Updating contentDiv, current text length:", assistantText.length);
                // Update content with markdown-rendered text
                contentDiv.innerHTML = marked.parse(assistantText);

                // Force reflow and scroll
                void contentDiv.offsetHeight; // Force reflow
                chatHistory.scrollTop = chatHistory.scrollHeight;
            }
        }

        // Final update to ensure everything is rendered
        contentDiv.innerHTML = marked.parse(assistantText);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        // Save to history
        messages.push({ role: 'assistant', content: assistantText });

        // Update sessions list
        await loadSessions();

    } catch (error) {
        console.error('Error:', error);
        removeThinking(); // Ensure indicator is removed on error
        appendMessage('system', 'Error: Connection lost.');
    } finally {
        userInput.disabled = false;
        sendBtn.disabled = false;
        userInput.focus();
    }
}

let thinkingDiv = null;

function showThinking() {
    if (thinkingDiv) return;

    thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message assistant';
    thinkingDiv.innerHTML = `
        <div class="content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    chatHistory.appendChild(thinkingDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function removeThinking() {
    if (thinkingDiv) {
        thinkingDiv.remove();
        thinkingDiv = null;
    }
}

if (sendBtn) {
    sendBtn.addEventListener('click', sendMessage);
}
if (userInput) {
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
}

// Initial load
loadSettings();
loadSessions();
