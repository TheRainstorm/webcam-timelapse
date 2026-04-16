# webcam-timelapse 项目需求文档

## 项目概述

一个多摄像头延时摄影系统，支持从网络摄像头流（ustreamer/go2rtc）定时抓帧、打水印、自动合成每日延时视频，并提供美观的 Web 界面管理所有摄像头和历史视频。

---

## 核心功能

### 1. 摄像头管理

- 支持配置多个摄像头，每个摄像头独立配置
- 全局默认配置 + 摄像头级别覆盖（层级合并）
- 摄像头属性：
  - `name`：显示名称
  - `snapshot_url`：JPEG 截图 URL（如 `http://host/snapshot`）
  - `stream_url`（可选）：WebRTC/HLS 实时流地址（用于网页预览）
  - `output_dir`：输出根目录
  - `interval`：抓帧间隔（秒，默认 60）
  - `retention_days`：快照保留天数（默认 30）
  - `watermark`：水印配置（见下）

### 2. 定时抓帧

- 按 `interval` 间隔从 `snapshot_url` 拉取 JPEG
- 保存到 `output_dir/snapshots/YYYY-MM-DD/HH-MM-SS.jpg`
- 失败时记录日志，不中断服务
- 支持水印叠加：
  - 位置：四角之一（`top-left` / `top-right` / `bottom-left` / `bottom-right`）
  - 内容：时间戳（格式可配置，如 `%Y-%m-%d %H:%M:%S`）
  - 字体文件路径、字体大小、字体颜色、背景色（可选半透明）

### 3. 每日视频合成

- 每天触发一次（可配置时间，默认 `00:05`，合成前一天）
- 将 `snapshots/YYYY-MM-DD/` 下所有帧按时间顺序合成视频
- 输出到 `output_dir/videos/YYYY-MM-DD.mp4`
- 编码：H.264，帧率可配置（默认 24fps）
- 分辨率：自动取第一帧分辨率，或可配置固定分辨率
- 合成完成后可选是否删除当天快照（默认保留）
- 使用 ffmpeg 合成（通过 subprocess 调用）

### 4. 快照清理

- 定时任务（每天运行）：删除超过 `retention_days` 的快照目录
- 视频不自动删除，通过 Web 界面手动删除

### 5. 配置文件

```yaml
# config.yaml 示例结构
global:
  interval: 60
  retention_days: 30
  video_fps: 24
  video_time: "00:05"
  watermark:
    enabled: true
    position: bottom-right
    font: /path/to/font.ttf
    size: 24
    color: white
    bg_color: "rgba(0,0,0,0.5)"
    format: "%Y-%m-%d %H:%M:%S"

cameras:
  - name: "Front Door"
    snapshot_url: "http://192.168.1.10/snapshot"
    stream_url: "http://192.168.1.10/stream"
    output_dir: "/data/front-door"
    interval: 30  # 覆盖全局
  - name: "Garden"
    snapshot_url: "http://192.168.1.11/snapshot"
    output_dir: "/data/garden"
```

---

## Web 界面

### 主页 — 摄像头总览

- 卡片式布局，每张卡片显示：
  - 摄像头名称
  - 最新快照缩略图（默认黑屏占位）
  - 点击播放实时流（若配置了 `stream_url`）
  - 今日已抓帧数 / 最近抓帧时间
  - 快速跳转到详情页

### 摄像头详情页

- 实时流预览（WebRTC/HLS/MJPEG，可选）
- 快照日历视图：按日期浏览历史快照
- 视频列表：显示所有已合成视频，支持：
  - 在线播放（HTML5 video）
  - 下载
  - 删除（二次确认）
- 统计信息：总快照数、总视频数、磁盘占用

### API 接口（RESTful）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/cameras` | 获取所有摄像头状态 |
| GET | `/api/cameras/{name}/snapshots` | 获取快照列表（按日期） |
| GET | `/api/cameras/{name}/videos` | 获取视频列表 |
| DELETE | `/api/cameras/{name}/videos/{date}` | 删除指定视频 |
| POST | `/api/cameras/{name}/trigger` | 手动触发抓帧 |
| POST | `/api/cameras/{name}/compose` | 手动触发视频合成 |

---

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI + Uvicorn |
| 定时任务 | APScheduler |
| 图像处理 | Pillow |
| 视频合成 | ffmpeg（subprocess） |
| HTTP 客户端 | httpx（异步） |
| 配置解析 | PyYAML + pydantic |
| 前端 | 原生 HTML/CSS/JS（无框架，轻量） |
| 容器化 | Docker + docker-compose |

---

## 项目结构

```
webcam-timelapse/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置加载与合并
│   ├── scheduler.py         # 定时任务
│   ├── capture.py           # 抓帧逻辑
│   ├── watermark.py         # 水印处理
│   ├── composer.py          # 视频合成
│   ├── cleaner.py           # 快照清理
│   ├── api/
│   │   └── routes.py        # API 路由
│   └── static/              # 前端静态文件
│       ├── index.html
│       ├── camera.html
│       ├── style.css
│       └── app.js
├── deploy/
│   ├── config.yaml           # 配置示例
│   ├── compose.yaml          # 发布镜像部署
│   ├── compose.dev.yaml      # 本地 build 开发
│   └── compose.lan.yaml      # LAN 示例
├── docs/
│   ├── idea.md
│   ├── project.md
│   └── todo.md
└── fonts/
    └── NotoSansMono-Regular.ttf  # 默认水印字体
```

---

## Docker 部署

```yaml
# deploy/compose.lan.yaml
services:
  timelapse:
    build: ..
    ports:
      - "8080:8080"
    volumes:
      - ../config.yaml:/app/config.yaml
      - ../data:/data
      - ../fonts:/app/fonts
    restart: unless-stopped
```

---

## 扩展想法（未来可选）

- 运动检测：只在画面有变化时才保存快照（节省存储）
- 邮件/Webhook 通知：摄像头离线告警
- 快照对比：滑动对比同一位置不同时间的画面
- 多分辨率输出：同时生成高清和压缩版视频
- 认证：简单的 Basic Auth 或 Token 保护 Web 界面
- 时间段过滤：只在指定时间段（如白天 6:00-22:00）抓帧
