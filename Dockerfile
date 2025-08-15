FROM --platform=linux/amd64 python:3.11-slim

# Set platform for multi-arch builds (Docker Buildx will set this)
ARG TARGETPLATFORM
ARG NODE_MAJOR=20

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
    fonts-unifont \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    dbus \
    xauth \
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
    vim \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install noVNC
RUN git clone https://github.com/novnc/noVNC.git /opt/novnc \
    && git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify \
    && ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Install Node.js using NodeSource PPA
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install nodejs -y \
    && rm -rf /var/lib/apt/lists/*

# Verify Node.js and npm installation (optional, but good for debugging)
RUN node -v && npm -v && npx -v

# Set up working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (system dependencies already installed above)
# Force reinstall to ensure version compatibility with browser-use
RUN playwright install --force chromium

# Copy the application code
COPY . .

# Fix Playwright paths for browser-use compatibility
COPY fix-playwright-paths.py /tmp/fix-playwright-paths.py
RUN python3 /tmp/fix-playwright-paths.py || echo "⚠️ Playwright path fix failed but continuing build"

# Patch browser-use to use Chrome channel as fallback
COPY patch-browser-channel.py /tmp/patch-browser-channel.py
RUN python3 /tmp/patch-browser-channel.py || echo "⚠️ Browser channel patch failed but continuing build"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV BROWSER_USE_LOGGING_LEVEL=info
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV CHROME_PATH=""
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV ANONYMIZED_TELEMETRY=false
ENV DISPLAY=:99
ENV RESOLUTION=1920x1080x24
ENV VNC_PASSWORD=vncpassword
ENV CHROME_PERSISTENT_SESSION=true
ENV RESOLUTION_WIDTH=1920
ENV RESOLUTION_HEIGHT=1080
ENV DOCKER_CONTAINER=true
ENV AWS_EXECUTION_ENV=true

# Copy and set up comprehensive health check
COPY health_check.sh /app/health_check.sh
RUN chmod +x /app/health_check.sh

# Add comprehensive health check with longer startup time for complex service dependencies
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD /app/health_check.sh
# Set up supervisor configuration
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy and setup entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose ports properly
EXPOSE 7788 6080 5901 8000 9222-9300 7789

# Use the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
