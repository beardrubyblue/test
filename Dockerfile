# As Scrapy runs on Python, I choose the official Python 3 Docker image.
FROM python:3.11
 
# Set the working directory to /usr/src/app.
WORKDIR /app
 
# Copy the file from the local host to the filesystem of the container at the working directory.
COPY requirements.txt ./
 
# Install Scrapy specified in requirements.txt.
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install && \
playwright install-deps
 
# Copy the project source code from the local host to the filesystem of the container at the working directory.
COPY . .