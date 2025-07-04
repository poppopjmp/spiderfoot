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
ENV SPIDERFOOT_DATA=/home/spiderfoot/data \
    SPIDERFOOT_LOGS=/home/spiderfoot/logs \
    SPIDERFOOT_CACHE=/home/spiderfoot/cache \
    PATH="/opt/venv/bin:/tools/bin:$PATH" \
    PYTHONPATH="/home/spiderfoot:/home/spiderfoot/modules" \
    VIRTUAL_ENV="/opt/venv"

# Create user and directories
RUN addgroup --system spiderfoot && \
    adduser --system --ingroup spiderfoot --home /home/spiderfoot \
            --shell /usr/sbin/nologin --gecos "SpiderFoot User" spiderfoot && \
    mkdir -p /home/spiderfoot/data /home/spiderfoot/logs /home/spiderfoot/cache /home/spiderfoot/.spiderfoot/logs && \
    # Do NOT chown bind-mounted folders here; this causes errors if the host directory is mounted at runtime.
    # Only set ownership for files inside the image.
    chown -R spiderfoot:spiderfoot /home/spiderfoot

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
    # Do NOT chown bind-mounted folders (e.g., /home/spiderfoot/data, /home/spiderfoot/logs, /home/spiderfoot/cache, /etc/spiderfoot) here; this causes errors if the host directory is mounted at runtime.
    # Only set ownership for files and folders created inside the image, not for host bind-mounts.
    rm -f /home/spiderfoot/data/spiderfoot.db

# Remove any existing logs that might have been copied and recreate logs directory
RUN rm -rf /home/spiderfoot/logs && \
    mkdir -p /home/spiderfoot/logs && \
    chown -R spiderfoot:spiderfoot /home/spiderfoot/logs && \
    chmod -R 755 /home/spiderfoot/logs

# Ensure the correct database directory structure exists
RUN mkdir -p /home/spiderfoot/.spiderfoot && \
    chown -R spiderfoot:spiderfoot /home/spiderfoot/.spiderfoot

# Create __init__.py files if they don't exist
RUN touch /home/spiderfoot/__init__.py && \
    touch /home/spiderfoot/modules/__init__.py && \
    touch /home/spiderfoot/spiderfoot/__init__.py

# Ensure proper ownership of all application files and directories (final step)
RUN chown -R spiderfoot:spiderfoot /home/spiderfoot 

USER spiderfoot

# Expose ports for both web UI and API
EXPOSE 5001 8001

# Default command with support for both web UI and API
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh", "python"]
CMD ["sf.py", "--both", "-l", "0.0.0.0:5001", "--api-listen", "0.0.0.0:8001"]

# ---
# NOTE: For persistent storage, logs, cache, and config, ensure the following paths are writeable by the spiderfoot user inside the container:
#   - /home/spiderfoot/data           (main data, including spiderfoot.db)
#   - /home/spiderfoot/cache          (cache)
#   - /home/spiderfoot/logs           (logs)
#   - /home/spiderfoot/config         (config, if used)
# If these are bind-mounted from the host, you must set correct permissions/ownership on the host before starting the container.
# The Dockerfile cannot change ownership of bind-mounted folders at runtime.
# ---