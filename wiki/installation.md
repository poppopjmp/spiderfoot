# Installation Guide

*Author: poppopjmp*

This guide will walk you through installing SpiderFoot on Linux, macOS, or Windows, as well as deploying with Docker for easy setup and portability.

---

## Requirements

- Python 3.7 or higher (recommended: latest stable)
- pip (Python package manager)
- Git (for cloning the repository)
- (Optional) Docker and Docker Compose for containerized deployments

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

- **Run with Docker:**

  ```sh
  docker run -p 5001:5001 poppopjmp/spiderfoot
  ```

- **Run with Docker Compose:**

  ```sh
  docker-compose up
  ```

- For production deployments, see [Production Deployment](../docs/PRODUCTION_DEPLOYMENT.md) for advanced configuration, persistent storage, and scaling tips.

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
