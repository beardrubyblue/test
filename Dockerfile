FROM dockerhub.arbat.dev/python:3.11
ARG WORKDIR=/unireger
ENV WORKDIR=${WORKDIR}
WORKDIR $WORKDIR
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install-deps
RUN playwright install firefox
RUN playwright install chromium
COPY . .
COPY Captcha-Solver-Chrome /app/Captcha-Solver-Chrome
ENTRYPOINT ["python", "main.py"]
