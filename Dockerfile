ARG REGISTRY=dockerhub.arbat.dev
FROM ${REGISTRY}/python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install-deps
RUN playwright install firefox
COPY . .
ENTRYPOINT ["python", "main.py"]