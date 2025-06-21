# SpiderFoot Production Deployment Script for Windows
# This script helps deploy SpiderFoot in production with all necessary services

param(
    [switch]$Monitoring,
    [switch]$Help
)

# Function to print colored output
function Write-Status {
    param($Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param($Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param($Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check if .env file exists
function Test-Environment {
    if (-not (Test-Path ".env")) {
        Write-Warning ".env file not found. Copying from .env.example..."
        Copy-Item ".env.example" ".env"
        Write-Warning "Please edit .env file with your configuration before proceeding!"
        Write-Host "Required changes:"
        Write-Host "  - Set DOMAIN_NAME"
        Write-Host "  - Change all default passwords"
        Write-Host "  - Set data paths for production"
        Write-Host "  - Configure SSL certificate paths"
        exit 1
    }
}

# Load environment variables from .env file
function Load-Environment {
    Write-Status "Loading environment configuration..."
    
    $envVars = @{}
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $envVars[$matches[1]] = $matches[2]
        }
    }
    
    return $envVars
}

# Validate required environment variables
function Test-EnvironmentVariables {
    param($EnvVars)
    
    Write-Status "Validating environment configuration..."
    
    if ($EnvVars["POSTGRES_PASSWORD"] -eq "changeme_secure_postgres_password") {
        Write-Error "Please change the default PostgreSQL password in .env"
        exit 1
    }
    
    if ($EnvVars["ELASTIC_PASSWORD"] -eq "changeme_secure_elastic_password") {
        Write-Error "Please change the default Elasticsearch password in .env"
        exit 1
    }
    
    if ($EnvVars["DOMAIN_NAME"] -eq "your-domain.com") {
        Write-Error "Please set your domain name in .env"
        exit 1
    }
    
    Write-Success "Environment validation passed"
}

# Create necessary directories
function New-DataDirectories {
    param($EnvVars)
    
    Write-Status "Creating data directories..."
    
    $directories = @(
        "$($EnvVars["DATA_PATH"])/spiderfoot",
        "$($EnvVars["DATA_PATH"])/postgres",
        "$($EnvVars["DATA_PATH"])/elasticsearch",
        "$($EnvVars["LOGS_PATH"])/spiderfoot",
        "$($EnvVars["BACKUP_PATH"])/postgres",
        $EnvVars["CERTS_PATH"]
    )
    
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    Write-Success "Directories created successfully"
}

# Generate SSL certificates if they don't exist (requires OpenSSL)
function New-SSLCertificates {
    param($EnvVars)
    
    Write-Status "Checking SSL certificates..."
    
    $certPath = $EnvVars["CERTS_PATH"]
    $domainName = $EnvVars["DOMAIN_NAME"]
    
    if (-not (Test-Path "$certPath/spiderfoot.crt") -or -not (Test-Path "$certPath/spiderfoot.key")) {
        Write-Warning "SSL certificates not found."
        
        # Check if OpenSSL is available
        try {
            openssl version | Out-Null
            Write-Status "Generating self-signed certificates with OpenSSL..."
            
            # Generate private key
            & openssl genrsa -out "$certPath/spiderfoot.key" 4096
            
            # Generate certificate signing request
            & openssl req -new -key "$certPath/spiderfoot.key" -out "$certPath/spiderfoot.csr" -subj "/CN=$domainName/O=SpiderFoot/C=US"
            
            # Generate self-signed certificate
            & openssl x509 -req -days 365 -in "$certPath/spiderfoot.csr" -signkey "$certPath/spiderfoot.key" -out "$certPath/spiderfoot.crt"
            
            # Create CA bundle
            Copy-Item "$certPath/spiderfoot.crt" "$certPath/ca-bundle.crt"
            
            Write-Success "Self-signed certificates generated"
            Write-Warning "For production, replace with certificates from a trusted CA"
        }
        catch {
            Write-Warning "OpenSSL not found. Please install OpenSSL or manually place certificates in $certPath"
            Write-Host "Required files:"
            Write-Host "  - spiderfoot.crt"
            Write-Host "  - spiderfoot.key"
            Write-Host "  - ca-bundle.crt"
        }
    }
    else {
        Write-Success "SSL certificates found"
    }
}

# Deploy the application
function Start-Deployment {
    param($WithMonitoring)
    
    Write-Status "Deploying SpiderFoot production stack..."
    
    # Pull latest images
    Write-Status "Pulling latest Docker images..."
    & docker-compose -f docker-compose-prod.yml pull
    
    # Start core services
    Write-Status "Starting core services (PostgreSQL, Elasticsearch, Redis)..."
    & docker-compose -f docker-compose-prod.yml up -d postgres elasticsearch redis
    
    # Wait for services to be healthy
    Write-Status "Waiting for services to be ready..."
    Start-Sleep -Seconds 30
    
    # Start application and reverse proxy
    Write-Status "Starting SpiderFoot application and Nginx..."
    & docker-compose -f docker-compose-prod.yml up -d spiderfoot nginx
    
    # Start monitoring stack if requested
    if ($WithMonitoring) {
        Write-Status "Starting monitoring stack..."
        & docker-compose -f docker-compose-prod.yml --profile monitoring up -d
    }
    
    Write-Success "Deployment completed!"
}

# Health check
function Test-Deployment {
    Write-Status "Performing health checks..."
    
    # Check if containers are running
    $runningContainers = & docker-compose -f docker-compose-prod.yml ps --format json | ConvertFrom-Json
    if ($runningContainers) {
        Write-Success "Containers are running"
    }
    else {
        Write-Error "Some containers are not running"
        & docker-compose -f docker-compose-prod.yml ps
        exit 1
    }
    
    # Check if SpiderFoot is responding
    Start-Sleep -Seconds 10
    try {
        $response = Invoke-WebRequest -Uri "https://localhost/health" -SkipCertificateCheck -ErrorAction Stop
        Write-Success "SpiderFoot is responding to HTTPS requests"
    }
    catch {
        Write-Warning "SpiderFoot health check failed (this might be normal during startup)"
    }
}

# Show deployment information
function Show-DeploymentInfo {
    param($EnvVars, $WithMonitoring)
    
    Write-Success "SpiderFoot Production Deployment Complete!"
    Write-Host ""
    Write-Host "Access URLs:"
    Write-Host "  - SpiderFoot: https://$($EnvVars["DOMAIN_NAME"])"
    Write-Host "  - Health Check: https://$($EnvVars["DOMAIN_NAME"])/health"
    
    if ($WithMonitoring) {
        Write-Host "  - Grafana: https://grafana.$($EnvVars["DOMAIN_NAME"])"
        Write-Host "  - Kibana: https://kibana.$($EnvVars["DOMAIN_NAME"])"
    }
    
    Write-Host ""
    Write-Host "Management Commands:"
    Write-Host "  - View logs: docker-compose -f docker-compose-prod.yml logs -f"
    Write-Host "  - Stop services: docker-compose -f docker-compose-prod.yml down"
    Write-Host "  - Restart services: docker-compose -f docker-compose-prod.yml restart"
    
    if ($WithMonitoring) {
        Write-Host "  - Start monitoring: docker-compose -f docker-compose-prod.yml --profile monitoring up -d"
    }
    
    Write-Host ""
    Write-Host "Backup Commands:"
    Write-Host "  - Manual backup: docker-compose -f docker-compose-prod.yml --profile backup run --rm postgres-backup"
    Write-Host ""
    Write-Host "Default Credentials (CHANGE THESE):"
    Write-Host "  - Grafana: admin / $($EnvVars["GRAFANA_PASSWORD"])"
    Write-Host "  - Kibana: elastic / $($EnvVars["ELASTIC_PASSWORD"])"
}

# Show help information
function Show-Help {
    Write-Host "SpiderFoot Production Deployment Script for Windows"
    Write-Host ""
    Write-Host "Usage: .\deploy-production.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Monitoring     Deploy with monitoring stack (Grafana, Kibana, Prometheus)"
    Write-Host "  -Help           Show this help message"
    Write-Host ""
    Write-Host "Prerequisites:"
    Write-Host "  1. Copy .env.example to .env and configure it"
    Write-Host "  2. Ensure Docker Desktop is installed and running"
    Write-Host "  3. Ensure sufficient disk space for data directories"
    Write-Host "  4. Install OpenSSL for certificate generation (optional)"
}

# Main deployment flow
function Start-Main {
    param($WithMonitoring)
    
    Write-Status "Starting SpiderFoot Production Deployment"
    
    Test-Environment
    $envVars = Load-Environment
    Test-EnvironmentVariables -EnvVars $envVars
    New-DataDirectories -EnvVars $envVars
    New-SSLCertificates -EnvVars $envVars
    Start-Deployment -WithMonitoring $WithMonitoring
    Test-Deployment
    Show-DeploymentInfo -EnvVars $envVars -WithMonitoring $WithMonitoring
}

# Main script logic
if ($Help) {
    Show-Help
}
else {
    Start-Main -WithMonitoring $Monitoring
}
