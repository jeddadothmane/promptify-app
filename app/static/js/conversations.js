let conversationId = localStorage.getItem('conversation_id') || null;

async function loadConversations() {
    const userId = localStorage.getItem('spotify_user_id');
    if (!userId) return;

    try {
        const res  = await fetch(`/conversations/${encodeURIComponent(userId)}`);
        if (!res.ok) return;
        const list = await res.json();
        renderConversations(list);
    } catch (_) {}
}

function renderConversations(list) {
    const section   = document.getElementById('historySection');
    const divider   = document.getElementById('historyDivider');
    const container = document.getElementById('conversationList');
    container.innerHTML = '';

    if (!list || list.length === 0) {
        section.style.display = 'none';
        divider.style.display = 'none';
        return;
    }

    section.style.display = 'flex';
    divider.style.display = 'block';

    list.forEach(conv => {
        const item = document.createElement('div');
        item.className  = 'conv-item' + (conv.id === conversationId ? ' active' : '');
        item.dataset.id = conv.id;

        const title = document.createElement('span');
        title.className   = 'conv-title';
        title.textContent = conv.title || 'Untitled';
        title.title       = conv.title || 'Untitled';

        const del = document.createElement('button');
        del.className   = 'conv-delete';
        del.textContent = '✕';
        del.title       = 'Delete';
        del.onclick     = async (e) => {
            e.stopPropagation();
            await deleteConversation(conv.id);
        };

        item.onclick = () => switchConversation(conv.id);
        item.appendChild(title);
        item.appendChild(del);
        container.appendChild(item);
    });
}

async function switchConversation(id) {
    conversationId = id;
    localStorage.setItem('conversation_id', id);

    document.querySelectorAll('.conv-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === id);
    });

    document.getElementById('chatMessages').innerHTML = '';

    try {
        const res  = await fetch(`/conversations/${encodeURIComponent(id)}/messages`);
        if (!res.ok) return;
        const msgs = await res.json();
        msgs.forEach(m => addMessage(m.role === 'user' ? 'user' : 'assistant', m.content));
    } catch (_) {}
}

async function deleteConversation(id) {
    const userId = localStorage.getItem('spotify_user_id');
    if (!userId) return;

    try {
        await fetch(
            `/conversations/${encodeURIComponent(id)}?user_id=${encodeURIComponent(userId)}`,
            { method: 'DELETE' }
        );
    } catch (_) {}

    if (conversationId === id) {
        conversationId = null;
        localStorage.removeItem('conversation_id');
        document.getElementById('chatMessages').innerHTML = '';
        addMessage('assistant', 'Conversation deleted. Start a new one anytime.');
    }

    await loadConversations();
}
