# Getting Started

*Author: poppopjmp*

Welcome to SpiderFoot! This guide will help you set up, configure, and run your first scan, whether you are a new user or an experienced security professional. Follow these steps to get SpiderFoot up and running quickly.

---

## 1. Installation

See the [Installation Guide](installation.md) for detailed steps. In summary:

- **Clone the repository:**
  ```sh
  git clone https://github.com/poppopjmp/spiderfoot.git
  cd spiderfoot
  ```
- **Install dependencies:**
  ```sh
  pip install -r requirements.txt
  ```
- **(Optional) Use Docker:**
  Docker provides an easy, isolated way to run SpiderFoot. See the [Docker section](installation.md#docker-installation) for details.

## 2. Launching the Web Interface

Start the web server:
```sh
python sf.py -l 127.0.0.1:5001
```
Then open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

- The default admin account will be created on first launch. Set a strong password.
- You can change the listening address and port in the command above.

## 3. Running Your First Scan

- Click **New Scan** in the web UI.
- Enter a target (e.g., example.com).
- Select the target type (e.g., DOMAIN_NAME) and choose which modules to run.
- Click **Run Scan**.
- Results will appear in real time. Use the sidebar to navigate between scans and workspaces.

## 4. Using the CLI

For a basic scan:
```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois
```
- Use `python sf.py -M` to list all available modules.
- Use `python sf.py -M <module>` for help on a specific module.

## 5. Workspaces and Multi-Target Scans

Workspaces allow you to organize and manage multiple scans:

- Workspaces are ideal for large projects, team collaboration, or recurring assessments.

## 6. Configuration

- Configure API keys for modules in the web UI under **Settings → Module Settings**.
- Advanced options can be set in the config file or via environment variables. See the [Configuration Guide](configuration.md).

## Troubleshooting
- If you have issues, check the [Troubleshooting Guide](troubleshooting.md).
- Ensure all dependencies are installed and ports are open.
- For Docker, check container logs with `docker logs <container_id>`.
- For module errors, verify API keys and settings.

---

Continue to the [Quick Start](quickstart.md) or [User Guide](user_guide.md) for more advanced usage, tips, and best practices.
