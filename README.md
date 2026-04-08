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
- Redis - 缓存
- Vue 3 + Vite - 前端框架

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
├── run.py                  # 项目启动入口
└── start.py                # 一键启动脚本
```

## 快速开始

### 方式一：一键启动（推荐）

使用提供的一键启动脚本：

```bash
python start.py
```

该脚本会自动完成以下操作：
1. 检查 Docker 运行状态
2. 启动 RabbitMQ 和 Redis 容器
3. 初始化数据库
4. 启动 FastAPI 服务

### 方式二：手动启动

#### 1. 启动依赖服务

**Docker 服务（RabbitMQ + Redis）：**
```bash
docker start deeee04007b2  # RabbitMQ
docker start 860458aef4e2  # Redis
```

**MySQL 服务：**
确保本地 MySQL 服务已启动（端口：3308）

#### 2. 环境配置

使用 conda 创建环境：
```bash
conda env create -f environment.yml
conda activate graduate_yolov12
```

或使用 pip 安装依赖：
```bash
pip install -r requirements.txt
```

#### 3. 数据库初始化

```bash
python init_db.py
```

#### 4. 启动后端服务

```bash
python run.py
```

后端服务启动后，访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

#### 5. 启动前端服务

进入前端目录：
```bash
cd ../ABRS-front
```

安装依赖：
```bash
npm install
```

启动开发服务器：
```bash
npm run dev
```

前端访问地址：http://localhost:5173

## 服务端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI | 8000 | 后端 API 服务 |
| MySQL | 3308 | 数据库服务 |
| RabbitMQ | 5672 | 消息队列服务 |
| RabbitMQ 管理界面 | 15672 | RabbitMQ Web 管理 |
| Redis | 6379 | 缓存服务 |
| Vue 开发服务器 | 5173 | 前端开发服务 |

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
- RTSP/HTTP-FLV 网络视频流

## 接口文档

启动后端服务后，访问 Swagger 文档：
- http://localhost:8000/docs

## 开发指南

参见 [PRD 文档](./PRD/ABRS_总PRD.md) 了解详细的开发规范和模块整合流程。

## 常见问题

### 1. 数据库连接失败

检查 MySQL 服务是否启动，以及配置文件 `config/db_config.py` 中的连接信息是否正确。

### 2. RabbitMQ 连接失败

确保 Docker 容器已启动：
```bash
docker ps
```

如果容器未运行，启动它：
```bash
docker start deeee04007b2
```

### 3. 前端 404 错误

确保后端服务已启动，并检查前端 API 调用路径是否正确。

### 4. 模型权重文件缺失

确保 `weights/` 目录中包含以下文件：
- yolov12n.pt - YOLOv12 检测模型
- banner.pt - 横幅检测模型（可选）

## License

MIT
