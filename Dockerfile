FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 确保 static 目录存在
RUN mkdir -p static || true

# 暴露端口
EXPOSE 8000

# 创建数据目录
RUN mkdir -p /app/data && chmod 777 /app/data

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

