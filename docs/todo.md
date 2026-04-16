# Todo

## 进行中


## 待完成


## 已完成

- [x] 项目初始化：目录结构、requirements.txt、deploy/config.yaml
- [x] config.py：配置加载、层级合并（全局 + 摄像头级）
- [x] capture.py：异步抓帧、保存 JPEG
- [x] watermark.py：Pillow 水印叠加
- [x] scheduler.py：APScheduler 定时抓帧 + 每日合成 + 清理
- [x] composer.py：ffmpeg 合成每日视频
- [x] cleaner.py：过期快照清理
- [x] api/routes.py：RESTful API
- [x] 前端：主页摄像头卡片
- [x] 前端：摄像头详情页（快照浏览 + 视频列表）
- [x] Dockerfile + deploy/compose.yaml
- [x] 集成测试：端到端验证（config/watermark/cleaner/composer/API/server 全部通过）

## 问题记录

- conda 网络不通（anaconda.org / pypi 均超时），使用已有 lerobot 环境（Python 3.10）+ pip 局域网安装替代
  - 安装命令：`/home/robot/miniconda3/envs/lerobot/bin/pip install fastapi uvicorn apscheduler httpx aiofiles`
  - 启动命令：`CONFIG_PATH=config.yaml /home/robot/miniconda3/envs/lerobot/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080`
