FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV LIBVA_DRIVER_NAME=radeonsi

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libva2 \
    mesa-va-drivers \
    tzdata \
    vainfo \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY fonts/ ./fonts/

ENV CONFIG_PATH=/app/config.yaml

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
