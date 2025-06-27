#!/bin/bash

# SpiderFoot Production Deployment Script
# This script helps deploy SpiderFoot in production with all necessary services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Copying from .env.example..."
    cp .env.example .env
    print_warning "Please edit .env file with your configuration before proceeding!"
    echo "Required changes:"
    echo "  - Set DOMAIN_NAME"
    echo "  - Change all default passwords"
    echo "  - Set data paths for production"
    echo "  - Configure SSL certificate paths"
    exit 1
fi

# Load environment variables
source .env

# Validate required environment variables
validate_env() {
    print_status "Validating environment configuration..."
    
    if [ "${POSTGRES_PASSWORD}" == "changeme_secure_postgres_password" ]; then
        print_error "Please change the default PostgreSQL password in .env"
        exit 1
    fi
    
    if [ "${ELASTIC_PASSWORD}" == "changeme_secure_elastic_password" ]; then
        print_error "Please change the default Elasticsearch password in .env"
        exit 1
    fi
    
    if [ "${DOMAIN_NAME}" == "your-domain.com" ]; then
        print_error "Please set your domain name in .env"
        exit 1
    fi
    
    print_success "Environment validation passed"
}

# Create necessary directories
create_directories() {
    print_status "Creating data directories..."
    
    mkdir -p "${DATA_PATH}/spiderfoot"
    mkdir -p "${DATA_PATH}/postgres"
    mkdir -p "${DATA_PATH}/elasticsearch"
    mkdir -p "${LOGS_PATH}/spiderfoot"
    mkdir -p "${BACKUP_PATH}/postgres"
    mkdir -p "${CERTS_PATH}"
    
    # Set appropriate permissions
    chmod 755 "${DATA_PATH}"
    chmod 755 "${LOGS_PATH}"
    chmod 755 "${BACKUP_PATH}"
    chmod 700 "${CERTS_PATH}"
    
    print_success "Directories created successfully"
}

# Generate SSL certificates if they don't exist
generate_certificates() {
    print_status "Checking SSL certificates..."
    
    if [ ! -f "${CERTS_PATH}/spiderfoot.crt" ] || [ ! -f "${CERTS_PATH}/spiderfoot.key" ]; then
        print_warning "SSL certificates not found. Generating self-signed certificates..."
        
        # Generate private key
        openssl genrsa -out "${CERTS_PATH}/spiderfoot.key" 4096
        
        # Generate certificate signing request
        openssl req -new -key "${CERTS_PATH}/spiderfoot.key" -out "${CERTS_PATH}/spiderfoot.csr" -subj "/CN=${DOMAIN_NAME}/O=SpiderFoot/C=US"
        
        # Generate self-signed certificate
        openssl x509 -req -days 365 -in "${CERTS_PATH}/spiderfoot.csr" -signkey "${CERTS_PATH}/spiderfoot.key" -out "${CERTS_PATH}/spiderfoot.crt"
        
        # Create CA bundle (for self-signed, same as cert)
        cp "${CERTS_PATH}/spiderfoot.crt" "${CERTS_PATH}/ca-bundle.crt"
        
        # Set permissions
        chmod 600 "${CERTS_PATH}/spiderfoot.key"
        chmod 644 "${CERTS_PATH}/spiderfoot.crt"
        
        print_success "Self-signed certificates generated"
        print_warning "For production, replace with certificates from a trusted CA"
    else
        print_success "SSL certificates found"
    fi
}

# Deploy the application
deploy() {
    print_status "Deploying SpiderFoot production stack..."
    
    # Pull latest images
    docker-compose -f docker-compose-prod.yml pull
    
    # Start core services
    print_status "Starting core services (PostgreSQL, Elasticsearch, Redis)..."
    docker-compose -f docker-compose-prod.yml up -d postgres elasticsearch redis
    
    # Wait for services to be healthy
    print_status "Waiting for services to be ready..."
    sleep 30
    
    # Start application and reverse proxy
    print_status "Starting SpiderFoot application and Nginx..."
    docker-compose -f docker-compose-prod.yml up -d spiderfoot nginx
    
    # Start monitoring stack if requested
    if [ "${1}" == "--monitoring" ]; then
        print_status "Starting monitoring stack..."
        docker-compose -f docker-compose-prod.yml --profile monitoring up -d
    fi
    
    print_success "Deployment completed!"
}

# Health check
health_check() {
    print_status "Performing health checks..."
    
    # Check if containers are running
    if docker-compose -f docker-compose-prod.yml ps | grep -q "Up"; then
        print_success "Containers are running"
    else
        print_error "Some containers are not running"
        docker-compose -f docker-compose-prod.yml ps
        exit 1
    fi
    
    # Check if SpiderFoot is responding
    sleep 10
    if curl -k -f "https://localhost/health" >/dev/null 2>&1; then
        print_success "SpiderFoot is responding to HTTPS requests"
    else
        print_warning "SpiderFoot health check failed (this might be normal during startup)"
    fi
}

# Show deployment information
show_info() {
    print_success "SpiderFoot Production Deployment Complete!"
    echo ""
    echo "Access URLs:"
    echo "  - SpiderFoot: https://${DOMAIN_NAME}"
    echo "  - Health Check: https://${DOMAIN_NAME}/health"
    
    if [ "${1}" == "--monitoring" ]; then
        echo "  - Grafana: https://grafana.${DOMAIN_NAME}"
        echo "  - Kibana: https://kibana.${DOMAIN_NAME}"
    fi
    
    echo ""
    echo "Management Commands:"
    echo "  - View logs: docker-compose -f docker-compose-prod.yml logs -f"
    echo "  - Stop services: docker-compose -f docker-compose-prod.yml down"
    echo "  - Restart services: docker-compose -f docker-compose-prod.yml restart"
    
    if [ "${1}" == "--monitoring" ]; then
        echo "  - Start monitoring: docker-compose -f docker-compose-prod.yml --profile monitoring up -d"
    fi
    
    echo ""
    echo "Backup Commands:"
    echo "  - Manual backup: docker-compose -f docker-compose-prod.yml --profile backup run --rm postgres-backup"
    echo ""
    echo "Default Credentials (CHANGE THESE):"
    echo "  - Grafana: admin / ${GRAFANA_PASSWORD}"
    echo "  - Kibana: elastic / ${ELASTIC_PASSWORD}"
}

# Main deployment flow
main() {
    print_status "Starting SpiderFoot Production Deployment"
    
    validate_env
    create_directories
    generate_certificates
    deploy "$1"
    health_check
    show_info "$1"
}

# Parse command line arguments
case "$1" in
    --monitoring)
        main --monitoring
        ;;
    --help|-h)
        echo "SpiderFoot Production Deployment Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --monitoring    Deploy with monitoring stack (Grafana, Kibana, Prometheus)"
        echo "  --help, -h      Show this help message"
        echo ""
        echo "Prerequisites:"
        echo "  1. Copy .env.example to .env and configure it"
        echo "  2. Ensure Docker and Docker Compose are installed"
        echo "  3. Ensure sufficient disk space for data directories"
        ;;
    *)
        main
        ;;
esac
