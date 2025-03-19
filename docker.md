# Docker 使用说明

本项目包含两个服务：
1. `alerts` - Prometheus告警处理服务
2. `chat` - AI聊天服务

## 快速开始

### 使用 Docker Compose（推荐）

1. 确保你的系统已安装Docker和Docker Compose
2. 在项目根目录下运行：

```bash
docker-compose up -d
```

这将会：
- 构建Docker镜像
- 创建并启动两个服务
- 映射端口 6000 和 6001 到宿主机
- 创建持久化数据卷

### 仅使用Docker

如果你只想运行告警服务：

```bash
# 构建镜像
docker build -t grok-app .

# 运行告警服务
docker run -d -p 6000:6000 -v $(pwd)/data:/app/data grok-app

# 运行聊天服务
docker run -d -p 6001:6001 -v $(pwd)/data:/app/data grok-app python chat.py
```

## 数据持久化

所有数据存储在 `./data` 目录，被挂载到容器内的 `/app/data` 目录。这确保了即使容器被删除，数据也会保留。

## 服务访问

- 告警服务: http://localhost:6000/api/alerts
- 聊天服务: 通过命令行界面使用（目前没有Web界面）

## 环境变量

可以通过环境变量定制服务：

- `DB_PATH`: 聊天历史数据库路径
- `ALERTS_DB_PATH`: 告警数据库路径

## 日志查看

```bash
# 查看告警服务日志
docker-compose logs alerts

# 查看聊天服务日志
docker-compose logs chat
``` 