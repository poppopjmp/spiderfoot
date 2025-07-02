#!/bin/bash
# SpiderFoot Microservice Startup Script

set -e

echo "Starting SpiderFoot Microservice Architecture..."
echo "=================================================="

# Function to check if a port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Port $port is already in use"
        return 1
    fi
    return 0
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1
    
    echo "Waiting for $name to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" >/dev/null 2>&1; then
            echo "$name is ready!"
            return 0
        fi
        echo "Attempt $attempt/$max_attempts: $name not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "Error: $name failed to start after $max_attempts attempts"
    return 1
}

# Check required ports
echo "Checking port availability..."
if ! check_port 8000; then exit 1; fi
if ! check_port 8001; then exit 1; fi
if ! check_port 8080; then exit 1; fi

# Create data directories
mkdir -p data/services

echo "Starting Service Discovery..."
python services/service_discovery.py \
    --host localhost \
    --port 8000 \
    --db-path data/services/service_discovery.db &
SERVICE_DISCOVERY_PID=$!

# Wait for service discovery to be ready
wait_for_service "http://localhost:8000/health" "Service Discovery"

echo "Starting Configuration Service..."
python services/config_service.py \
    --host localhost \
    --port 8001 \
    --db-path data/services/config_service.db \
    --migrate \
    --service-discovery-url http://localhost:8000 &
CONFIG_SERVICE_PID=$!

# Wait for configuration service to be ready
wait_for_service "http://localhost:8001/health" "Configuration Service"

echo "Starting API Gateway..."
python services/api_gateway.py \
    --host localhost \
    --port 8080 \
    --service-discovery-url http://localhost:8000 &
API_GATEWAY_PID=$!

# Wait for API gateway to be ready
wait_for_service "http://localhost:8080/health" "API Gateway"

echo ""
echo "=================================================="
echo "SpiderFoot Microservices are now running!"
echo "=================================================="
echo ""
echo "Service Discovery:    http://localhost:8000"
echo "Configuration Service: http://localhost:8001"
echo "API Gateway:          http://localhost:8080"
echo ""
echo "API Endpoints:"
echo "  Health Check:       http://localhost:8080/health"
echo "  Configuration:      http://localhost:8080/api/config"
echo "  Service Discovery:  http://localhost:8080/api/discovery/services"
echo ""
echo "Documentation:        http://localhost:8080/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping all services..."
    if [ ! -z "$API_GATEWAY_PID" ]; then
        kill $API_GATEWAY_PID 2>/dev/null || true
    fi
    if [ ! -z "$CONFIG_SERVICE_PID" ]; then
        kill $CONFIG_SERVICE_PID 2>/dev/null || true
    fi
    if [ ! -z "$SERVICE_DISCOVERY_PID" ]; then
        kill $SERVICE_DISCOVERY_PID 2>/dev/null || true
    fi
    echo "All services stopped."
    exit 0
}

# Set up signal handlers
trap cleanup INT TERM

# Wait for any background job to finish
wait