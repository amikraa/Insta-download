"""
Instagram Reel Downloader - Flask Backend
Production-ready streaming downloader with no disk storage.

Features:
- Pure streaming (no file storage)
- API key protection
- Rate limiting
- Video + Audio streaming
- MP3 extraction
- Render deployment ready
"""

import os
import re
import time
import logging
from functools import wraps
from collections import defaultdict
from threading import Lock

from flask import Flask, request, jsonify, Response
import yt_dlp
import requests

from config import Config

# ═══════════════════════════════════════════════════════════════
# APPLICATION SETUP
# ═══════════════════════════════════════════════════════════════

app = Flask(__name__, static_folder='.')

# Configure logging
logging.basicConfig(
    level=logging.INFO if not Config.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate configuration
Config.validate()

# ═══════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, max_requests=30, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = Lock()
    
    def is_allowed(self, client_ip):
        """Check if request is allowed for the given IP"""
        with self.lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Clean old entries
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if req_time > window_start
            ]
            
            # Check limit
            if len(self.requests[client_ip]) >= self.max_requests:
                return False
            
            # Record request
            self.requests[client_ip].append(now)
            return True
    
    def get_retry_after(self, client_ip):
        """Get seconds until the client can retry"""
        with self.lock:
            if client_ip not in self.requests:
                return 0
            oldest = min(self.requests[client_ip])
            return max(0, int(oldest + self.window_seconds - time.time())) + 1


# Initialize rate limiter
rate_limiter = RateLimiter(
    max_requests=Config.RATE_LIMIT_MAX,
    window_seconds=Config.RATE_LIMIT_WINDOW
)

# ═══════════════════════════════════════════════════════════════
# MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

def require_api_key(f):
    """Decorator to require API key in request headers"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key required',
                'message': 'Please provide X-API-Key header or api_key parameter'
            }), 401
        
        if api_key != Config.API_KEY:
            logger.warning(f"Invalid API key attempt from {request.remote_addr}")
            return jsonify({
                'success': False,
                'error': 'Invalid API key'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(f):
    """Decorator to apply rate limiting"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        
        if not rate_limiter.is_allowed(client_ip):
            retry_after = rate_limiter.get_retry_after(client_ip)
            logger.warning(f"Rate limit exceeded for {client_ip}")
            
            response = jsonify({
                'success': False,
                'error': 'Rate limit exceeded',
                'message': f'Too many requests. Try again in {retry_after} seconds.'
            })
            response.headers['Retry-After'] = str(retry_after)
            return response, 429
        
        return f(*args, **kwargs)
    return decorated_function


# ═══════════════════════════════════════════════════════════════
# CORS MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

@app.after_request
def add_cors_headers(response):
    """Add CORS headers to all responses - allows any origin (temporary for dev/testing)"""
    origin = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Origin'] = origin if origin else '*'
    response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = '3600'
    return response


# ═══════════════════════════════════════════════════════════════
# YT-DLP EXTRACTOR
# ═══════════════════════════════════════════════════════════════

