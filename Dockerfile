#
# Spiderfoot Dockerfile - v5.1.2
#

# Build stage
FROM debian:bullseye-slim as builder

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
    python3-pip \
    git \
    curl \
    wget \
    unzip \
    npm \
    swig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements and install Python packages
ARG REQUIREMENTS=requirements.txt
COPY $REQUIREMENTS requirements.txt ./

# Install Python packages to a single prefix location
RUN pip install --no-cache-dir -U pip==25.0.1 && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    # Install additional tools to the same prefix
    pip install --no-cache-dir --prefix=/install dnstwist snallygaster trufflehog wafw00f

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
    pip install --no-cache-dir --prefix=/install -r /tools/CMSeeK/requirements.txt && \
    mkdir /tools/CMSeeK/Results

# Runtime stage
FROM debian:bullseye-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    zlib1g \
    python3 \
    python3-pip \
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

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy tools from builder
COPY --from=builder /tools /tools

# Set up environment with explicit Python path
ENV SPIDERFOOT_DATA=/var/lib/spiderfoot \
    SPIDERFOOT_LOGS=/var/lib/spiderfoot/log \
    SPIDERFOOT_CACHE=/var/lib/spiderfoot/cache \
    PATH="/tools/bin:$PATH" \
    PYTHONPATH="/usr/local/lib/python3.9/site-packages:/home/spiderfoot:/home/spiderfoot/modules"

# Create user and directories
RUN addgroup --system spiderfoot && \
    adduser --system --ingroup spiderfoot --home /home/spiderfoot \
            --shell /usr/sbin/nologin --gecos "SpiderFoot User" spiderfoot && \
    mkdir -p $SPIDERFOOT_DATA $SPIDERFOOT_LOGS $SPIDERFOOT_CACHE /home/spiderfoot/.spiderfoot/logs && \
    chown -R spiderfoot:spiderfoot /home/spiderfoot $SPIDERFOOT_DATA $SPIDERFOOT_LOGS $SPIDERFOOT_CACHE

# Enable NMAP capabilities
RUN setcap cap_net_raw,cap_net_admin=eip /usr/bin/nmap

# Copy application files
WORKDIR /home/spiderfoot
COPY --chown=spiderfoot:spiderfoot . .

# Create __init__.py files if they don't exist
RUN touch /home/spiderfoot/__init__.py && \
    touch /home/spiderfoot/modules/__init__.py && \
    touch /home/spiderfoot/spiderfoot/__init__.py

# Verify critical dependencies and module structure
RUN echo "=== Python Path Test ===" && \
    python3 -c "import sys; print('Python path:'); [print(f'  {p}') for p in sys.path]" && \
    echo "=== Dependency Test ===" && \
    python3 -c "import cherrypy; print('CherryPy found')" && \
    python3 -c "import requests; print('Requests found')" && \
    python3 -c "import lxml; print('LXML found')" && \
    echo "=== SpiderFoot Import Test ===" && \
    python3 -c "from spiderfoot import SpiderFootHelpers; print('SpiderFootHelpers imported')" && \
    python3 -c "from sflib import SpiderFoot; print('SpiderFoot imported')" && \
    echo "=== Module Count ===" && \
    find /home/spiderfoot/modules -name 'sfp_*.py' | wc -l

USER spiderfoot

EXPOSE 5001 8001

ENTRYPOINT ["python3"]
CMD ["sf.py", "-l", "0.0.0.0:5001"]