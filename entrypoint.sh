#!/bin/bash

echo "🚀 Starting Browser Use WebUI container..."

# Set default values for required environment variables if not provided
export BROWSER_SERVICE_API_KEY="${BROWSER_SERVICE_API_KEY:-fallback-api-key-for-health-check}"
export CHROME_DEBUGGING_PORT="${CHROME_DEBUGGING_PORT:-9222}"

# Find a free port for Chrome remote debugging if default is taken
PORT=$CHROME_DEBUGGING_PORT
while netstat -tuln | grep -q ":$PORT " && [ $PORT -lt 9300 ]; do
  PORT=$((PORT+1))
done

export CHROME_DEBUGGING_PORT=$PORT
echo "✅ Using Chrome debugging port: $PORT"

# Ensure required directories exist
mkdir -p /app/data/chrome_data
mkdir -p /tmp/agent_history
mkdir -p /tmp/downloads
mkdir -p /var/log/supervisor

# Set proper permissions
chmod 755 /app/health_check.sh 2>/dev/null || true

echo "✅ Environment setup complete"
echo "🔧 Starting supervisord with all services..."

# Start supervisord in the foreground to properly manage child processes
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf
