# Installation Guide

## System Requirements

### Minimum Requirements
- **Python**: 3.7 or higher (Python 3.9+ recommended)
- **Operating System**: Linux, macOS, or Windows
- **Memory**: 512 MB RAM (2 GB+ recommended for large scans)
- **Storage**: 1 GB available disk space
- **Network**: Internet connection for module functionality

### Recommended Requirements
- **Python**: 3.9 or higher
- **Memory**: 4 GB RAM or more
- **Storage**: 10 GB available disk space
- **CPU**: Multi-core processor for concurrent scanning

## Installation Methods

### Method 1: Latest Release (Recommended)

Clone the repository and install:

```bash
# Clone repository
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot

# Install dependencies
pip3 install -r requirements.txt

# Start SpiderFoot web interface
python3 sf.py -l 127.0.0.1:5001
```

### Method 2: Development Setup

For development or latest features:

```bash
# Clone repository
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot

# Create virtual environment (recommended)
python3 -m venv spiderfoot-env
source spiderfoot-env/bin/activate  # On Windows: spiderfoot-env\Scripts\activate

# Install dependencies
pip3 install -r requirements.txt

# Start SpiderFoot
python3 sf.py -l 127.0.0.1:5001
```

### Method 3: Docker Installation

#### Using Docker

```bash
# Build and run with Docker
docker build -t spiderfoot .
docker run -p 5001:5001 spiderfoot

# Or use docker-compose
docker-compose up

# Run with persistent data
docker run -p 5001:5001 -v $(pwd)/data:/var/lib/spiderfoot spiderfoot
```

#### Using Docker Compose

The repository includes several docker-compose configurations:

```bash
# Development environment
docker-compose -f docker-compose-dev.yml up

# Production environment  
docker-compose -f docker-compose-prod.yml up

# Default configuration
docker-compose up
```

## Platform-Specific Instructions

### Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install Python and pip
sudo apt install python3 python3-pip python3-venv git

# Install SpiderFoot
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot
pip3 install -r requirements.txt
```

### CentOS/RHEL/Fedora

```bash
# Install Python and dependencies
sudo dnf install python3 python3-pip git  # Fedora
# sudo yum install python3 python3-pip git  # CentOS/RHEL

# Clone and install SpiderFoot
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot
pip3 install -r requirements.txt
```

### macOS

```bash
# Install Python (if not already installed)
brew install python3 git

# Clone and install SpiderFoot
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot
pip3 install -r requirements.txt
```

### Windows

1. **Install Python 3.7+** from [python.org](https://python.org)
2. **Install Git** from [git-scm.com](https://git-scm.com)
3. **Open Command Prompt or PowerShell**:

```cmd
# Clone repository
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot

# Install dependencies
pip install -r requirements.txt

# Start SpiderFoot
python sf.py -l 127.0.0.1:5001
```

## Verification

After installation, verify SpiderFoot is working:

```bash
# Check version
python3 sf.py --version

# List available modules
python3 sf.py -M

# Start web interface
python3 sf.py -l 127.0.0.1:5001
```

Open your browser to `http://127.0.0.1:5001` to access the web interface.

## Common Installation Issues

### Permission Errors
```bash
# Use user installation
pip3 install --user -r requirements.txt

# Or use virtual environment (recommended)
python3 -m venv spiderfoot-env
source spiderfoot-env/bin/activate
pip install -r requirements.txt
```

### Port Already in Use
```bash
# Use different port
python3 sf.py -l 127.0.0.1:5002

# Check what's using port 5001
netstat -tlnp | grep 5001  # Linux/macOS
netstat -ano | findstr 5001  # Windows
```

### Python Module Errors
```bash
# Update pip
pip3 install --upgrade pip

# Install specific module
pip3 install requests cherrypy

# Clear pip cache
pip3 cache purge
```

## Next Steps

- **Basic Usage**: See [Quick Start Guide](quickstart.md)
- **Configuration**: See [Configuration Guide](configuration.md)  
- **Web Interface**: See [Web Interface Guide](web_interface.md)
- **Command Line**: See [CLI Usage Guide](cli_usage.md)
# or
sudo yum install python3 python3-pip git  # CentOS/RHEL

# Install SpiderFoot
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot
pip3 install -r requirements.txt
```

### macOS

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python3 git

# Install SpiderFoot
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot
pip3 install -r requirements.txt
```

### Windows

