# Multi-stage Docker build for M-Pesa Telegram Bot

# Stage 1: Builder stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/botuser/.local

# Copy application code
COPY --chown=botuser:botuser . .

# Create logs directory
RUN mkdir -p /app/logs && chown -R botuser:botuser /app/logs

# Switch to non-root user
USER botuser

# Add local bin to PATH
ENV PATH=/home/botuser/.local/bin:$PATH

# Expose port for FastAPI callback endpoint
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run the application
# Use callback_server.py for FastAPI callback server
# Use weekendvibe.py for bot with FastAPI and database
# Use mpesabotgig.py for simple version (testing only)
CMD ["uvicorn", "callback_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
