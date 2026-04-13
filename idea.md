webcam-timelapse

项目介绍：

- 支持添加多个 camera（名字，对应配置），每隔 camera 如下
  - 从一个 url （如 ustreamer / go2rtc）获得 usb webcam （jpeg）截图
  - 设置一个输出目录 output
  - 每隔固定间隔截取一帧，保留到 output/snapshot 里
    - 支持在选择的位置（四角）打上时间戳水印，使用字体文件，可设置大小
  - 每天一个时间（比如中午 12 点前）合并生成上一天的视频，保存到 output/videos 里
    - 使用 h264 编码
  - snapshots 默认保留 30 天（可配置）
  - video 手动删除
  - 所有配置分层次保存到 yaml 配置文件
  - stream url 可选，webrtc 显示 camera 实时画面（h264）
- 可以配置全局默认配置，和每个 camera 单独配置

网页需求

- 启动一个网页服务
- 美观显示所有 camera
  - 默认黑屏，点击可以播放当前实时画面
- 可以进入 camera 详细界面
- 显示历史延时摄影，可以删除延时摄影


技术栈

- 主要使用 python
- 支持 docker 部署
- 代码风格要短小精悍可读

