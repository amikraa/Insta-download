# Instagram Reel Downloader

A production-ready Flask backend for downloading Instagram Reels with no file storage, API protection, and rate limiting.

## Features

- **No Disk Storage** - All videos are streamed directly to the client
- **API Key Protection** - Secure your API with key-based authentication
- **Rate Limiting** - Prevent abuse with configurable rate limits
- **Video + Audio** - Extract videos with audio using yt-dlp
- **MP3 Extraction** - Separate endpoint for audio-only downloads
- **Production Ready** - Optimized for Render deployment
- **Minimal Memory** - Chunked streaming for low memory usage
- **Clean API** - JSON responses for easy frontend integration

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` and set your API key:

```env
INSTAGRAM_API_KEY=your-secret-api-key-here
```

### 3. Run the Application

```bash
python app.py
```

The application will start on `http://localhost:5000`

## API Endpoints

### `POST /api/download`

Extract video information from an Instagram URL.

**Headers:**
- `X-API-Key`: Your API key

**Body:**
```json
{
  "url": "https://www.instagram.com/reel/..."
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "videoUrl": "https://...",
    "audioUrl": "https://...",
    "thumbnail": "https://...",
    "title": "Video title",
    "duration": 45,
    "author": "@username",
    "shortcode": "abc123"
  },
  "message": "Video extracted successfully"
}
```

### `POST /api/download-audio`

Extract audio-only from an Instagram URL.

**Headers:**
- `X-API-Key`: Your API key

**Body:**
```json
{
  "url": "https://www.instagram.com/reel/..."
}
```

### `GET /api/stream`

Stream video or audio content to the client.

**Query Parameters:**
- `url`: The media URL to stream
- `filename`: Download filename
- `type`: Content type (video/mp4 or audio/mpeg)
- `api_key`: Your API key (or use X-API-Key header)

**Example:**
```
/api/stream?url=https://...&filename=video.mp4&type=video/mp4&api_key=your-key
```

### `GET /api/health`

Health check endpoint (no authentication required).

## Frontend Integration

Include the API key in your requests:

```javascript
const API_KEY = 'your-api-key-here';

// Download video info
const response = await fetch('/api/download', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
  },
  body: JSON.stringify({ url: instagramUrl })
});

const data = await response.json();

// Stream video
const streamUrl = `/api/stream?url=${encodeURIComponent(data.data.videoUrl)}&filename=video.mp4&type=video/mp4&api_key=${API_KEY}`;
window.open(streamUrl, '_blank');
```

## Deployment to Render

1. Push your code to GitHub
2. Create a new Web Service on Render
3. Connect your repository
4. Set the following environment variables:
   - `INSTAGRAM_API_KEY` - Your secret API key
   - `PORT` - Render will set this automatically
5. Deploy!

Render will automatically detect the Python application and use `gunicorn` as the WSGI server.

### Render Build Command
```
pip install -r requirements.txt
```

### Render Start Command
```
gunicorn app:app
```

## Configuration

All configuration is done through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `INSTAGRAM_API_KEY` | `change-me-in-production` | API key for authentication |
| `FLASK_HOST` | `0.0.0.0` | Server host |
| `FLASK_PORT` | `5000` | Server port |
| `FLASK_DEBUG` | `false` | Debug mode |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window (seconds) |
| `RATE_LIMIT_MAX` | `30` | Max requests per window |
| `MAX_URL_LENGTH` | `500` | Maximum URL length |
| `REQUEST_TIMEOUT` | `30` | Request timeout (seconds) |
| `YTDLP_TIMEOUT` | `30` | yt-dlp timeout (seconds) |
| `YTDLP_RETRIES` | `3` | yt-dlp retries |
| `CHUNK_SIZE` | `8192` | Stream chunk size (bytes) |

## Security

### API Key Protection
All API endpoints (except `/api/health`) require a valid API key. Generate a strong random key:

```bash
openssl rand -hex 32
```

### Rate Limiting
Default: 30 requests per minute per IP address. Configure via environment variables.

### Input Validation
- URL format validation
- URL length limits
- Proper error handling without information leakage

## Important Notes

### Cookies
The application uses `cookies.txt` for Instagram authentication. Generate this file using yt-dlp:

```bash
yt-dlp --cookies-from-browser chrome:~/.config/google-chrome/Default --cookies cookies.txt "https://instagram.com"
```

Or manually create a Netscape-format cookies file.

### Instagram Rate Limits
Instagram may rate limit or block requests. Using authenticated cookies helps mitigate this.

### Legal Considerations
- Only download content you have permission to download
- Respect creators' intellectual property rights
- This tool is for personal use only

## Project Structure

```
Reel-downloder/
├── app.py              # Main Flask application
├── config.py           # Configuration settings
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (do not commit!)
├── .env.example       # Environment template
├── .gitignore         # Git ignore rules
├── index.html         # Frontend (optional)
└── cookies.txt        # Instagram cookies (do not commit!)
```

## License

MIT License - Use responsibly and respect content creators' rights.

## Disclaimer

This tool is for educational purposes. Always respect Instagram's Terms of Service and content creators' intellectual property rights. Do not use this tool for unauthorized downloading or redistribution of copyrighted content.