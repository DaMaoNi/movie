from flask import Flask, render_template, request, jsonify, redirect, url_for
import requests
from urllib.parse import quote, unquote
from bs4 import BeautifulSoup

app = Flask(__name__)

ALIST_BASE_URL = "http://www.zhanghanhome.cn:5678"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.mts', '.m2ts'}


def get_file_url(path):
    encoded_path = quote(path)
    return f"{ALIST_BASE_URL}/d{encoded_path}"


def get_raw_url(path):
    params = {"password": "", "path": path}
    try:
        resp = requests.get(f"{ALIST_BASE_URL}/api/fs/get", params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200:
                return data.get("data", {}).get("raw_url")
    except Exception as e:
        print(f"Get raw URL error: {e}")
    return None


def call_alist_api(path="/", page=1, per_page=50):
    params = {
        "password": "",
        "path": path,
        "page": page,
        "per_page": per_page,
        "refresh": "true"
    }
    try:
        resp = requests.get(f"{ALIST_BASE_URL}/api/fs/list", params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def is_video_file(name):
    name_lower = name.lower()
    for ext in VIDEO_EXTENSIONS:
        if name_lower.endswith(ext):
            return True
    return False


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f}KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.1f}MB"
    else:
        return f"{size_bytes/1024**3:.2f}GB"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/browse")
def browse():
    path = request.args.get("path", "/")
    page = int(request.args.get("page", 1))
    decoded_path = unquote(path)

    result = call_alist_api(decoded_path, page)

    items = []
    if result and result.get("code") == 200:
        for item in result.get("data", {}).get("content", []):
            items.append({
                "name": item["name"],
                "path": item["name"],
                "is_dir": item.get("is_dir", False),
                "size": format_size(item.get("size", 0)) if not item.get("is_dir") else "",
                "type": item.get("type", 1),
                "is_video": is_video_file(item["name"]) if not item.get("is_dir") else False
            })

    return render_template("browse.html",
                         items=items,
                         current_path=decoded_path,
                         page=page)


@app.route("/search")
def search():
    keyword = request.args.get("keyword", "")
    if not keyword:
        return redirect(url_for("index"))

    all_results = []

    try:
        resp = requests.get(
            f"{ALIST_BASE_URL}/search",
            params={"box": keyword, "type": "video"},
            headers=HEADERS,
            timeout=60
        )
        resp.encoding = 'utf-8'

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            links = soup.find_all('a')

            seen_paths = set()

            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                if href.startswith('/') and keyword.lower() in text.lower() and href not in seen_paths:
                    seen_paths.add(href)

                    name = href.split('/')[-1]
                    if is_video_file(name):
                        all_results.append({
                            "name": name,
                            "path": href,
                            "is_dir": False,
                            "is_video": True
                        })
                    elif text == name or '/' not in href.rstrip('/'):
                        pass
                    else:
                        all_results.append({
                            "name": text,
                            "path": href,
                            "is_dir": True,
                            "is_video": False
                        })

    except Exception as e:
        print(f"Search error: {e}")

    return render_template("search.html",
                         results=all_results,
                         keyword=keyword)


@app.route("/api/direct_play/<path:file_path>")
def direct_play(file_path):
    decoded_path = unquote(file_path)
    raw_url = get_raw_url(decoded_path)

    if raw_url:
        return jsonify({"success": True, "raw_url": raw_url})
    return jsonify({"success": False, "error": "无法获取视频链接"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)