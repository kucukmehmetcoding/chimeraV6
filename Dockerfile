# ChimeraBot Dockerfile - Optimized for Coolify Deployment
# Python 3.11 with TA-Lib support
# v6.0 - Percentage-based SL/TP System

# Use Python 3.11 slim for smaller image size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for TA-Lib and compilation (optimized for Coolify)
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    gcc \
    g++ \
    make \
    libc-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install TA-Lib C library (optimized for build caching)
RUN wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make -j$(nproc) && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz && \
    ldconfig

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel Cython

# Install numpy first (TA-Lib dependency)
RUN pip install --no-cache-dir numpy==1.24.3

# Install TA-Lib Python wrapper (optimized)
RUN pip install --no-cache-dir --no-binary :all: TA-Lib

# Copy requirements first for better caching
COPY requirements.txt .

# Install all dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/data/backups

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Run DB migrations (ensure schema is up to date)
# || true ensures build continues even if migration fails
RUN python3 migrations/add_advanced_risk_columns.py || true
RUN python3 migrations/add_amount_column.py || true

# Clean up build dependencies to reduce image size
RUN apt-get remove -y build-essential gcc g++ make python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Run the bot
CMD ["python", "-m", "src.main_orchestrator"]
