import socket
import time
from urllib.parse import unquote

import requests
import requests.packages.urllib3.util.connection as urllib3_conn
from bs4 import BeautifulSoup, SoupStrainer
from flask import Flask, render_template, request, jsonify, redirect, url_for

urllib3_conn.allowed_gai_family = lambda: socket.AF_INET

import os
import sys

_base_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
app = Flask(__name__, template_folder=os.path.join(_base_dir, 'templates'))

ALIST_BASE_URL = "http://www.zhanghanhome.cn:5678"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_session = requests.Session()
_search_cache = {}
SEARCH_CACHE_TTL = 3600
SEARCH_CACHE_MAX_ENTRIES = 100
SEARCH_TIMEOUT = 15
MAX_SEARCH_RESULTS = 200


def _get_cached_search(keyword):
    entry = _search_cache.get(keyword)
    if entry and time.time() - entry["time"] < SEARCH_CACHE_TTL:
        return entry["results"]
    return None


def _set_cached_search(keyword, results):
    _search_cache[keyword] = {"results": results, "time": time.time()}
    if len(_search_cache) > SEARCH_CACHE_MAX_ENTRIES:
        oldest = min(_search_cache, key=lambda k: _search_cache[k]["time"])
        del _search_cache[oldest]


def _log_request_time(label, start):
    elapsed = time.time() - start
    print(f"[perf] {label} took {elapsed * 1000:.0f}ms")


def get_raw_url(path):
    start = time.time()
    params = {"password": "", "path": path}
    try:
        resp = _session.get(f"{ALIST_BASE_URL}/api/fs/get", params=params, headers=HEADERS, timeout=30)
        _log_request_time(f"GET /api/fs/get path={path}", start)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200:
                return data.get("data", {}).get("raw_url")
    except Exception as e:
        print(f"Get raw URL error: {e}")
    return None


def call_alist_api(path="/", page=1, per_page=50):
    start = time.time()
    params = {
        "password": "",
        "path": path,
        "page": page,
        "per_page": per_page,
        "refresh": "true"
    }
    try:
        resp = _session.get(f"{ALIST_BASE_URL}/api/fs/list", params=params, headers=HEADERS, timeout=30)
        _log_request_time(f"GET /api/fs/list path={path}", start)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f}MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f}GB"


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
        content = result.get("data") or {}
        for item in content.get("content") or []:
            items.append({
                "name": item["name"],
                "path": item["name"],
                "is_dir": item.get("is_dir", False),
                "size": format_size(item.get("size", 0)) if not item.get("is_dir") else "",
                "type": item.get("type", 1),
                "is_video": not item.get("is_dir", False)
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

    cached = _get_cached_search(keyword)
    if cached is not None:
        return render_template("search.html", results=cached, keyword=keyword)

    all_results = []
    seen_paths = set()

    try:
        req_start = time.time()
        resp = _session.get(
            f"{ALIST_BASE_URL}/search",
            params={"box": keyword, "type": "video"},
            headers=HEADERS,
            timeout=SEARCH_TIMEOUT,
            stream=True
        )
        # measure TTFB (time to first byte)
        ttfb = time.time() - req_start
        body = resp.content
        body_size = len(body)
        total_dl = time.time() - req_start
        resp.close()

        _log_request_time(f"GET /search keyword={keyword}", req_start)
        print(f"[perf]   TTFB={ttfb * 1000:.0f}ms body_size={body_size / 1024:.0f}KB total={total_dl * 1000:.0f}ms")

        if resp.status_code == 200:
            strainer = SoupStrainer('a')
            soup = BeautifulSoup(body, 'lxml', parse_only=strainer)

            keyword_lower = keyword.lower()

            for link in soup:
                href = link.get('href', '')
                if not href.startswith('/') or href in seen_paths:
                    continue

                text = link.get_text(strip=True)
                if keyword_lower not in text.lower():
                    continue

                seen_paths.add(href)

                name = href.split('/')[-1]
                all_results.append({
                    "name": name or text,
                    "path": href,
                    "is_dir": True,
                    "is_video": False
                })

                if len(all_results) >= MAX_SEARCH_RESULTS:
                    break

    except Exception as e:
        print(f"Search error: {e}")

    _set_cached_search(keyword, all_results)

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
