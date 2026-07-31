# Fliki 视频制作还原 - Backend Dockerfile
# For remote cloud renderer + Lambda integration (rev18 stage C)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1

# ffmpeg + curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl ca-certificates wget gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google.gpg \
    && sh -c 'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt
COPY backend /app/backend
COPY scripts /app/scripts

ENV PYTHONPATH=/app/backend
ENV REMOTION_BROWSER_EXECUTABLE=/usr/bin/google-chrome-stable
ENV RENDER_QUEUE_MAX_CONCURRENT=3
EXPOSE 5181
WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5181"]