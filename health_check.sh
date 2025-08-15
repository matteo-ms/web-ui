#!/bin/bash

# Comprehensive health check script for AWS ELB
# This script prioritizes the most critical services for AWS health checks

set -e

echo "🏥 Starting health check..."

# Function to check if a service is responding with retry logic
check_service_with_retry() {
    local port=$1
    local path=$2
    local description=$3
    local max_retries=3
    local retry_delay=2
    
    echo "Checking $description on port $port..."
    
    for i in $(seq 1 $max_retries); do
        # Check if port is open
        if nc -z localhost $port; then
            echo "✅ Port $port is open for $description"
            
            # For HTTP services, check if they respond correctly
            if [ -n "$path" ]; then
                if curl -f -s -m 5 "http://localhost:$port$path" > /dev/null 2>&1; then
                    echo "✅ $description HTTP check passed"
                    return 0
                else
                    echo "⚠️  HTTP check failed for $description (attempt $i/$max_retries)"
                fi
            else
                echo "✅ $description is healthy (port check only)"
                return 0
            fi
        else
            echo "⚠️  Port $port is not open for $description (attempt $i/$max_retries)"
        fi
        
        if [ $i -lt $max_retries ]; then
            echo "Retrying in ${retry_delay}s..."
            sleep $retry_delay
        fi
    done
    
    echo "❌ $description failed after $max_retries attempts"
    return 1
}

# Priority 1: Check API server with health endpoint (most reliable)
if check_service_with_retry 7789 "/healthcheck" "API Server"; then
    echo "✅ Critical API server is healthy!"
else
    echo "❌ Critical API server health check failed"
    exit 1
fi

# Priority 2: Check main Gradio UI (what ELB typically checks)
if check_service_with_retry 7788 "" "Main Web UI"; then
    echo "✅ Main Web UI is responding!"
else
    echo "⚠️  Main Web UI not responding, but API server is healthy"
    # Don't exit here - API server being healthy is sufficient for basic functionality
fi

# Priority 3: Check supporting services (optional for basic functionality)
check_service_with_retry 6080 "/" "noVNC Web Interface" || echo "⚠️  noVNC not available but continuing..."
check_service_with_retry 5901 "" "VNC Server" || echo "⚠️  VNC Server not available but continuing..."

# Check if Chrome debugging port is accessible (optional)
if netstat -tuln | grep -q ":922[0-9] "; then
    echo "✅ Chrome debugging port is accessible"
else
    echo "⚠️  Chrome debugging port not found, but continuing..."
fi

echo "✅ Health check completed - essential services are running!"
exit 0 