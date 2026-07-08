FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（PostgreSQL 客户端库、编译工具）
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件并安装，利用缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

EXPOSE 8000

# 使用 0.0.0.0 监听，方便 Docker 外部访问
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
