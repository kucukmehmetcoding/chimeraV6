# ChimeraBot Dockerfile - Coolify Deployment
# Python 3.11 with TA-Lib support

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for TA-Lib
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and install build tools first
RUN pip install --upgrade pip setuptools wheel

# Install core dependencies separately to identify issues
RUN pip install --no-cache-dir python-binance==1.0.32
RUN pip install --no-cache-dir pandas==2.1.4 numpy==1.24.3
RUN pip install --no-cache-dir TA-Lib==0.4.28

# Install remaining dependencies
RUN pip install --no-cache-dir SQLAlchemy==2.0.23 python-dotenv==1.0.0 PyYAML==6.0.1
RUN pip install --no-cache-dir schedule==1.2.1 tenacity==8.2.3 retry==0.9.2
RUN pip install --no-cache-dir python-telegram-bot==21.0 requests==2.31.0
RUN pip install --no-cache-dir feedparser==6.0.11 beautifulsoup4==4.12.3 lxml==5.1.0
RUN pip install --no-cache-dir praw==7.7.1 pytrends==4.9.2
RUN pip install --no-cache-dir google-generativeai==0.3.2
RUN pip install --no-cache-dir aiohttp==3.9.1 websockets==12.0
RUN pip install --no-cache-dir pycryptodome==3.19.0 tqdm==4.66.1

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the bot
CMD ["python", "-m", "src.main_orchestrator"]
