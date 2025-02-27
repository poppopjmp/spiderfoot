#
# Spiderfoot Dockerfile
#


FROM debian:bullseye-slim
ARG REQUIREMENTS=requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends gcc=4:10.2.1-1 git=1:2.30.2-1+deb11u2 curl=7.74.0-1.3+deb11u7 swig=4.0.2-1 libxml2-dev=2.9.10+dfsg-6.7+deb11u5 libxslt-dev=1.1.34-4+deb11u1 libjpeg-dev=1:2.0.6-4 zlib1g-dev=1:1.2.11.dfsg-2+deb11u2 libffi-dev=3.3-6 libssl-dev=1.1.1n-0+deb11u3 cargo=0.55.0-1 rustc=1.48.0+dfsg1-2~deb11u1 python3=3.9.2-3 python3-venv=3.9.2-3 python3-pip=20.3.4-4+deb11u1 nbtscan=1.5.1-1 onesixtyone=0.3.3-1 nmap=7.91+dfsg1+really7.80+dfsg1-2+deb11u1 whatweb=0.5.3-0.1 bsdmainutils=12.1.7+nmu3 dnsutils=1:9.16.22-1~deb11u1 coreutils=8.32-4 libcap2-bin=1:2.44-1 && rm -rf /var/lib/apt/lists/*
WORKDIR /home/spiderfoot
#COPY $REQUIREMENTS requirements.txt ./
RUN pip install --no-cache-dir -U pip==25.0.1
RUN pip install --no-cache-dir -r requirements.txt

# Place database and logs outside installation directory
ENV SPIDERFOOT_DATA /var/lib/spiderfoot
ENV SPIDERFOOT_LOGS /var/lib/spiderfoot/log
ENV SPIDERFOOT_CACHE /var/lib/spiderfoot/cache

# Run everything as one command so that only one layer is created
RUN apt-get update && apt-get install -y --no-install-recommends libxml2=2.9.10+dfsg-6.7+deb11u5 libxslt1.1=1.1.34-4+deb11u1 libjpeg62-turbo=1:2.0.6-4 zlib1g=1:1.2.11.dfsg-2+deb11u2 python3=3.9.2-3 \
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
RUN mkdir /tools \
    && pip install --no-cache-dir dnstwist==20200707 snallygaster==0.0.8 trufflehog==2.0.9 wafw00f==2.1.0 -t /tools \
    && cd /tools \
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
