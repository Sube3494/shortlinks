FROM oven/bun:1.3.13

WORKDIR /app

ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG ALL_PROXY=""
ARG NO_PROXY="localhost,127.0.0.1"
ENV HTTP_PROXY= \
    HTTPS_PROXY= \
    ALL_PROXY= \
    NO_PROXY=localhost,127.0.0.1 \
    http_proxy= \
    https_proxy= \
    all_proxy= \
    no_proxy=localhost,127.0.0.1

# 复制依赖文件
COPY package.json bun.lock ./

# 安装依赖
RUN bun install --frozen-lockfile

# 复制项目文件
COPY . .

# 构建 Node 运行时产物
RUN bun run build:node

# 确保 static 和 data 目录存在
RUN mkdir -p static data

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["bun", "run", "start:node"]
