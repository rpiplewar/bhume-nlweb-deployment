# Multi-stage build for optimization
FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    pip install --no-cache-dir --upgrade pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY code/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.13-slim

# Install security updates only
RUN apt-get update &&\
   apt-get install -y --no-install-recommends --only-upgrade \
       $(apt-get --just-print upgrade | grep "^Inst" | grep -i securi | awk '{print $2}') &&\
   apt-get clean &&\
   rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
RUN groupadd -r nlweb && \
    useradd -r -g nlweb -d /app -s /bin/bash nlweb && \
    chown -R nlweb:nlweb /app

# Create directories
RUN mkdir -p /app/data && \
    mkdir -p /app/logs && \
    chown -R nlweb:nlweb /app/data && \
    chown -R nlweb:nlweb /app/logs

# Copy Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set PATH to include local bin
ENV PATH="/usr/local/bin:/app/.local/bin:$PATH"

# Copy application code
COPY code/ /app/
COPY static/ /app/static/
COPY data/ /app/data/
COPY startup.sh /app/

# Set environment variables
ENV NLWEB_OUTPUT_DIR=/app
ENV PYTHONPATH=/app
ENV PATH="/usr/local/bin:/app/.local/bin:$PATH"

# Fix permissions and make startup.sh executable
RUN chown -R nlweb:nlweb /app && \
    chmod +x /app/startup.sh

# Switch to non-root user
USER nlweb

# Expose port
EXPOSE 8080

# Use startup.sh for runtime data loading
CMD ["./startup.sh"]
