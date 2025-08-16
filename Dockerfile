FROM dockerhub.arbat.dev/python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y \
    fonts-dejavu \
    fonts-unifont \
    libjpeg62-turbo \
    libwebp-dev \
    libvpx-dev \
    libicu-dev \
    libenchant-2-2 \
    libgdk-pixbuf-xlib-2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libasound2 \
    --no-install-recommends
RUN playwright install firefox
RUN playwright install chromium
COPY . .
ENTRYPOINT ["python", "main.py"]
