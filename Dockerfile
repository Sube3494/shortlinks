FROM oven/bun:1.3.13

WORKDIR /app

# 复制依赖文件
COPY package.json ./

# 安装依赖
RUN bun install

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
