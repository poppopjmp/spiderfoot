# Getting Started

*Author: poppopjmp*

Welcome to SpiderFoot! This guide will help you set up, configure, and run your first scan, whether you are a new user or an experienced security professional. Follow these steps to get SpiderFoot up and running quickly.

---

## 1. Installation

See the [Installation Guide](installation.md) for detailed steps. In summary:

- **Clone the repository:**
  ```bash
  git clone https://github.com/poppopjmp/spiderfoot.git
  cd spiderfoot
  ```

### Docker Microservices (Recommended)

```bash
cp docker/env.example .env
# Edit .env with your API keys (OpenAI, Anthropic, etc.)
docker compose -f docker-compose-microservices.yml up --build -d
```

Access the UI at [https://localhost](https://localhost).

### Standalone Mode

```bash
pip install -r requirements.txt
python sf.py -l 127.0.0.1:5001
```

Access at [http://127.0.0.1:5001](http://127.0.0.1:5001).

## 2. Launching the Web Interface

Open your browser and navigate to the SpiderFoot URL. Log in with the default credentials (`admin` / `admin`) or your configured admin account.

![Login](images/login.png)

The **Dashboard** provides at-a-glance statistics — active scans, total events, risk distribution, and recent scan activity.

![Dashboard](images/dashboard.png)

## 3. Running Your First Scan

- Click **New Scan** from the sidebar or dashboard.
- Enter a target (e.g., `example.com`).
- Select the target type and choose module categories.
- Click **Run Scan**.

![New Scan](images/new_scan.png)

Results appear in real time. Click any scan to open the **Scan Detail** view with 8 tabs: Summary, Browse, Correlations, Graph, GeoMap, AI Report, Scan Settings, and Log.

![Scans](images/scans.png)

![Scan Detail - Summary](images/scan_detail_summary.png)

## 4. Using the CLI

For a basic scan:
```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois
```
- Use `python sf.py -M` to list all available modules.
- Use `python sf.py -M <module>` for help on a specific module.

## 5. Workspaces and Multi-Target Scans

Organize related scans into **Workspaces** for multi-target campaigns, recurring assessments, or team collaboration. Each workspace groups scans, tracks notes, and provides workspace-level analytics and AI-generated reports.

![Workspaces](images/workspaces.png)

## 6. Configuration

### Basic Configuration
- Configure API keys for modules in the web UI under **Settings → Module Settings**.
- Advanced options can be set in the config file or via environment variables. See the [Configuration Guide](configuration.md).

### Security Configuration (Recommended)
For production deployments, configure security features:

```bash
# Set strong secret keys
export SPIDERFOOT_CSRF_SECRET=$(openssl rand -hex 32)
export SPIDERFOOT_JWT_SECRET=$(openssl rand -hex 32)

# Enable security logging
export SPIDERFOOT_SECURITY_LOG_FILE=/var/log/spiderfoot/security.log
```

Or via configuration file:
```ini
[security]
csrf_enabled = True
csrf_secret_key = your-strong-secret-key
rate_limiting_enabled = True
input_validation_enabled = True
session_security_enabled = True
api_security_enabled = True
security_logging_enabled = True
```

### Security Validation
Validate your security setup:
```bash
cd spiderfoot
python security_validator.py .
```

## Troubleshooting
- If you have issues, check the [Troubleshooting Guide](troubleshooting.md).
- Ensure all dependencies are installed and ports are open.
- For Docker, check container logs with `docker logs <container_id>`.
- For module errors, verify API keys and settings.

---

Continue to the [Quick Start](quickstart.md) or [User Guide](user_guide.md) for more advanced usage, tips, and best practices.
