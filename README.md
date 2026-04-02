# Abnormal-Behavior-Recognition-System (ABRS)

基于计算机视觉技术的异常行为识别系统，支持横幅识别、离岗识别、徘徊警告、聚集警告四大核心模块。

## 技术栈

- Python 3.11
- FastAPI - Web框架
- YOLOv12 - 目标检测
- ByteTrack - 多目标跟踪
- PaddleOCR - 文字识别
- MySQL - 数据存储
- RabbitMQ - 消息队列

## 项目结构

```
ABRS/
├── PRD/                    # 项目需求文档
├── config/                 # 全局配置
├── api/                    # 统一API路由
├── core/                   # 核心模块逻辑
├── models/                 # ORM模型
├── utils/                  # 工具类
├── static/                 # 静态资源
├── logs/                   # 日志目录
├── scripts/                # 辅助脚本
├── init_db.py              # 数据库初始化
└── run.py                  # 项目启动入口
```

## 快速开始

### 1. 环境配置

使用conda创建环境：
```bash
conda env create -f environment.yml
```

或使用pip安装依赖：
```bash
pip install -r requirements.txt
```

### 2. 数据库初始化

```bash
python init_db.py
```

### 3. 启动项目

```bash
python run.py
```

## 核心模块

| 模块 | 功能 | 路由前缀 |
|------|------|----------|
| 横幅识别 | 检测横幅违规 | /api/v1/banner |
| 离岗识别 | 检测人员离岗 | /api/v1/absent |
| 徘徊警告 | 检测区域徘徊 | /api/v1/loitering |
| 聚集警告 | 检测人员聚集 | /api/v1/gathering |

## 输入源支持

- 本地摄像头
- 本地视频文件（MP4/AVI）
- RTSP/HTTP-FLV网络视频流

## 开发指南

参见 [PRD文档](./PRD/ABRS_总PRD.md) 了解详细的开发规范和模块整合流程。

## License

MIT