def extract_video_info(url, extract_audio=False):
    """
    Extract video/audio information from Instagram URL using yt-dlp.
    Returns direct URLs for streaming without downloading to disk.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'no_check_certificate': True,
        'extract_flat': False,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'socket_timeout': Config.YTDLP_TIMEOUT,
        'retries': Config.YTDLP_RETRIES,
    }
    
    if extract_audio:
        # Audio-only extraction
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [],
        })
    else:
        # Video with audio - prefer combined format
        ydl_opts.update({
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
        })
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None, "No video information found"
            
            # Handle playlist/carousel - get first video
            if 'entries' in info and info['entries']:
                info = next((e for e in info['entries'] if e), info)
            
            return info, None
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if 'Private' in error_msg or 'private' in error_msg:
            return None, "Cannot download private content"
        if 'Blocked' in error_msg or 'unavailable' in error_msg:
            return None, "Video is unavailable or blocked"
        return None, f"Extraction error: {error_msg}"
    except Exception as e:
        logger.error(f"yt-dlp error: {str(e)}")
        return None, f"Unexpected error: {str(e)}"


def get_streaming_url(info, prefer_audio=False):
    """
    Extract the best streaming URL from yt-dlp info dict.
    Returns tuple of (url, format_info) or (None, error).
    """
    if not info:
        return None, "No video information available"
    
    # For audio extraction
    if prefer_audio:
        if 'url' in info:
            return info['url'], {'ext': info.get('ext', 'mp3'), 'format': info.get('format', 'bestaudio')}
        # Look for audio formats
        formats = info.get('formats', [])
        audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('url')]
        if audio_formats:
            best = sorted(audio_formats, key=lambda x: x.get('abr', 0) or 0, reverse=True)[0]
            return best['url'], {'ext': best.get('ext', 'mp3'), 'format': best.get('format', 'audio')}
    
    # For video - prefer combined video+audio
    if 'url' in info:
        # Direct URL available
        has_audio = info.get('acodec') != 'none' if info.get('acodec') else True
        return info['url'], {
            'ext': info.get('ext', 'mp4'),
            'format': info.get('format', 'best'),
            'has_audio': has_audio,
            'resolution': info.get('resolution', info.get('height', 'unknown'))
        }
    
    # Look for combined formats first
    formats = info.get('formats', [])
    
    # Find best combined video+audio format
    combined = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url')]
    if combined:
        best = sorted(combined, key=lambda x: x.get('height', 0) or 0, reverse=True)[0]
        return best['url'], {
            'ext': best.get('ext', 'mp4'),
            'format': best.get('format', 'combined'),
            'has_audio': True,
            'resolution': f"{best.get('height', '?')}p"
        }
    
    # Fallback: video-only format (audio might be separate)
    video_only = [f for f in formats if f.get('vcodec') != 'none' and f.get('url')]
    if video_only:
        best = sorted(video_only, key=lambda x: x.get('height', 0) or 0, reverse=True)[0]
        return best['url'], {
            'ext': best.get('ext', 'mp4'),
            'format': best.get('format', 'video'),
            'has_audio': False,
            'resolution': f"{best.get('height', '?')}p",
            'note': 'Video only - audio may be missing'
        }
    
    return None, "No suitable streaming URL found"


# ═══════════════════════════════════════════════════════════════
# STREAMING HELPERS
# ═══════════════════════════════════════════════════════════════

def stream_url(url, filename, content_type, extra_headers=None):
    """
    Stream content from URL to client without storing on disk.
    Uses chunked transfer for memory efficiency.
    """
    headers = {**Config.INSTAGRAM_HEADERS}
    if extra_headers:
        headers.update(extra_headers)
    
    try:
        # Use requests with streaming
        r = requests.get(url, stream=True, headers=headers, timeout=Config.REQUEST_TIMEOUT)
        r.raise_for_status()
        
        content_length = r.headers.get('Content-Length')
        
        response_headers = {
            'Content-Type': content_type,
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-cache',
            'X-Content-Type-Options': 'nosniff',
        }
        
        if content_length:
            response_headers['Content-Length'] = content_length
        
        def generate():
            try:
                for chunk in r.iter_content(chunk_size=Config.CHUNK_SIZE):
                    if chunk:
                        yield chunk
            except Exception as e:
                logger.error(f"Streaming error: {str(e)}")
            finally:
                r.close()
        
        return Response(
            generate(),
            status=200,
            headers=response_headers,
            direct_passthrough=True
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch stream: {str(e)}")
        return None, f"Failed to fetch content: {str(e)}"


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def home():
    """API root - health check"""
    return jsonify({'status': 'API running', 'version': '2.0.0'})


@app.route('/api/download', methods=['POST'])
@require_api_key
@rate_limit
def download_video():
    """
    Extract video information from Instagram URL.
    Returns streaming URLs for video and audio.
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Invalid request',
            'message': 'Request body must be JSON'
        }), 400
    
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'Missing URL',
            'message': 'Please provide an Instagram URL'
        }), 400
    
    if len(url) > Config.MAX_URL_LENGTH:
        return jsonify({
            'success': False,
            'error': 'URL too long',
            'message': f'URL must be under {Config.MAX_URL_LENGTH} characters'
        }), 400
    
    # Validate Instagram URL
    ig_pattern = r'https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[^\s/?#]+'
    if not re.match(ig_pattern, url, re.IGNORECASE):
        return jsonify({
            'success': False,
            'error': 'Invalid URL',
            'message': 'Please provide a valid Instagram URL (reel, post, or TV)'
        }), 400
    
    try:
        logger.info(f"Processing video request: {url[:50]}...")
        
        # Extract video info
        info, error = extract_video_info(url, extract_audio=False)
        
        if error:
            return jsonify({
                'success': False,
                'error': 'Extraction failed',
                'message': error
            }), 400
        
        # Get video streaming URL
        video_url, video_info = get_streaming_url(info, prefer_audio=False)
        
        if not video_url:
            return jsonify({
                'success': False,
                'error': 'No video URL',
                'message': video_info or 'Could not extract video URL'
            }), 400
        
        # Get audio streaming URL
        audio_url, audio_info = get_streaming_url(info, prefer_audio=True)
        
        # Build response
        response_data = {
            'videoUrl': video_url,
            'videoInfo': video_info,
            'thumbnail': info.get('thumbnail', info.get('thumbnails', [{}])[-1].get('url') if info.get('thumbnails') else None),
            'title': info.get('title', info.get('description', 'Instagram Video')),
            'duration': info.get('duration'),
            'author': info.get('uploader', info.get('channel', None)),
            'shortcode': info.get('id'),
            'upload_date': info.get('upload_date'),
        }
        
        if audio_url:
            response_data['audioUrl'] = audio_url
            response_data['audioInfo'] = audio_info
        
        logger.info(f"Successfully extracted video: {response_data['shortcode']}")
        
        return jsonify({
            'success': True,
            'data': response_data,
            'message': 'Video extracted successfully'
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in download: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Please try again.'
        }), 500


