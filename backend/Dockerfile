# P5E Docker 验证 v2 (2026-07-25): Playwright base 自带 Chromium + Node
# 选 Playwright 镜像 (chromium pre-installed + python + node) 避免 apt-get 装 chromium 卡 76MB 下载
FROM mcr.microsoft.com/playwright:v1.49.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com,files.pythonhosted.org,pypi.org \
    NODE_OPTIONS=--max-old-space-size=2048

# Playwright 的 Chromium 目录带版本号，建立稳定入口，避免升级基础镜像后路径失效。
RUN CHROME="$(find /ms-playwright -type f -path '*/chrome-linux/chrome' | head -n 1)" \
    && test -n "$CHROME" \
    && ln -sf "$CHROME" /usr/local/bin/fliki-chromium \
    && /usr/local/bin/fliki-chromium --version

# ffmpeg + libsqlite + fonts (chromium + node 20 already in base)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsqlite3-0 \
    fonts-noto-cjk fonts-noto-color-emoji \
    python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg sanity
RUN ffmpeg -version | head -1

WORKDIR /app

# Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --default-timeout=120 --retries=5 -r /app/requirements.txt

# Backend source
COPY . /app/

# Remotion deps (npm registry via mirror)
WORKDIR /app/workers/remotion-project
RUN npm config set registry https://registry.npmmirror.com \
    && PUPPETEER_SKIP_DOWNLOAD=true PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true npm ci --no-audit --no-fund 2>&1 | tail -10

# Remotion 运行时会执行 compositor，并写入 webpack 缓存；仅开放所需路径。
RUN find node_modules/@remotion/compositor-* -maxdepth 1 -type f \
      \( -name remotion -o -name ffmpeg -o -name ffprobe \) \
      -exec chmod +x {} + \
    && mkdir -p node_modules/.cache \
    && chown -R 1000:1000 node_modules/.cache

WORKDIR /app

# Remotion env (point to Playwright chromium)
ENV REMOTION_BROWSER_EXECUTABLE=/usr/local/bin/fliki-chromium \
    FFMPEG_EXECUTABLE=/usr/bin/ffmpeg \
    FLIKI_HOST=0.0.0.0 \
    FLIKI_PORT=8765 \
    FLIKI_DISK_PATH=/app/data

# P5E: .env 持久化密钥写到 /app/secrets (UID 1000 可写), 不污染 /app.
ENV FLIKI_SECRETS_PATH=/app/secrets/.fliki_provider_secrets.json

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8765/health || exit 1

# P5E: /app/data 与 /app/secrets 提供 UID 1000 可写的运行目录.
RUN mkdir -p /app/data /app/secrets && chown -R 1000:1000 /app/data /app/secrets
USER 1000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
