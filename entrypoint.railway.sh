#!/bin/bash

# Railway entrypoint for Browser Use WebUI with multiple services
set -e

echo "🚂 Starting Browser Use WebUI with multiple services on Railway..."

# Create VNC password directory and file
mkdir -p ~/.vnc
# Try vncpasswd first, fallback to manual creation
if command -v vncpasswd >/dev/null 2>&1; then
    echo "${VNC_PASSWORD:-vncpassword}" | vncpasswd -f > ~/.vnc/passwd
    chmod 600 ~/.vnc/passwd
else
    echo "⚠️  vncpasswd not found, creating password file manually"
    # Create a simple password file (less secure but functional)
    echo "${VNC_PASSWORD:-vncpassword}" > ~/.vnc/passwd
    chmod 600 ~/.vnc/passwd
fi

# Start Xvfb (virtual display)
echo "Starting virtual display..."
Xvfb :99 -screen 0 ${RESOLUTION:-1920x1080x24} -ac +extension GLX +render -noreset &
export DISPLAY=:99

# Wait for display to be ready
sleep 3

# Start VNC server
echo "Starting VNC server on port 5901..."
if command -v x11vnc >/dev/null 2>&1; then
    x11vnc -display :99 -forever -shared -rfbauth ~/.vnc/passwd -rfbport 5901 &
else
    echo "⚠️  x11vnc not found, skipping VNC server"
fi

# Start window manager
echo "Starting window manager..."
fluxbox &

# Start noVNC web interface on port 6080
echo "Starting noVNC web interface on port 6080..."
if [ -d "/opt/novnc" ]; then
    cd /opt/novnc && ./utils/novnc_proxy --vnc localhost:5901 --listen 0.0.0.0:6080 --web /opt/novnc &
else
    echo "⚠️  noVNC not found, skipping..."
fi

# Start persistent Chrome browser with remote debugging
echo "Starting Chrome browser with remote debugging on port 9222..."
mkdir -p /app/data/chrome_data
$(find /ms-browsers/chromium-*/chrome-linux -name chrome 2>/dev/null | head -1) \
    --no-sandbox \
    --user-data-dir=/app/data/chrome_data \
    --window-position=0,0 \
    --window-size=${RESOLUTION_WIDTH:-1920},${RESOLUTION_HEIGHT:-1080} \
    --start-maximized \
    --disable-dev-shm-usage \
    --disable-gpu \
    --disable-software-rasterizer \
    --no-first-run \
    --no-default-browser-check \
    --remote-debugging-port=9222 \
    --remote-debugging-address=0.0.0.0 \
    "data:text/html,<html><body><h1>Browser Ready</h1></body></html>" &

# Wait for services to initialize
sleep 5

# Use Railway's PORT environment variable for nginx, fallback to 80
export NGINX_PORT=${PORT:-80}
export GRADIO_SERVER_PORT=7788

echo "🌐 Starting WebUI on internal port $GRADIO_SERVER_PORT..."
echo "🖥️  VNC available on port 5901"
echo "🌍 noVNC web interface available on port 6080"
echo "🛠️  Chrome debugging available on port 9222"

# Start the WebUI in background
python webui.py --ip 127.0.0.1 --port $GRADIO_SERVER_PORT &

# Wait for WebUI to start
sleep 5

# Update nginx configuration to use Railway's port
sed -i "s/listen 80;/listen $NGINX_PORT;/" /etc/nginx/nginx.conf

echo "🔄 Starting nginx reverse proxy on port $NGINX_PORT..."
echo "📍 Access points:"
echo "   • Main UI: https://your-app.up.railway.app/"
echo "   • VNC Web: https://your-app.up.railway.app/vnc/"
echo "   • Chrome Debug: https://your-app.up.railway.app/debug/"

# Start nginx in foreground (main process)
exec nginx -g "daemon off;"
