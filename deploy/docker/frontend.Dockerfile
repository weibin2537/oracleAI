# deploy/docker/frontend.Dockerfile
FROM node:16-alpine as build

WORKDIR /app

# 安装依赖
COPY frontend/package*.json ./
RUN npm install

# 复制代码
COPY frontend/ .

# 构建前端
RUN npm run build

# 生产环境
FROM nginx:alpine

# 复制构建产物
COPY --from=build /app/dist /usr/share/nginx/html

# 复制Nginx配置
COPY deploy/docker/nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"]