FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install-deps
RUN playwright install chromium
COPY . .
ENTRYPOINT ["python", "main.py"]