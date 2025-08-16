FROM dockerhub.arbat.dev/python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y \
    fonts-ubuntu \
    fonts-unifont \
    libjpeg62-turbo \
    libwebp7 \
    libvpx7 \
    libicu72 \
    libenchant-2-2 \
    libgdk-pixbuf-xlib-2.0-0 \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN playwright install firefox
RUN playwright install chromium
COPY . .
ENTRYPOINT ["python", "main.py"]
