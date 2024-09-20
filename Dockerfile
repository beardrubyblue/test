FROM dockerhub.arbat.dev/python:3.11
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y xvfb && rm -rf /var/lib/apt/lists/*
RUN pip install -r requirements.txt
RUN playwright install-deps
RUN playwright install firefox
RUN playwright install chromium
COPY . .
COPY Captcha-Solver-Chrome /app/Captcha-Solver-Chrome
ENTRYPOINT ["xvfb-run", "--auto-servernum", "--server-args='-screen 0 1920x1080x24'", "python", "main.py"]
