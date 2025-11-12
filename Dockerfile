# ChimeraBot Dockerfile - Coolify Deployment
# Python 3.11 with TA-Lib support

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for TA-Lib and compilation
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    git \
    gcc \
    g++ \
    make \
    libc-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz && \
    ldconfig

# Upgrade pip and install build tools first
RUN pip install --upgrade pip setuptools wheel Cython

# Install numpy first (TA-Lib dependency)
RUN pip install --no-cache-dir numpy==1.24.3

# Install TA-Lib Python wrapper (try with verbose output)
RUN pip install --no-cache-dir --no-binary :all: TA-Lib || \
    (echo "First attempt failed, trying with verbose..." && \
     pip install --no-cache-dir --verbose TA-Lib)

# Install core dependencies
RUN pip install --no-cache-dir python-binance==1.0.32
RUN pip install --no-cache-dir pandas==2.1.4

# Install remaining dependencies
RUN pip install --no-cache-dir SQLAlchemy==2.0.23 python-dotenv==1.0.0 PyYAML==6.0.1
RUN pip install --no-cache-dir schedule==1.2.1 tenacity==8.2.3 retry==0.9.2
RUN pip install --no-cache-dir python-telegram-bot==21.0 requests==2.31.0
RUN pip install --no-cache-dir feedparser==6.0.11 beautifulsoup4==4.12.3 lxml==5.1.0
RUN pip install --no-cache-dir praw==7.7.1 pytrends==4.9.2
RUN pip install --no-cache-dir google-generativeai==0.3.2
RUN pip install --no-cache-dir aiohttp==3.9.1 websockets==12.0
RUN pip install --no-cache-dir pycryptodome==3.19.0 tqdm==4.66.1
# Re-enable VADER (required for sentiment); ensure consistent with requirements.txt
RUN pip install --no-cache-dir vaderSentiment==3.3.2

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Make entrypoint script executable (already copied with COPY . .)
RUN chmod +x /app/docker-entrypoint.sh

# Run DB migrations (ensure schema is up to date)
# || true ensures build continues even if migration fails
RUN python3 migrations/add_advanced_risk_columns.py || true
RUN python3 migrations/add_amount_column.py || true

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Accept build args from Coolify and set as ENV
ARG ENABLE_REAL_TRADING=false
ARG BINANCE_API_KEY
ARG BINANCE_SECRET_KEY
ARG TELEGRAM_BOT_TOKEN
ARG TELEGRAM_CHAT_ID
ARG BINANCE_TESTNET=False

ENV ENABLE_REAL_TRADING=${ENABLE_REAL_TRADING}
ENV BINANCE_API_KEY=${BINANCE_API_KEY}
ENV BINANCE_SECRET_KEY=${BINANCE_SECRET_KEY}
ENV TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
ENV TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
ENV BINANCE_TESTNET=${BINANCE_TESTNET}

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Run the bot
CMD ["python", "-m", "src.main_orchestrator"]
