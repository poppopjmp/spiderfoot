# Quick Start

*Author: poppopjmp*

This guide will help you run your first scan in minutes using either the web interface or the command line. Follow these steps for a fast and successful start with SpiderFoot.

---

## Web Interface

1. **Start SpiderFoot:**

   ```sh
   python sf.py -l 127.0.0.1:5001
   ```

2. **Open the Web UI:**
   - Go to [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.
   - Log in with your admin account (created on first launch).

3. **Create a New Scan:**
   - Click **New Scan**
   - Enter your target (e.g., example.com)
   - Select the target type (e.g., DOMAIN_NAME) and choose modules
   - Click **Run Scan**

4. **View Results:**
   - Results will appear in real time. Use the sidebar to navigate between scans and workspaces.
   - You can filter, search, and export results as needed.

---

## Command-Line Example

Run a scan directly from the CLI:

```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois
```

- Use `python sf.py -M` to list all modules.
- Use `python sf.py -M <module>` for help on a specific module.

---

## Workspaces (CLI)

Workspaces allow you to manage multiple targets and scans:



- Workspaces are ideal for large projects, recurring assessments, or team collaboration.

---

## Troubleshooting

- If you have issues, see the [Troubleshooting Guide](troubleshooting.md).
- For help with modules, see the [Modules Guide](modules.md).
- For configuration and API keys, see the [Configuration Guide](configuration.md).

---

Next: [Configuration](configuration.md) for API keys, advanced settings, and more tips.
