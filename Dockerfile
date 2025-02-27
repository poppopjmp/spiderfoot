#
# Spiderfoot Dockerfile
#


FROM debian:bullseye-slim
ARG REQUIREMENTS=requirements.txt
RUN apt-get update && apt-get install -y gcc git curl swig libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev libffi-dev libssl-dev cargo rustc python3 python3-venv python3-pip
WORKDIR /home/spiderfoot
COPY $REQUIREMENTS requirements.txt ./
RUN pip install --no-cache-dir -U pip==25.0.1 && pip install --no-cache-dir -r requirements.txt

# Place database and logs outside installation directory
ENV SPIDERFOOT_DATA /var/lib/spiderfoot
ENV SPIDERFOOT_LOGS /var/lib/spiderfoot/log
ENV SPIDERFOOT_CACHE /var/lib/spiderfoot/cache

# Run everything as one command so that only one layer is created
RUN apt-get update && apt-get install -y --no-install-recommends libxml2 libxslt1.1 libjpeg62-turbo zlib1g \
    && addgroup --system spiderfoot \
    && adduser --system --ingroup spiderfoot --home /home/spiderfoot --shell /usr/sbin/nologin \
               --gecos "SpiderFoot User" spiderfoot \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p $SPIDERFOOT_DATA || true \
    && mkdir -p $SPIDERFOOT_LOGS || true \
    && mkdir -p $SPIDERFOOT_CACHE || true \
    && chown spiderfoot:spiderfoot $SPIDERFOOT_DATA \
    && chown spiderfoot:spiderfoot $SPIDERFOOT_LOGS \
    && chown spiderfoot:spiderfoot $SPIDERFOOT_CACHE

# Install tools/dependencies from apt
RUN apt-get -y update && apt-get -y install nbtscan onesixtyone nmap whatweb bsdmainutils dnsutils coreutils libcap2-bin
RUN mkdir /tools 
WORKDIR /tools
RUN pip install --no-cache-dir dnstwist==20200707 snallygaster==0.0.8 trufflehog==2.0.9 wafw00f==2.1.0 -t /tools \
    && git clone --depth 1 https://github.com/testssl/testssl.sh.git \
    && git clone https://github.com/Tuhinshubhra/CMSeeK && cd CMSeeK && pip install --no-cache-dir -r requirements.txt && mkdir Results

## Enable NMAP into the container to be fully used
RUN setcap cap_net_raw,cap_net_admin=eip /usr/bin/nmap

USER spiderfoot

EXPOSE 5001
EXPOSE 8000

WORKDIR /home/spiderfoot
COPY . .
# Run the application.
ENTRYPOINT ["python3"]
CMD ["sf.py", "-l", "0.0.0.0:5001"]
