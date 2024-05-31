FROM dockerhub.arbat.dev
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install-deps
RUN playwright install firefox
COPY . .
ENTRYPOINT ["python", "main.py"]