#!/bin/bash

# Railway entrypoint for Browser Use WebUI
set -e

echo "🚂 Starting Browser Use WebUI on Railway..."

# Start Xvfb (virtual display)
echo "Starting virtual display..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
export DISPLAY=:99

# Wait for display to be ready
sleep 2

# Start VNC server (optional, for debugging)
echo "Starting VNC server..."
x11vnc -display :99 -forever -usepw -create -rfbport 5900 &

# Start window manager
echo "Starting window manager..."
fluxbox &

# Wait a moment for everything to initialize
sleep 3

# Use Railway's PORT environment variable, fallback to 7788
export GRADIO_SERVER_PORT=${PORT:-7788}

echo "🌐 Starting WebUI on port $GRADIO_SERVER_PORT..."

# Start the WebUI directly (no supervisor needed on Railway)
exec python webui.py --ip 0.0.0.0 --port $GRADIO_SERVER_PORT
