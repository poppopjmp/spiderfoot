# Configuration

*Author: poppopjmp*

SpiderFoot can be configured via the web UI, configuration file, and environment variables. Proper configuration ensures you get the most out of all modules and integrations, and helps tailor SpiderFoot to your environment and use case.

---

## API Keys

Many modules require API keys for external services. Configure these in the web UI:

- Go to **Settings → Module Settings**
- Enter your API keys for services such as:
  - VirusTotal
  - Shodan
  - Hunter.io
  - SecurityTrails
  - Have I Been Pwned
  - ...and more

> **Tip:** Modules that require API keys will show a warning if not configured. You can run scans without API keys, but results may be limited.

---

## Configuration File

Advanced options can be set in `spiderfoot.conf` (or `spiderfoot.cfg`):

```ini
[webui]
host = 127.0.0.1
port = 5001

[database]
path = spiderfoot.db
```

- You can change the web UI port, database location, logging options, and more.
- For production, consider moving the database to a persistent storage location.

---

## Environment Variables

You can override some settings using environment variables (useful for Docker and CI/CD):

- `SPIDERFOOT_DB_PATH` – Path to the database file
- `SPIDERFOOT_WEBUI_PORT` – Port for the web UI
- `SPIDERFOOT_WEBUI_HOST` – Host address for the web UI
- `SPIDERFOOT_LOG_LEVEL` – Logging verbosity (e.g., INFO, DEBUG)

---

## Best Practices

- Always keep your API keys secure and never share them publicly.
- Use a dedicated config file for production deployments.
- Regularly review and update your API keys and module settings.
- For Docker, use environment variables or mount a config file for persistent configuration.

---

## Troubleshooting

- If a module fails, check if its API key is set and valid.
- For config file errors, ensure correct INI syntax and file permissions.
- For Docker, use environment variables or mount a config file.
- See the [Troubleshooting Guide](troubleshooting.md) for more help.

---

See the [User Guide](user_guide.md) for more usage details and advanced configuration options.
