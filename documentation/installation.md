# Installation Guide

## Requirements
- Python 3.7+
- pip
- Git

## Steps

```sh
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot
pip install -r requirements.txt
python sf.py -l 127.0.0.1:5001
```

## Docker

```sh
docker run -p 5001:5001 poppopjmp/spiderfoot
docker-compose up
```

See [Quick Start](quickstart.md) for your first scan.
