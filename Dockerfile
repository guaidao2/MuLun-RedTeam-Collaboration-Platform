# 幕论红队协同平台 - 镜像构建
# 使用完整依赖安装（含 mcp），老服务器无需本机装 mcp/python 环境

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖层（利用镜像缓存，代码改动时不必重装依赖）
# 默认走清华 PyPI 镜像加速国内下载；海外/内网可 --build-arg 覆盖为官方源或自建源：
#   docker build --build-arg PIP_INDEX_URL=https://pypi.org/simple -t mulun-redteam .
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -i "${PIP_INDEX_URL}"

# 拷贝源码
COPY . .

# 运行时数据卷（sqlite db / 上传 / 报告 / api_token）
VOLUME ["/app/data"]

EXPOSE 5000

# 启动：见 docs/DEPLOY.md —— 生产需设置 REDTEAM_JWT_SECRET 才会监听 0.0.0.0
CMD ["python", "app.py"]
