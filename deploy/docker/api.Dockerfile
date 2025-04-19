# deploy/docker/api.Dockerfile
FROM python:3.9.22-slim-bullseye

WORKDIR /app

# 安装依赖
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY api/ /app/api/
COPY graph/ /app/graph/

# 创建上传目录
RUN mkdir -p /app/data/uploads

# 暴露端口
EXPOSE 8000

# 设置默认命令
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]