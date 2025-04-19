# deploy/docker/parser.Dockerfile
FROM python:3.9.22-slim-bullseye

WORKDIR /app

# 安装依赖
COPY parser/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY parser/ /app/parser/

# 创建数据和模型目录
RUN mkdir -p /app/data /app/models

# 设置默认命令
CMD ["python", "-m", "parser.main"]




