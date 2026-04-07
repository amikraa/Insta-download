"""
Configuration settings for Instagram Reel Downloader
All settings are loaded from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration class"""
    
    # API Security
    API_KEY = os.environ.get('INSTAGRAM_API_KEY', '2e7e08e1e7f078ab97b325dc8e3b311b1663edb9eb11d907a553238ead00c8b0')
    
    # CORS Configuration
    ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', '*')  # Set to your frontend domain in production
    
    # Server Settings
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', os.environ.get('FLASK_PORT', 5000)))
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    # Rate Limiting
    RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', 60))  # seconds
    RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', 30))  # requests per window
    
    # Request Settings
    MAX_URL_LENGTH = int(os.environ.get('MAX_URL_LENGTH', 500))
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 30))  # seconds
    
    # yt-dlp Settings
    YTDLP_TIMEOUT = int(os.environ.get('YTDLP_TIMEOUT', 30))
    YTDLP_RETRIES = int(os.environ.get('YTDLP_RETRIES', 3))
    
    # Streaming Settings
    CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', 8192))  # bytes
    STREAM_BUFFER_SIZE = int(os.environ.get('STREAM_BUFFER_SIZE', 65536))  # bytes
    
    # Headers for proxy requests
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',  # Important: prevent compression for streaming
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Instagram-specific headers
    INSTAGRAM_HEADERS = {
        **DEFAULT_HEADERS,
        'Referer': 'https://www.instagram.com/',
        'Origin': 'https://www.instagram.com',
    }
    
    @classmethod
    def validate(cls):
        """Validate configuration and raise errors for critical issues"""
        if cls.API_KEY == 'change-me-in-production':
            print("WARNING: Using default API key. Set INSTAGRAM_API_KEY environment variable for production.")
        return True