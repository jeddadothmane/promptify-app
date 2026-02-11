# 🎵 Promptify App

**Promptify** is an intelligent Spotify assistant powered by OpenAI that allows you to interact with your Spotify account using natural language. Ask questions, get insights about your music preferences, and even create custom playlists—all through conversational AI.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-orange.svg)
![Spotify](https://img.shields.io/badge/Spotify-API-1DB954.svg)

---

## 🌟 Features

- 🤖 **AI-Powered Conversations**: Natural language interaction with your Spotify data
- 🎨 **Top Artists & Tracks**: Discover your most listened-to artists and songs
- 🕒 **Recently Played**: See what you've been listening to recently
- ▶️ **Current Playback**: Check what's playing right now
- 📋 **Playlist Management**: View your playlists and create new ones with AI
- 🔍 **Smart Search**: Find tracks using natural language descriptions
- 🎭 **Intelligent Playlist Creation**: Create custom playlists from text prompts (e.g., "Make me a workout playlist with 20 energetic songs")

---

## 📋 Prerequisites

Before you begin, ensure you have the following:

- **Python 3.8+** installed
- **OpenAI API Key** - Get one from [OpenAI Platform](https://platform.openai.com/)
- **Spotify Developer Account** - Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/jeddadothmane/promptify-app.git
cd promptify-app
```

### 2. Set Up Virtual Environment

```bash
# Create virtual environment (if not exists)
python -m venv venv

# Activate it
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1

# On Windows CMD:
.\venv\Scripts\activate.bat

# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r app/requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root directory:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Spotify Configuration
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback

# Optional: Model Configuration
OPENAI_MODEL=gpt-4o-mini
```

#### Getting Your API Keys:

**OpenAI:**
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to "API Keys" section
4. Click "Create new secret key"

**Spotify:**
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create an App"
4. Fill in the app name and description
5. Copy your `Client ID` and `Client Secret`
6. In app settings, add `http://localhost:8000/callback` to **Redirect URIs**

### 5. Launch the Application

```bash
uvicorn app.controller.app:app --reload --port 8000
```

The application will be available at: **http://localhost:8000**

---

## 🎮 How to Use

### Step 1: Authenticate with Spotify

1. Open your browser and navigate to: **http://localhost:8000/login**
2. You'll be redirected to Spotify's authorization page
3. Click "Agree" to authorize the application
4. You'll be redirected back with your access token
5. **Save your access token** - you'll need it for API requests

### Step 2: Interact with the App

#### Option A: Web Interface

Visit **http://localhost:8000** to use the web interface (if available).

#### Option B: API Endpoint

Make a POST request to `/ask`:

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What are my top 5 artists?",
    "spotify_access_token": "YOUR_ACCESS_TOKEN_HERE",
    "model": "gpt-4o-mini",
    "temperature": 0.7
  }'
```

### Example Questions You Can Ask:

- 🎤 **"What are my top 5 artists?"**
- 🎵 **"Show me my most played tracks"**
- 🕒 **"What did I listen to recently?"**
- ▶️ **"What am I listening to right now?"**
- 📋 **"Show me my playlists"**
- 🔍 **"Search for songs by Drake"**
- 🎭 **"Create a workout playlist with 15 high-energy songs"**
- 🌙 **"Make me a relaxing evening playlist with jazz and chill music"**

---

## 📚 API Documentation

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Home page / Web UI |
| `POST` | `/ask` | Submit a question with Spotify context |
| `GET` | `/login` | Initiate Spotify OAuth authentication |
| `GET` | `/callback` | OAuth callback (handles Spotify redirect) |
| `GET` | `/spotify/tools` | List available Spotify tools |
| `GET` | `/docs` | Interactive API documentation (Swagger UI) |
| `GET` | `/docs-page` | Documentation page |

### Request Schema (`/ask` endpoint)

```json
{
  "prompt": "string (required)",
  "spotify_access_token": "string (optional)",
  "model": "string (default: gpt-4o-mini)",
  "temperature": 0.7,
  "system": "string (optional)"
}
```

### Response Schema

```json
{
  "answer": "string"
}
```

---

## 🛠️ Available Spotify Tools

The app automatically determines which Spotify tool to use based on your question:

1. **get_top_artists** - Get your most listened-to artists
2. **get_top_tracks** - Get your most played tracks
3. **get_recently_played** - See your recently played songs
4. **get_current_playback** - Check current playback status
5. **search_tracks** - Search for songs by query
6. **get_user_playlists** - List your Spotify playlists
7. **create_playlist_from_prompt** - AI-powered playlist creation

---

## 📁 Project Structure

```
promptify-app/
├── app/
│   ├── __init__.py
│   ├── requirements.txt           # Python dependencies
│   ├── clients/                   # API client modules
│   │   ├── __init__.py
│   │   ├── open_ai_client.py     # OpenAI integration
│   │   ├── spotify_mcp.py        # Spotify API wrapper
│   │   └── resources/
│   │       └── spotify_tools.json # Tool definitions
│   ├── controller/                # Application logic
│   │   ├── __init__.py
│   │   ├── app.py                # FastAPI application
│   │   ├── schemas.py            # Pydantic models
│   │   └── utils.py              # Helper functions
│   └── view/                      # HTML templates
│       ├── index.html
│       ├── success.html
│       ├── error.html
│       └── ...
├── venv/                          # Virtual environment
├── .env                           # Environment variables (create this)
├── .gitignore
└── README.md
```

---

## 🔧 Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | - | Your OpenAI API key |
| `SPOTIFY_CLIENT_ID` | ✅ Yes | - | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | ✅ Yes | - | Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | ❌ No | `http://127.0.0.1:8000/callback` | OAuth redirect URI |
| `OPENAI_MODEL` | ❌ No | `gpt-4o-mini` | OpenAI model to use |

### Spotify Scopes

The app requests the following Spotify permissions:
- `user-top-read` - Access top artists and tracks
- `user-read-recently-played` - Read recently played tracks
- `user-read-playback-state` - Read playback state
- `user-modify-playback-state` - Control playback
- `playlist-read-private` - Access private playlists
- `playlist-modify-public` - Modify public playlists
- `playlist-modify-private` - Modify private playlists

---

## 🐛 Troubleshooting

### Issue: "jinja2 must be installed to use Jinja2Templates"

**Solution:**
```bash
pip install jinja2
```

### Issue: Spotify Authentication Fails

**Causes & Solutions:**
- ❌ **Redirect URI mismatch**: Ensure `SPOTIFY_REDIRECT_URI` in `.env` matches exactly what's configured in your Spotify Developer Dashboard
- ❌ **Invalid credentials**: Double-check your `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`

### Issue: OpenAI API Error

**Causes & Solutions:**
- ❌ **Invalid API key**: Verify your `OPENAI_API_KEY` is correct
- ❌ **Insufficient credits**: Check your OpenAI account balance
- ❌ **Rate limit exceeded**: Wait a moment and try again

### Issue: Access Token Expired

**Solution:**  
Spotify access tokens expire after a period. Simply visit `/login` again to get a new token.

---

## 🚦 Development

### Running in Development Mode

```bash
uvicorn app.controller.app:app --reload --port 8000
```

The `--reload` flag enables auto-reload on code changes.

### Accessing Interactive API Docs

FastAPI automatically generates interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

---

## 📝 Notes

- 🔐 **Security**: Never commit your `.env` file or expose your API keys
- ⏰ **Token Expiration**: Spotify access tokens expire after ~1 hour
- 🧠 **AI Intelligence**: The app uses OpenAI to intelligently determine which Spotify tool to use based on your natural language input
- 🎭 **Playlist Creation**: The AI can create playlists by understanding your description and finding matching tracks

---

## 📄 License

This project is for educational and personal use.

---

## 📞 Support

If you encounter any issues or have questions, please check the **Troubleshooting** section above or open an issue on GitHub.

---

**Enjoy your AI-powered Spotify experience! 🎵✨**
