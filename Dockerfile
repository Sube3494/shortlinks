FROM node:20-slim

WORKDIR /app

# 安装 pnpm
RUN npm install -g pnpm

# 复制依赖文件
COPY package.json pnpm-lock.yaml* ./

# 安装依赖
RUN pnpm install

# 复制项目文件
COPY . .

# 构建 Node 运行时产物
RUN pnpm run build:node

# 确保 static 和 data 目录存在
RUN mkdir -p static data

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["pnpm", "run", "start:node"]
