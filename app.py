from flask import Flask, request, jsonify, send_from_directory, Response
import yt_dlp
import webbrowser
import threading
import time
import os
import uuid
import requests

app = Flask(__name__)

# Serve index.html
@app.route('/')
def home():
    return send_from_directory(os.getcwd(), 'index.html')


# 🔥 Fetch video using yt-dlp
def fetch_video(url):
    file_id = str(uuid.uuid4())
    output = f"downloads/{file_id}.%(ext)s"

    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        'outtmpl': output,
        'cookiefile': 'cookies.txt',
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        filename = ydl.prepare_filename(info)
        filename = filename.rsplit('.', 1)[0] + '.mp4'

        return {
            "videoUrl": f"/downloads/{os.path.basename(filename)}",
            "thumbUrl": info.get("thumbnail"),
            "caption": info.get("title"),
            "owner": info.get("uploader"),
            "duration": info.get("duration"),
            "shortcode": info.get("id"),
        }


# ✅ API: Get video data
@app.route('/api/download', methods=['POST'])
def download():
    data = request.json
    url = data.get("url")

    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400

    try:
        result = fetch_video(url)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/downloads/<filename>')
def serve_file(filename):
    return send_from_directory('downloads', filename, as_attachment=True)

# ✅ API: Stream video (used by "Save MP4" button)
@app.route('/api/proxy-download')
def proxy_download():
    video_url = request.args.get('url')
    filename = request.args.get('filename', 'video.mp4')

    if not video_url:
        return "Missing URL", 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.instagram.com/"
        }

        r = requests.get(video_url, stream=True, headers=headers)

        return Response(
            r.iter_content(chunk_size=8192),
            content_type=r.headers.get('content-type', 'video/mp4'),
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": r.headers.get("content-length", ""),
            }
        )

    except Exception as e:
        return f"Error: {str(e)}", 500


# Auto open browser
def open_browser():
    time.sleep(1)
    webbrowser.open("http://localhost:3000")


if __name__ == "__main__":
    threading.Thread(target=open_browser).start()
    app.run(port=3000)