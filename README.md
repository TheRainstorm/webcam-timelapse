# Webcam Timelapse

一个多摄像头延时摄影服务。它会按配置定时从网络摄像头的 JPEG snapshot 地址抓帧、叠加时间水印、按天合成 MP4 延时视频，并提供 FastAPI + 静态页面用于查看摄像头状态、快照和视频。

## Features

- 多摄像头配置，支持全局默认值和摄像头级覆盖。
- 定时抓帧，保存到 `output_dir/snapshots/YYYY-MM-DD/HH-MM-SS.jpg`。
- 可配置时间水印：位置、字体、字号、颜色、背景色和时间格式。
- 每日自动合成视频，默认合成前一天快照到 `output_dir/videos/YYYY-MM-DD.mp4`。
- 每日清理过期快照，视频保留并可通过 API 删除。
- Web 界面和 REST API，用于查看摄像头、快照、视频并手动触发任务。

## Quick Start

### Docker Compose

1. 复制并编辑配置：

```bash
cp config.example.yaml config.yaml
```

2. 修改 `config.yaml` 里的摄像头地址和输出目录。Docker Compose 默认把宿主机的 `./data` 挂载到容器内 `/data`，所以摄像头的 `output_dir` 建议使用 `/data/<camera-name>`：

```yaml
cameras:
  - name: "Front Door"
    snapshot_url: "http://192.168.1.10/snapshot"
    stream_url: "http://192.168.1.10/stream"
    output_dir: "/data/front-door"
```

3. 启动服务：

```bash
docker compose up -d --build
```

4. 打开 Web 界面：

```text
http://localhost:8080
```

5. 查看日志：

```bash
docker compose logs -f timelapse
```

### Local Python

本地运行需要 Python 3.11+，并且系统里需要可执行的 `ffmpeg`。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

如果配置文件不在仓库根目录，可以指定 `CONFIG_PATH`：

```bash
CONFIG_PATH=/path/to/config.yaml uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Configuration

配置文件默认读取 `config.yaml`，也可以通过环境变量 `CONFIG_PATH` 指定。`global` 会作为默认值，`cameras` 中每个摄像头可以覆盖这些字段。

```yaml
global:
  interval: 60
  retention_days: 30
  video_fps: 24
  video_time: "00:05"
  watermark:
    enabled: true
    position: bottom-right
    font: fonts/NotoSansMono-Regular.ttf
    size: 24
    color: "white"
    bg_color: "rgba(0,0,0,128)"
    format: "%Y-%m-%d %H:%M:%S"

cameras:
  - name: "Front Door"
    snapshot_url: "http://192.168.1.10/snapshot"
    stream_url: "http://192.168.1.10/stream"
    output_dir: "/data/front-door"
    interval: 30
```

关键字段：

- `snapshot_url`: 必填，返回 JPEG 图片的摄像头截图地址。
- `stream_url`: 可选，用于前端实时预览。
- `output_dir`: 必填，快照和视频的输出根目录。
- `interval`: 抓帧间隔，单位秒。
- `retention_days`: 快照保留天数。
- `video_fps`: 合成视频帧率。
- `video_time`: 每日合成任务触发时间，格式为 `HH:MM`，默认合成前一天。
- `watermark.font`: 水印字体路径；Docker Compose 会把 `./fonts` 挂载到 `/app/fonts`。

## Output Layout

每个摄像头的输出目录结构如下：

```text
<output_dir>/
  snapshots/
    2026-04-13/
      12-00-00.jpg
      12-01-00.jpg
  videos/
    2026-04-13.mp4
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/cameras` | 获取摄像头列表和当前状态 |
| `GET` | `/api/cameras/{name}/snapshots` | 获取摄像头快照日期和文件列表 |
| `GET` | `/api/cameras/{name}/videos` | 获取摄像头视频列表 |
| `DELETE` | `/api/cameras/{name}/videos/{video_date}` | 删除指定日期的视频 |
| `POST` | `/api/cameras/{name}/trigger` | 手动抓取一帧 |
| `POST` | `/api/cameras/{name}/compose` | 手动合成视频，默认合成昨天 |
| `GET` | `/api/cameras/{name}/snapshots/{snap_date}/{filename}` | 下载或查看单张快照 |
| `GET` | `/api/cameras/{name}/videos/{filename}` | 下载或播放 MP4 视频 |

手动合成指定日期：

```bash
curl -X POST "http://localhost:8080/api/cameras/Front%20Door/compose?target_date=2026-04-13"
```

## Project Structure

```text
.
├── app/
│   ├── api/routes.py      # REST API
│   ├── capture.py         # 抓帧和保存
│   ├── cleaner.py         # 快照清理
│   ├── composer.py        # ffmpeg 视频合成
│   ├── config.py          # 配置加载和层级合并
│   ├── main.py            # FastAPI 入口
│   ├── scheduler.py       # APScheduler 定时任务
│   ├── watermark.py       # 水印处理
│   └── static/            # Web 静态页面
├── config.example.yaml
├── docker-compose.yml
├── Dockerfile
├── fonts/
└── requirements.txt
```
