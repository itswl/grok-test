FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY alerts.py .
COPY chat.py .
COPY report.py .
COPY config.yaml .

# 创建数据卷
VOLUME ["/app/data"]

# 设置环境变量，将数据库路径指向数据卷
ENV DB_PATH="/app/data/chat.db"
ENV ALERTS_DB_PATH="/app/data/alerts.db"

# 暴露端口
EXPOSE 6000

# 设置启动命令（默认启动alert服务）
CMD ["python", "alerts.py"] 