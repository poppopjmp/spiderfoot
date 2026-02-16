# Installation Guide

*Author: poppopjmp*

This guide will walk you through installing SpiderFoot v5.3.3 on Linux, macOS, or Windows, as well as deploying with Docker for easy setup and portability. The enhanced SpiderFoot includes 277 modules with advanced capabilities for TikTok OSINT, blockchain analytics, performance optimization, and AI-powered analysis.

---

## Requirements

- **Python 3.8 or higher** (recommended: Python 3.11+)
- **pip** (Python package manager)
- **Git** (for cloning the repository)
- **Memory**: Minimum 2GB RAM (4GB+ recommended for enhanced features)
- **Disk Space**: Minimum 2GB (additional space for caching and databases)
- **(Optional)** Docker and Docker Compose for containerized deployments

### Enhanced Features Requirements

For full functionality of enhanced modules:

- **API Keys**: TikTok Research API, BlockCypher, Etherscan, OpenAI (see [Configuration](configuration.md))
- **Additional Memory**: +500MB for performance optimization and caching
- **Network Access**: Outbound HTTPS for blockchain APIs and AI services

## Installation Steps (Linux, macOS, Windows)

1. **Clone the repository:**

   ```sh
   git clone https://github.com/poppopjmp/spiderfoot.git
   cd spiderfoot
   ```

2. **Install dependencies:**

   ```sh
   pip install -r requirements.txt
   ```

   - If you use a virtual environment:

     ```sh
     python -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     pip install -r requirements.txt
     ```

3. **Run SpiderFoot:**

   ```sh
   python sf.py -l 127.0.0.1:5001
   ```

   - Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.
   - The default admin account will be created on first launch. Set a strong password.
   - You can change the listening address and port as needed.

---

## Docker Installation

Docker is the easiest way to run SpiderFoot in a portable, isolated environment.

- **Run with Docker Compose (profiles):**

  ```sh
  cp .env.example .env
  # Edit .env — change passwords, uncomment profile sections as needed

  # Core only (5 services: postgres, redis, api, worker, frontend)
  docker compose -f docker-compose-microservices.yml up --build -d

  # Full stack (all services except SSO)
  docker compose -f docker-compose-microservices.yml --profile full up --build -d
  ```

  See [Docker Deployment Guide](docker_deployment.md) for available profiles and advanced configuration.

---

## Upgrading SpiderFoot

- To upgrade, pull the latest code from GitHub and reinstall dependencies:

  ```sh
  git pull
  pip install -r requirements.txt
  ```
- For Docker, pull the latest image:

  ```sh
  docker pull poppopjmp/spiderfoot
  ```

---

## Troubleshooting

- If you see missing dependency errors, run `pip install -r requirements.txt` again.
- For permission errors, try running as administrator or with `sudo` (Linux/macOS).
- For Docker issues, check container logs with `docker logs <container_id>`.
- See the [Troubleshooting Guide](troubleshooting.md) for more help.

---

Continue to the [Getting Started](getting_started.md) guide to launch your first scan.
