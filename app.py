# -*- coding: utf-8 -*-
"""
极简视频搜索 + PotPlayer 播放 Flask 应用
数据源：http://www.zhanghanhome.cn:5678/tvbox/my.json
功能：关键词搜索 → 浏览目录 → 获取直链 → PotPlayer 播放
"""

from flask import Flask, render_template, request, jsonify
import requests
import re
import os
import socket
from urllib.parse import unquote

app = Flask(__name__)

# ==================== 配置区 ====================
# AList 服务器地址（小雅 AList），可通过环境变量覆盖
ALIST_SERVER = os.environ.get("ALIST_SERVER", "http://www.zhanghanhome.cn:5678")
# 远端 TVBox JSON 数据地址
DATA_URL = f"{ALIST_SERVER}/tvbox/my.json"
# 请求超时（秒）
TIMEOUT = 15


# ==================== 强制 IPv4 ====================
def _patch_ipv4():
    """
    强制所有 requests 请求使用 IPv4，避免 IPv6 连接超时或失败。
    原理：猴子补丁 socket.getaddrinfo，过滤掉 AF_INET6 结果，
    使所有 DNS 解析只返回 IPv4 地址。
    """
    _orig = socket.getaddrinfo

    def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _ipv4_only


# 应用启动时立即打补丁
_patch_ipv4()


# ==================== 小雅 AList 搜索 ====================
def search_xiaoya(keyword):
    """
    调用小雅 AList 自定义搜索接口 /search?box=关键词&type=video
    解析返回 HTML 中的目录链接，提取搜索结果
    """
    results = []
    try:
        resp = requests.get(
            f"{ALIST_SERVER}/search",
            params={"box": keyword, "type": "video"},
            timeout=TIMEOUT
        )
        html = resp.text
        # 小雅搜索结果格式：<a href=/path/to/dir>显示文本</a>
        # 匹配所有 <a> 标签中的路径和文本
        pattern = r'<a\s+href=([^>]+)>([^<]+)</a>'
        matches = re.findall(pattern, html)
        for href, text in matches:
            # 只保留以 / 开头的内部路径，排除静态资源等
            if (href.startswith('/')
                    and not href.startswith('//')
                    and not href.startswith('/assets')
                    and not href.startswith('/d/')
                    and not href.startswith('/s/')
                    and not href.startswith('/api/')):
                # 关键修复：搜索结果中的路径含 URL 编码（如 %20），
                # AList API 需要解码后的真实路径才能正确访问
                decoded_path = unquote(href)
                results.append({
                    'path': decoded_path,
                    'name': text.strip()
                })
    except requests.RequestException as e:
        print(f"[搜索失败] {e}")
    return results


# ==================== AList 目录浏览 ====================
def list_directory(path):
    """
    调用 AList API /api/fs/list 列出指定目录内容
    返回文件和子目录列表
    """
    items = []
    try:
        resp = requests.post(
            f"{ALIST_SERVER}/api/fs/list",
            json={"path": path, "page": 1, "per_page": 200},
            timeout=TIMEOUT
        )
        data = resp.json()
        if data.get('code') == 200:
            for item in data.get('data', {}).get('content', []):
                name = item.get('name', '')
                is_dir = item.get('is_dir', False)
                size = item.get('size', 0)
                # 拼接完整路径
                full_path = f"{path.rstrip('/')}/{name}"
                # 不限制文件后缀，所有文件均可点击（目录进入浏览，文件获取直链播放）
                items.append({
                    'name': name,
                    'path': full_path,
                    'is_dir': is_dir,
                    'size': size
                })
    except requests.RequestException as e:
        print(f"[目录浏览失败] path={path}, error={e}")
    return items


# ==================== AList 获取文件直链 ====================
def get_file_raw_url(path):
    """
    调用 AList API /api/fs/get 获取文件的真实播放直链（raw_url）
    该直链可直接用于 PotPlayer 播放
    """
    try:
        resp = requests.post(
            f"{ALIST_SERVER}/api/fs/get",
            json={"path": path},
            timeout=TIMEOUT
        )
        data = resp.json()
        if data.get('code') == 200:
            raw_url = data.get('data', {}).get('raw_url', '')
            return raw_url
    except requests.RequestException as e:
        print(f"[获取直链失败] path={path}, error={e}")
    return ''


# ==================== Flask 路由 ====================
@app.route('/')
def index():
    """首页：极简搜索页面"""
    return render_template('index.html')


@app.route('/api/search')
def api_search():
    """搜索接口：根据关键词搜索视频目录"""
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify({'results': [], 'error': '请输入搜索关键词'})
    results = search_xiaoya(keyword)
    return jsonify({'results': results})


@app.route('/api/list')
def api_list():
    """目录浏览接口：列出指定路径下的文件和子目录"""
    path = request.args.get('path', '/').strip()
    items = list_directory(path)
    return jsonify({'items': items})


@app.route('/api/play')
def api_play():
    """播放接口：获取视频文件直链，供前端调用 PotPlayer"""
    path = request.args.get('path', '').strip()
    if not path:
        return jsonify({'url': '', 'error': '路径为空'})
    raw_url = get_file_raw_url(path)
    if raw_url:
        return jsonify({'url': raw_url})
    else:
        return jsonify({'url': '', 'error': '无法获取播放地址'})


# ==================== 启动入口 ====================
if __name__ == '__main__':
    print(f"数据源: {DATA_URL}")
    print(f"AList 服务器: {ALIST_SERVER}")
    print("启动地址: http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
