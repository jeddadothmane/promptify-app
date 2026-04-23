let spotifyToken    = null;
let isAuthenticated = false;

function checkAuthStatus() {
    const savedToken  = localStorage.getItem('spotify_token');
    const tokenExpiry = localStorage.getItem('spotify_token_expiry');

    if (savedToken && tokenExpiry && new Date() < new Date(tokenExpiry)) {
        spotifyToken    = savedToken;
        isAuthenticated = true;
        updateAuthUI(true);
        loadConversations();
    } else {
        localStorage.removeItem('spotify_token');
        localStorage.removeItem('spotify_token_expiry');
        updateAuthUI(false);
    }
}

function updateAuthUI(authenticated) {
    const dot        = document.getElementById('statusDot');
    const headerDot  = document.getElementById('chatHeaderDot');
    const authStatus = document.getElementById('authStatus');
    const loginBtn   = document.getElementById('loginBtn');
    const logoutBtn  = document.getElementById('logoutBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const badge      = document.getElementById('connectedBadge');
    const input      = document.getElementById('promptInput');
    const sendBtn    = document.getElementById('sendBtn');
    const headerSub  = document.getElementById('chatHeaderSub');

    if (authenticated) {
        dot.classList.add('connected');
        headerDot.classList.add('connected');
        authStatus.textContent   = 'Connected';
        loginBtn.textContent     = 'Reconnect';
        logoutBtn.style.display  = 'block';
        newChatBtn.style.display = 'block';
        badge.style.display      = 'block';
        input.disabled           = false;
        sendBtn.disabled         = false;
        headerSub.textContent    = 'Spotify connected';
    } else {
        dot.classList.remove('connected');
        headerDot.classList.remove('connected');
        authStatus.textContent   = 'Not connected';
        loginBtn.textContent     = 'Login with Spotify';
        logoutBtn.style.display  = 'none';
        newChatBtn.style.display = 'none';
        badge.style.display      = 'none';
        input.disabled           = true;
        sendBtn.disabled         = true;
        headerSub.textContent    = 'Connect Spotify to get started';
    }
}

function loginToSpotify() {
    if (isAuthenticated) {
        addMessage('assistant', 'You\'re already connected to Spotify! Go ahead and ask me anything. 🎵');
        return;
    }
    window.location.href = '/login';
}

function logoutFromSpotify() {
    localStorage.removeItem('spotify_token');
    localStorage.removeItem('spotify_token_expiry');
    localStorage.removeItem('spotify_refresh_token');
    localStorage.removeItem('spotify_user_id');
    localStorage.removeItem('conversation_id');
    spotifyToken    = null;
    isAuthenticated = false;
    conversationId  = null;
    updateAuthUI(false);
    document.getElementById('chatMessages').innerHTML = '';
    addMessage('assistant', 'You\'ve been disconnected. Login again whenever you\'re ready.');
}

document.addEventListener('DOMContentLoaded', checkAuthStatus);
