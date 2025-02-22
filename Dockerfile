#
# Spiderfoot Dockerfile
#
# http://www.spiderfoot.net
#
# Written by: Michael Pellon <m@pellon.io>
# Updated by: Chandrapal <bnchandrapal@protonmail.com>
# Updated by: Steve Micallef <steve@binarypool.com>
# Updated by: Steve Bate <svc-spiderfoot@stevebate.net>
#    -> Inspired by https://github.com/combro2k/dockerfiles/tree/master/alpine-spiderfoot
#
# Usage:
#
#   sudo docker build -t spiderfoot .
#   sudo docker run -p 5001:5001 --security-opt no-new-privileges spiderfoot
#
# Using Docker volume for spiderfoot data
#
#   sudo docker run -p 5001:5001 -v /mydir/spiderfoot:/var/lib/spiderfoot spiderfoot
#
# Using SpiderFoot remote command line with web server
#
#   docker run --rm -it spiderfoot sfcli.py -s http://my.spiderfoot.host:5001/
#
# Running spiderfoot commands without web server (can optionally specify volume)
#
#   sudo docker run --rm spiderfoot sf.py -h
#
# Running a shell in the container for maintenance
#   sudo docker run -it --entrypoint /bin/sh spiderfoot
#
# Running spiderfoot unit tests in container
#
#   sudo docker build -t spiderfoot-test --build-arg REQUIREMENTS=test/requirements.txt .
#   sudo docker run --rm spiderfoot-test -m pytest --flake8 .
 

FROM debian:bullseye-slim
ARG REQUIREMENTS=requirements.txt
RUN apt-get update && apt-get install -y gcc git curl swig libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev libffi-dev libssl-dev cargo rustc python3 python3-venv python3-pip
COPY $REQUIREMENTS requirements.txt ./
RUN ls
RUN echo "$REQUIREMENTS"
RUN pip install -U pip
RUN pip install -r requirements.txt

# Place database and logs outside installation directory
ENV SPIDERFOOT_DATA /var/lib/spiderfoot
ENV SPIDERFOOT_LOGS /var/lib/spiderfoot/log
ENV SPIDERFOOT_CACHE /var/lib/spiderfoot/cache

# Run everything as one command so that only one layer is created
RUN apt-get update && apt-get install -y libxml2 libxslt1.1 libjpeg62-turbo zlib1g python3 \
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

# Install Python tools

RUN mkdir /tools
RUN pip install dnstwist snallygaster trufflehog wafw00f -t /tools
RUN cd /tools
RUN git clone --depth 1 https://github.com/testssl/testssl.sh.git
RUN git clone https://github.com/Tuhinshubhra/CMSeeK && cd CMSeeK && pip install -r requirements.txt && mkdir Results

## Enable NMAP into the container to be fully used
RUN setcap cap_net_raw,cap_net_admin=eip /usr/bin/nmap

USER spiderfoot

EXPOSE 5001

WORKDIR /home/spiderfoot
COPY . .
# Run the application.
ENTRYPOINT ["python3"]
CMD ["sf.py", "-l", "0.0.0.0:5001"]
