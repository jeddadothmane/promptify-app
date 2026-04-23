function newChat() {
    conversationId = null;
    localStorage.removeItem('conversation_id');
    document.getElementById('chatMessages').innerHTML = '';
    document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
    addMessage('assistant', 'New conversation started. What would you like to know about your music?');
}

function useExample(text) {
    if (!isAuthenticated) {
        addMessage('assistant', 'Please connect to Spotify first using the button on the left.');
        return;
    }
    const input = document.getElementById('promptInput');
    input.value = text;
    input.focus();
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
}

async function sendMessage() {
    const input   = document.getElementById('promptInput');
    const sendBtn = document.getElementById('sendBtn');
    const message = input.value.trim();
    if (!message) return;

    addMessage('user', message);
    input.value        = '';
    input.style.height = 'auto';

    const loadingId  = addMessage('assistant', 'Thinking…', true);
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<div class="spinner"></div>';

    try {
        const res  = await fetch('/ask', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({
                prompt:               message,
                spotify_access_token: spotifyToken,
                conversation_id:      conversationId
            })
        });
        const data = await res.json();
        removeMessage(loadingId);

        if (res.ok) {
            const isNewConv = data.conversation_id && data.conversation_id !== conversationId;
            if (data.conversation_id) {
                conversationId = data.conversation_id;
                localStorage.setItem('conversation_id', conversationId);
            }
            addMessage('assistant', data.answer);
            if (isNewConv) loadConversations();
        } else {
            addMessage('assistant', `Error: ${data.detail || 'Something went wrong'}`);
        }
    } catch (err) {
        removeMessage(loadingId);
        addMessage('assistant', `Error: ${err.message}`);
    } finally {
        sendBtn.disabled  = false;
        sendBtn.innerHTML = '↑';
    }
}

function addMessage(sender, content, isLoading = false) {
    const feed  = document.getElementById('chatMessages');
    const wrap  = document.createElement('div');
    const msgId = 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    wrap.id        = msgId;
    wrap.className = `message ${sender}${isLoading ? ' loading' : ''}`;

    const label       = document.createElement('div');
    label.className   = 'message-label';
    label.textContent = sender === 'user' ? 'You' : 'Promptify';

    const bubble     = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = isLoading
        ? '<div class="spinner"></div> ' + content
        : content;

    wrap.appendChild(label);
    wrap.appendChild(bubble);
    feed.appendChild(wrap);
    feed.scrollTop = feed.scrollHeight;
    return msgId;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('promptInput');

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    input.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
});
