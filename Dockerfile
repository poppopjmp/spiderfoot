#
# Spiderfoot Dockerfile
#


FROM debian:bullseye-slim
ARG REQUIREMENTS=requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends gcc libxml2 libxslt1.1 libjpeg62-turbo zlib1g git curl unzip wget npm swig libxml2-dev build-essential libxslt-dev libjpeg-dev zlib1g-dev libffi-dev libssl-dev python3 python3-dev python3-pip nbtscan onesixtyone nmap whatweb bsdmainutils dnsutils coreutils libcap2-bin && apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /home/spiderfoot
COPY $REQUIREMENTS requirements.txt ./
RUN pip install --no-cache-dir -U pip==25.0.1 && pip install --no-cache-dir -r requirements.txt

# Place database and logs outside installation directory
ENV SPIDERFOOT_DATA /var/lib/spiderfoot
ENV SPIDERFOOT_LOGS /var/lib/spiderfoot/log
ENV SPIDERFOOT_CACHE /var/lib/spiderfoot/cache

# Run everything as one command so that only one layer is created
RUN addgroup --system spiderfoot \
    && adduser --system --ingroup spiderfoot --home /home/spiderfoot --shell /usr/sbin/nologin \
               --gecos "SpiderFoot User" spiderfoot \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p $SPIDERFOOT_DATA || true \
    && mkdir -p $SPIDERFOOT_LOGS || true \
    && mkdir -p $SPIDERFOOT_CACHE || true \
    && chown spiderfoot:spiderfoot $SPIDERFOOT_DATA \
    && chown spiderfoot:spiderfoot $SPIDERFOOT_LOGS \
    && chown spiderfoot:spiderfoot $SPIDERFOOT_CACHE


RUN mkdir -p /tools/bin
WORKDIR /tools/bin
RUN wget https://github.com/projectdiscovery/nuclei/releases/download/v3.3.9/nuclei_3.3.9_linux_amd64.zip \
    && unzip nuclei_3.3.9_linux_amd64.zip \
    && rm nuclei_3.3.9_linux_amd64.zip \
    && chmod +x nuclei

# Download nuclei-templates
RUN git clone https://github.com/projectdiscovery/nuclei-templates.git /tools/nuclei-templates

RUN npm config set prefix /tools \
    && npm install -g retire

WORKDIR /tools
RUN pip install --no-cache-dir dnstwist snallygaster trufflehog wafw00f -t /tools \
    && git clone --depth 1 https://github.com/testssl/testssl.sh.git \
    && git clone https://github.com/Tuhinshubhra/CMSeeK \
    && pip install --no-cache-dir -r CMSeeK/requirements.txt -t /tools \
    && mkdir CMSeeK/Results \
    && echo "Checking installation paths..." \
    && if [ -x /usr/bin/nbtscan ]; then echo "nbtscan: /usr/bin/nbtscan (OK)"; else echo "nbtscan: NOT FOUND"; fi \
    && if [ -x /usr/bin/onesixtyone ]; then echo "onesixtyone: /usr/bin/onesixtyone (OK)"; else echo "onesixtyone: NOT FOUND"; fi \
    && if [ -x /usr/bin/nmap ]; then echo "nmap: /usr/bin/nmap (OK)"; else echo "nmap: NOT FOUND"; fi \
    && if [ -x /usr/bin/whatweb ]; then echo "whatweb: /usr/bin/whatweb (OK)"; else echo "whatweb: NOT FOUND"; fi \
    && if [ -x /usr/bin/dig ]; then echo "dnsutils: /usr/bin/dig (OK)"; else echo "dnsutils: NOT FOUND"; fi \
    # Check in /tools/bin/ for pip-installed tools
    && if [ -x /tools/bin/dnstwist ]; then echo "dnstwist: /tools/bin/dnstwist (OK)"; else echo "dnstwist: NOT FOUND"; fi \
    && if [ -x /tools/bin/snallygaster ]; then echo "snallygaster: /tools/bin/snallygaster (OK)"; else echo "snallygaster: NOT FOUND"; fi \
    && if [ -x /tools/bin/trufflehog ]; then echo "trufflehog: /tools/bin/trufflehog (OK)"; else echo "trufflehog: NOT FOUND"; fi \
    && if [ -x /tools/bin/wafw00f ]; then echo "wafw00f: /tools/bin/wafw00f (OK)"; else echo "wafw00f: NOT FOUND"; fi \
    && if [ -x /tools/testssl.sh/testssl.sh ]; then echo "testssl.sh: /tools/testssl.sh/testssl.sh (OK)"; else echo "testssl.sh: NOT FOUND"; fi \
    && if [ -f /tools/CMSeeK/cmseek.py ]; then echo "CMSeeK: /tools/CMSeeK/cmseek.py (OK)"; else echo "CMSeeK: NOT FOUND"; fi \
    && if [ -x /tools/bin/retire ]; then echo "retire.js: /tools/bin/retire (OK)"; else echo "retire.js: NOT FOUND"; fi \
    && if [ -x /tools/bin/wappalyzer ]; then echo "wappalyzer: /tools/bin/wappalyzer (OK)"; else echo "wappalyzer: NOT FOUND"; fi \
    && if [ -x /tools/bin/nuclei ]; then echo "nuclei: /tools/bin/nuclei (OK)"; else echo "nuclei: NOT FOUND"; fi
    

## Enable NMAP into the container to be fully used
RUN setcap cap_net_raw,cap_net_admin=eip /usr/bin/nmap

RUN chown -R spiderfoot:spiderfoot /home/spiderfoot/
USER spiderfoot

EXPOSE 5001
EXPOSE 8000

WORKDIR /home/spiderfoot
COPY . .
# Run the application.
ENTRYPOINT ["python3"]
CMD ["sf.py", "-l", "0.0.0.0:5001"]
