FROM --platform=linux/amd64 python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    netcat-traditional \
    gnupg \
    curl \
    unzip \
    xvfb \
    libgconf-2-4 \
    libxss1 \
    libnss3 \
    libnspr4 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    fonts-liberation \
    dbus \
    xauth \
    xvfb \
    x11vnc \
    tigervnc-tools \
    supervisor \
    net-tools \
    procps \
    git \
    python3-numpy \
    fontconfig \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    && rm -rf /var/lib/apt/lists/*

# Install noVNC
RUN git clone https://github.com/novnc/noVNC.git /opt/novnc \
    && git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify \
    && ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Set platform for AMD64 compatibility
ARG TARGETPLATFORM=linux/amd64

# Set up working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers with system dependencies
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install playwright && \
    playwright install --with-deps chromium

# Copy the application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV BROWSER_USE_LOGGING_LEVEL=info
ENV CHROME_PATH=/ms-playwright/chromium-*/chrome-linux/chrome
ENV ANONYMIZED_TELEMETRY=false
ENV DISPLAY=:99
ENV RESOLUTION=1920x1080x24
ENV VNC_PASSWORD=vncpassword
ENV CHROME_PERSISTENT_SESSION=true
ENV RESOLUTION_WIDTH=1920
ENV RESOLUTION_HEIGHT=1080
ENV DOCKER_CONTAINER=true
ENV AWS_EXECUTION_ENV=true

# Create startup script
RUN echo '#!/bin/bash\n\
# Find a free port for Chrome remote debugging\n\
PORT=9222\n\
while netstat -tuln | grep -q ":$PORT " && [ $PORT -lt 9300 ]; do\n\
  PORT=$((PORT+1))\n\
done\n\
\n\
# Update environment variable with the free port\n\
export CHROME_DEBUGGING_PORT=$PORT\n\
echo "Using Chrome debugging port: $PORT"\n\
\n\
exec "$@"\n' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Add a simple health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD nc -z localhost 7788 || exit 1

# Set up supervisor configuration
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose ports properly
EXPOSE 7788 6080 5901 8000 9222-9300 7789

# Use the entrypoint script and shell form command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
