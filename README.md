# 小雅影视

基于 Flask 的影视搜索播放网站，支持本地 PotPlayer 播放。

## 功能特性

- 🔍 搜索影视资源 - 支持搜索电影、电视剧、动漫、纪录片等
- 🎬 PotPlayer 播放 - 直接调用本地 PotPlayer 播放视频
- 📁 文件夹浏览 - 支持浏览文件夹目录结构
- 🎥 视频直链 - 获取直链，播放流畅

## 环境要求

- Python 3.8+
- PotPlayer (需提前安装)

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

访问 http://127.0.0.1:5000

## 目录说明

```
movie/
├── app.py              # Flask 主程序
├── requirements.txt    # Python 依赖
├── templates/          # HTML 模板
│   ├── base.html       # 基础模板
│   ├── index.html      # 首页
│   ├── browse.html     # 浏览页面
│   └── search.html     # 搜索页面
└── README.md
```

## API 接口

| URL | 说明 |
|-----|------|
| `/` | 首页 |
| `/search?keyword=xxx` | 搜索 |
| `/browse?path=/xxx` | 浏览文件夹 |
| `/api/direct_play/<path>` | 获取视频直链 |

## 技术栈

- Flask
- BeautifulSoup4
- requests
- PotPlayer