@app.route('/api/download-audio', methods=['POST'])
@require_api_key
@rate_limit
def download_audio():
    """
    Extract audio-only from Instagram URL.
    Returns streaming URL for MP3.
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Invalid request'
        }), 400
    
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'Missing URL'
        }), 400
    
    # Validate Instagram URL
    ig_pattern = r'https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[^\s/?#]+'
    if not re.match(ig_pattern, url, re.IGNORECASE):
        return jsonify({
            'success': False,
            'error': 'Invalid URL'
        }), 400
    
    try:
        logger.info(f"Processing audio request: {url[:50]}...")
        
        # Extract audio info
        info, error = extract_video_info(url, extract_audio=True)
        
        if error:
            return jsonify({
                'success': False,
                'error': 'Extraction failed',
                'message': error
            }), 400
        
        # Get audio streaming URL
        audio_url, audio_info = get_streaming_url(info, prefer_audio=True)
        
        if not audio_url:
            return jsonify({
                'success': False,
                'error': 'No audio URL',
                'message': 'Could not extract audio URL'
            }), 400
        
        response_data = {
            'audioUrl': audio_url,
            'audioInfo': audio_info,
            'title': info.get('title', info.get('description', 'Instagram Audio')),
            'duration': info.get('duration'),
            'author': info.get('uploader', info.get('channel', None)),
            'shortcode': info.get('id'),
        }
        
        logger.info(f"Successfully extracted audio: {response_data['shortcode']}")
        
        return jsonify({
            'success': True,
            'data': response_data,
            'message': 'Audio extracted successfully'
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in audio download: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/stream', methods=['GET'])
@require_api_key
@rate_limit
def stream_content():
    """
    Proxy stream content from extracted URL.
    Use this endpoint to stream video/audio through your server.
    """
    media_url = request.args.get('url')
    filename = request.args.get('filename', 'media.mp4')
    content_type = request.args.get('type', 'video/mp4')
    
    if not media_url:
        return jsonify({
            'success': False,
            'error': 'Missing URL parameter'
        }), 400
    
    # Validate URL format
    if not media_url.startswith(('http://', 'https://')):
        return jsonify({
            'success': False,
            'error': 'Invalid URL format'
        }), 400
    
    try:
        logger.info(f"Streaming: {filename}")
        
        response = stream_url(media_url, filename, content_type)
        
        if response:
            return response
        
        return jsonify({
            'success': False,
            'error': 'Streaming failed'
        }), 500
        
    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Streaming error'
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint (no auth required for monitoring)"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'version': '2.0.0'
    })


# ═══════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Not found'
    }), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({
        'success': False,
        'error': 'Method not allowed'
    }), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info("Starting Instagram Reel Downloader v2.0.0")
    logger.info(f"Host: {Config.HOST}, Port: {Config.PORT}")
    logger.info(f"Rate limiting: {Config.RATE_LIMIT_MAX} req/{Config.RATE_LIMIT_WINDOW}s")
    
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        threaded=True
    )
