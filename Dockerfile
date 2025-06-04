FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y \
    chromium-driver \
    chromium \
    fonts-liberation \
    wget \
    curl \
    unzip \
    gnupg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=3001
ENV SELENIUM_HEADLESS=true

CMD ["python", "main_api.py"]