1. **Install Python 3.9+** from [python.org](https://www.python.org/downloads/)
2. **Install Git** from [git-scm.com](https://git-scm.com/download/win)
3. **Open Command Prompt or PowerShell**

```cmd
# Clone repository
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot

# Install dependencies
pip install -r requirements.txt

# Start SpiderFoot
python sf.py -l 127.0.0.1:5001
```

## Post-Installation Setup

### Initial Configuration

1. **Access Web Interface**: Open http://127.0.0.1:5001 in your browser
2. **Configure Settings**: Navigate to Settings to configure modules and API keys
3. **Test Installation**: Run a basic scan to verify functionality

### API Keys Configuration

Many SpiderFoot modules require API keys for external services:

```python
# Example API key configuration
api_keys = {
    'virustotal': 'your_virustotal_api_key',
    'shodan': 'your_shodan_api_key',
    'threatcrowd': '',  # No API key required
    'passivetotal': 'your_passivetotal_api_key'
}
```

Configure API keys through:
- **Web Interface**: Settings → Module Settings
- **Configuration File**: Edit `spiderfoot.conf`
- **Environment Variables**: Set `SPIDERFOOT_API_KEYS`

Ready to start? Check out the [Quick Start Guide](quickstart.md)!
3. **Test Installation**: Run a basic scan to verify functionality

### API Keys Configuration

Many SpiderFoot modules require API keys for external services:

```python
# Example API key configuration
api_keys = {
    'virustotal': 'your_virustotal_api_key',
    'shodan': 'your_shodan_api_key',
    'threatcrowd': '',  # No API key required
    'passivetotal': 'your_passivetotal_api_key'
}
```

Configure API keys through:
- **Web Interface**: Settings → Module Settings
- **Configuration File**: Edit `spiderfoot.conf`
- **Environment Variables**: Set `SPIDERFOOT_API_KEYS`

### Database Initialization

SpiderFoot automatically creates its SQLite database on first run. For custom database locations:

```bash
# Specify custom database location
python sf.py -l 127.0.0.1:5001 -d /path/to/custom/database.db
```

## Verification

### Test Basic Functionality

```bash
# Test CLI functionality
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Test web interface
curl http://127.0.0.1:5001/
```

### Test Workflow Functionality

```bash
# Test workspace creation
python sfworkflow.py create-workspace "Test Workspace"

# Test target addition
python sfworkflow.py add-target <workspace_id> example.com --type DOMAIN_NAME

# Test multi-target scanning
python sfworkflow.py multi-scan <workspace_id> --modules sfp_dnsresolve
```

## Troubleshooting

### Common Installation Issues

#### Python Version Issues
```bash
# Check Python version
python3 --version

# If using wrong Python version
which python3
/usr/bin/python3 -V
```

#### Dependency Installation Failures
```bash
# Upgrade pip
pip3 install --upgrade pip

# Install specific dependency
pip3 install requests

# Clear pip cache
pip3 cache purge
```

#### Permission Issues
```bash
# Install with user permissions
pip3 install --user -r requirements.txt

# Use virtual environment
python3 -m venv spiderfoot-env
source spiderfoot-env/bin/activate
```

#### Port Binding Issues
```bash
# Check port usage
netstat -tlnp | grep 5001

# Use different port
python sf.py -l 127.0.0.1:5002
```

### Docker Issues

#### Container Access
```bash
# Check running containers
docker ps

# Check container logs
docker logs <container_id>

# Access container shell
docker exec -it <container_id> /bin/bash
```

#### Volume Mounting
```bash
# Correct volume mounting
docker run -p 5001:5001 -v $(pwd)/data:/var/lib/spiderfoot spiderfoot/spiderfoot
```

## Performance Optimization

### Memory Optimization
```bash
# Limit module concurrent execution
export SPIDERFOOT_MAX_THREADS=3

# Optimize database
python sf.py --optimize-db
```

### Network Optimization
```bash
# Configure proxy settings
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080

# Configure DNS servers
export SPIDERFOOT_DNS_SERVER=8.8.8.8
```

## Next Steps

After successful installation:

1. **Read the [Quick Start Guide](quickstart.md)**
2. **Explore [Module Documentation](modules/index.md)**
3. **Learn about [Workspaces](WORKSPACE_INTEGRATION_COMPLETE.md)**
4. **Check [Configuration Options](configuration.md)**

## Getting Help

- **Documentation**: [GitHub Wiki](https://github.com/smicallef/spiderfoot/wiki)
- **Issues**: [GitHub Issues](https://github.com/smicallef/spiderfoot/issues)
- **Community**: [Discord Server](https://discord.gg/vyvztrG)
- **Twitter**: [@spiderfoot](https://twitter.com/spiderfoot)
