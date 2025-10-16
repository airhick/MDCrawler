FROM python:3.11-slim

# Force rebuild - v2.1.1 with Docker fixes
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CRAWLER_VERSION=2.1.1

WORKDIR /app

# Install system dependencies for lxml/bs4 and Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1.1 \
        libxslt1-dev \
        ca-certificates \
        # Playwright/Chromium dependencies
        wget \
        gnupg \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libatspi2.0-0 \
        libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browsers (dependencies already installed above)
RUN python -m playwright install chromium

# Copy application code (force rebuild on change)
ARG CACHEBUST=1
COPY app.py ./

# Verify critical files exist
RUN ls -la app.py requirements.txt && \
    python -c "import app; print('✓ app.py loads successfully')"

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]

