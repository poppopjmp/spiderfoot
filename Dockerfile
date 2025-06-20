#
# Spiderfoot Dockerfile - Enterprise Edition
# Improved version with virtual environment support and FastAPI
#

# Build stage
FROM python:3.11-slim-bullseye as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    libjpeg-dev \
    zlib1g-dev \
    libffi-dev \
    libssl-dev \
    python3-dev \
    git \
    curl \
    wget \
    unzip \
    npm \
    swig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python packages
ARG REQUIREMENTS=requirements.txt
COPY $REQUIREMENTS requirements.txt ./

# Install Python packages in virtual environment
RUN pip install --no-cache-dir -U pip==25.0.1 && \
    pip install --no-cache-dir -r requirements.txt && \
    # Install additional security tools
    pip install --no-cache-dir dnstwist snallygaster trufflehog wafw00f

# Download and build tools
RUN mkdir -p /tools/bin && \
    # Nuclei
    wget -q https://github.com/projectdiscovery/nuclei/releases/download/v3.3.9/nuclei_3.3.9_linux_amd64.zip && \
    unzip nuclei_3.3.9_linux_amd64.zip -d /tools/bin && \
    rm nuclei_3.3.9_linux_amd64.zip && \
    chmod +x /tools/bin/nuclei && \
    # Nuclei templates
    git clone --depth 1 https://github.com/projectdiscovery/nuclei-templates.git /tools/nuclei-templates && \
    # Node.js tools
    npm config set prefix /tools && \
    npm install -g retire && \
    # Git tools
    git clone --depth 1 https://github.com/testssl/testssl.sh.git /tools/testssl.sh && \
    git clone --depth 1 https://github.com/Tuhinshubhra/CMSeeK /tools/CMSeeK && \
    pip install --no-cache-dir -r /tools/CMSeeK/requirements.txt && \
    mkdir /tools/CMSeeK/Results

# Runtime stage
FROM python:3.11-slim-bullseye

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    zlib1g \
    nbtscan \
    onesixtyone \
    nmap \
    whatweb \
    bsdmainutils \
    dnsutils \
    coreutils \
    libcap2-bin \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy tools from builder
COPY --from=builder /tools /tools

# Set up environment with virtual environment
ENV SPIDERFOOT_DATA=/var/lib/spiderfoot \
    SPIDERFOOT_LOGS=/var/lib/spiderfoot/log \
    SPIDERFOOT_CACHE=/var/lib/spiderfoot/cache \
    PATH="/opt/venv/bin:/tools/bin:$PATH" \
    PYTHONPATH="/home/spiderfoot:/home/spiderfoot/modules" \
    VIRTUAL_ENV="/opt/venv"

# Create user and directories
RUN addgroup --system spiderfoot && \
    adduser --system --ingroup spiderfoot --home /home/spiderfoot \
            --shell /usr/sbin/nologin --gecos "SpiderFoot User" spiderfoot && \
    mkdir -p $SPIDERFOOT_DATA $SPIDERFOOT_LOGS $SPIDERFOOT_CACHE /home/spiderfoot/.spiderfoot/logs && \
    chown -R spiderfoot:spiderfoot /home/spiderfoot $SPIDERFOOT_DATA $SPIDERFOOT_LOGS $SPIDERFOOT_CACHE

# Enable NMAP capabilities
RUN setcap cap_net_raw,cap_net_admin=eip /usr/bin/nmap

# Copy application files (excluding database)
WORKDIR /home/spiderfoot

# Copy the rest of the application files
COPY --chown=spiderfoot:spiderfoot . .

# Copy and set up the startup script
COPY --chown=root:root docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Remove any database files from application directory to prevent conflicts
RUN rm -f /home/spiderfoot/spiderfoot.db && \
    rm -f /home/spiderfoot/data/spiderfoot.db

# Ensure the correct database directory structure exists
RUN mkdir -p /home/spiderfoot/.spiderfoot && \
    chown -R spiderfoot:spiderfoot /home/spiderfoot/.spiderfoot

# Create __init__.py files if they don't exist
RUN touch /home/spiderfoot/__init__.py && \
    touch /home/spiderfoot/modules/__init__.py && \
    touch /home/spiderfoot/spiderfoot/__init__.py

# Verify critical dependencies and module structure
RUN echo "=== Virtual Environment Test ===" && \
    which python && python --version && \
    echo "=== Python Path Test ===" && \
    python -c "import sys; print('Python path:'); [print(f'  {p}') for p in sys.path]" && \
    echo "=== Dependency Test ===" && \
    python -c "import cherrypy; print('CherryPy found')" && \
    python -c "import fastapi; print('FastAPI found')" && \
    python -c "import uvicorn; print('Uvicorn found')" && \
    python -c "import requests; print('Requests found')" && \
    python -c "import lxml; print('LXML found')" && \
    echo "=== SpiderFoot Import Test ===" && \
    python -c "from spiderfoot import SpiderFootHelpers; print('SpiderFootHelpers imported')" && \
    python -c "from sflib import SpiderFoot; print('SpiderFoot imported')" && \
    echo "=== Module Count ===" && \
    find /home/spiderfoot/modules -name 'sfp_*.py' | wc -l && \
    echo "=== FastAPI Test ===" && \
    python -c "import sfapi; print('FastAPI module imported successfully')" && \
    echo "=== Virtual Environment Info ===" && \
    python -c "import sys; print(f'Executable: {sys.executable}'); print(f'Virtual env: {getattr(sys, \"base_prefix\", sys.prefix) != sys.prefix}')"

USER spiderfoot

# Expose ports for both web UI and API
EXPOSE 5001 8001

# Default command with support for both web UI and API
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh", "python"]
CMD ["python", "sf.py", "--both", "-l", "0.0.0.0:5001", "--api-listen", "0.0.0.0:8001"]