# Webcam Timelapse

一个多摄像头延时摄影服务。它会按配置定时从网络摄像头的 JPEG snapshot 地址抓帧、叠加时间水印、按天合成 MP4 延时视频，并提供 FastAPI + 静态页面用于查看摄像头状态、快照和视频。

![index.png](https://imagebed.yfycloud.site/2026/04/1423c169cc2126b0ba121c568f516f63.png)

![video.png](https://imagebed.yfycloud.site/2026/04/2dc12a61fa47cfff303dad827d303e0a.png)

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
cp deploy/config.yaml config.yaml
```

2. 修改 `config.yaml` 里的摄像头地址和输出目录。Docker Compose 默认把宿主机的 `./data` 挂载到容器内 `/data`，所以摄像头的 `output_dir` 建议使用 `/data/<camera-name>`：

```yaml
cameras:
  - name: "Front Door"
    snapshot_url: "http://192.168.1.10/snapshot"
    stream_url: "/go2rtc/webrtc.html?src=front-door"
    output_dir: "/data/front-door"
```

3. 启动服务：

```bash
docker compose -f deploy/compose.yaml up -d
```

4. 打开 Web 界面：

```text
http://localhost:4433
```

5. 查看日志：

```bash
docker compose -f deploy/compose.yaml logs -f timelapse
```

### Docker Nginx Reverse Proxy

`deploy/compose.yaml` 使用发布镜像，包含一个 `nginx` 服务。容器启动时会根据环境变量生成 Nginx 配置：

- `/` 反代到 timelapse Web。
- `/go2rtc/` 反代到 go2rtc WebRTC 服务，并自动去掉 `/go2rtc/` 前缀。

常用环境变量：

```yaml
environment:
  - SERVER_NAME=timelapse.yfycloud.site
  - LISTEN_PORT=4433
  - TIMELAPSE_UPSTREAM=http://timelapse:8080
  - GO2RTC_UPSTREAM=http://go2rtc:1984
```

如果 go2rtc 跑在宿主机或另一台内网机器，把 `GO2RTC_UPSTREAM` 改成 Docker 容器可访问的地址，例如：

```yaml
GO2RTC_UPSTREAM=http://host.docker.internal:1984
```

此时相机配置里的实时预览地址只写 path：

```yaml
stream_url: "/go2rtc/webrtc.html?src=front-door"
```

公网访问 `https://timelapse.yfycloud.site:4433` 时，浏览器会自动用同一个域名加载 `/go2rtc/...`。

#### Outer Nginx with TLS and Basic Auth

如果公网机器上还要再做一层 Nginx，推荐分工如下：

- 外层 Nginx：TLS + Basic Auth + 全部转发到 Docker Nginx。
- Docker Nginx：`/` -> timelapse，`/go2rtc/` -> go2rtc。

先创建 Basic Auth 密码文件：

```bash
sudo apt-get install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd-timelapse timelapse
```

外层 Nginx 示例，假设 Docker Nginx 映射到宿主机 `127.0.0.1:7788`：

```nginx
server {
    listen 4433 ssl http2;
    listen [::]:4433 ssl http2;
    server_name timelapse.yfycloud.site;

    ssl_certificate     /etc/letsencrypt/live/timelapse.yfycloud.site/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/timelapse.yfycloud.site/privkey.pem;

    auth_basic "Webcam Timelapse";
    auth_basic_user_file /etc/nginx/.htpasswd-timelapse;

    client_max_body_size 100m;

    location / {
        proxy_pass http://127.0.0.1:7788;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

这种方式下，外层 Nginx 不需要再单独写 `/go2rtc/` 分流，直接把所有路径转给 Docker Nginx 即可。Docker Nginx 会继续处理 `/go2rtc/` 前缀。普通 Web/API 不需要关闭 buffering；如需针对 WebRTC 关闭 buffering，应放在 Docker Nginx 的 `/go2rtc/` location 中。

### Docker Images

发布部署使用两个镜像：

- `rzero/webcam-timelapse:latest`: FastAPI 应用和静态页面。
- `rzero/webcam-timelapse-nginx:latest`: Nginx 反向代理，负责 `/` 和 `/go2rtc/` 路由。

可以在同一次发布流程里一起构建和推送：

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t rzero/webcam-timelapse:latest \
  --push .

docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/nginx/Dockerfile \
  -t rzero/webcam-timelapse-nginx:latest \
  --push .
```

本地开发使用 `deploy/compose.dev.yaml`，它会从当前代码 build 镜像：

```bash
docker compose -f deploy/compose.dev.yaml up -d --build
```

开发 compose 默认设置：

```yaml
SCHEDULER_ENABLED=false
```

这样开发服务只启动 Web/API，不会自动抓帧、合成视频或清理快照。适合把生产数据目录以只读方式挂载进开发容器，用于查看已有数据而不影响正在运行的生产服务。

### Local Python

本地运行需要 Python 3.11+，并且系统里需要可执行的 `ffmpeg`。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp deploy/config.yaml config.yaml
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

如果配置文件不在仓库根目录，可以指定 `CONFIG_PATH`：

```bash
CONFIG_PATH=/path/to/config.yaml uvicorn app.main:app --host 0.0.0.0 --port 8080
```

如果只想启动 Web/API，不启动后台定时任务，可以设置：

```bash
SCHEDULER_ENABLED=false uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Configuration

配置文件默认读取 `config.yaml`，也可以通过环境变量 `CONFIG_PATH` 指定。`global` 会作为默认值，`cameras` 中每个摄像头可以覆盖这些字段。

```yaml
global:
  interval: 30
  retention_days: 30
  video_fps: 60
  video_speed_factor: 1.0
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
    stream_url: "/go2rtc/webrtc.html?src=front-door"
    output_dir: "/data/front-door"
    interval: 30
```

关键字段：

- `snapshot_url`: 必填，返回 JPEG 图片的摄像头截图地址。
- `stream_url`: 可选，用于前端实时预览；建议只配置 path，例如 `/go2rtc/webrtc.html?src=front-door`，由当前访问域名和反向代理补全。
- `output_dir`: 必填，快照和视频的输出根目录。
- `interval`: 抓帧间隔，单位秒。
- `retention_days`: 快照保留天数。
- `video_fps`: 合成视频输出帧率。
- `video_speed_factor`: 快进系数，实际快进倍数 = `interval * video_fps * video_speed_factor`。
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
├── deploy/
│   ├── config.yaml           # 配置示例
│   ├── compose.yaml          # 发布镜像部署
│   ├── compose.dev.yaml      # 本地 build 开发
│   └── compose.lan.yaml      # 仅应用服务的 LAN 示例
├── docs/
│   ├── idea.md
│   ├── project.md
│   └── todo.md
├── Dockerfile
├── fonts/
└── requirements.txt
```

本机私有的 `config.yaml`、`docker-compose.yaml` 和运行数据目录不纳入 git 管理。
