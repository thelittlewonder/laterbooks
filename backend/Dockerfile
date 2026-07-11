FROM python:3.11-slim-bookworm

WORKDIR /app

# System libraries for PaddleOCR / OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium + OS dependencies
RUN playwright install --with-deps chromium

COPY app ./app

ENV PYTHONUNBUFFERED=1
ENV UPLOAD_DIR=/tmp/uploads

RUN mkdir -p /tmp/uploads

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
