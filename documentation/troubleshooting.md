# Troubleshooting

If you encounter issues with SpiderFoot, use this guide to diagnose and resolve common problems. For additional help, consult the documentation, GitHub Issues, or the Discord community.

---

## General Troubleshooting Steps

- **Check logs:** Review logs in the `logs/` directory for error messages and stack traces.
- **Verify dependencies:** Ensure all required Python packages are installed. Use `pip install -r requirements.txt` to install missing dependencies.
- **Restart the application:** Sometimes, simply restarting SpiderFoot or your Docker container resolves transient issues.
- **Check for updates:** Make sure you are running the latest version of SpiderFoot and its dependencies.

---

## Troubleshooting Workflow Diagram

Below is a simple troubleshooting workflow for SpiderFoot. Follow the arrows to diagnose and resolve issues efficiently.

```mermaid
flowchart TD
    A[SpiderFoot Issue Detected] --> B{Is there an error in logs?}
    B -- Yes --> C[Read error message]
    C --> D{Is it a dependency error?}
    D -- Yes --> E[Run pip install -r requirements.txt]
    D -- No --> F{Is it a config error?}
    F -- Yes --> G[Check config file syntax and permissions]
    F -- No --> H[Search error message online or in docs]
    B -- No --> I[Check Docker/container logs]
    I --> J{Is it a Docker issue?}
    J -- Yes --> K[Check volume permissions, ports, and restart container]
    J -- No --> L[Ask for help on GitHub or Discord]
    H --> L
    G --> M[Restart SpiderFoot]
    E --> M
    K --> M
    M --> N[Issue resolved?]
    N -- Yes --> O[Done]
    N -- No --> L
```

---

## Troubleshooting Decision Tree

```mermaid
flowchart LR
    A[Problem Detected] --> B{Web UI or CLI?}
    B -- Web UI --> C{Page Loads?}
    C -- No --> D[Check server status and port]
    C -- Yes --> E{Scan Results Appear?}
    E -- No --> F[Check logs, API keys, modules]
    E -- Yes --> G[Check for data completeness]
    B -- CLI --> H{Error Message?}
    H -- Yes --> I[Read and search error]
    H -- No --> J[Check command syntax]
```

---

## Docker Troubleshooting Flow

```mermaid
flowchart TD
    A[Docker Container Fails] --> B{Check logs}
    B -- Error found --> C[Resolve error]
    B -- No error --> D[Check volume mounts]
    D --> E{Permissions OK?}
    E -- No --> F[Fix permissions]
    E -- Yes --> G[Check network settings]
    G --> H{Ports open?}
    H -- No --> I[Open required ports]
    H -- Yes --> J[Ask for help]
```

---

## API Troubleshooting Flow

```mermaid
flowchart TD
    A[API Call Fails] --> B{Error Message?}
    B -- 401/403 --> C[Check API key/auth]
    B -- 404 --> D[Check endpoint URL]
    B -- 500 --> E[Check server logs]
    B -- CORS --> F[Check browser/network]
    B -- Other --> G[Search docs/community]
```

---

## Visual: Common Error Types

```mermaid
flowchart TD
    A[Error Occurs] --> B{Type?}
    B -- Dependency --> C[Install/Update Python packages]
    B -- Config --> D[Check config file, env vars]
    B -- Network --> E[Check ports, firewall, DNS]
    B -- API --> F[Check API keys, endpoint, docs]
    B -- Docker --> G[Check logs, volumes, permissions]
    B -- Unknown --> H[Search docs/community]
```

---

## Visual: Support Channels

```mermaid
flowchart TD
    A[Need Help?] --> B[Check Documentation]
    B --> C[Search GitHub Issues]
    C --> D[Ask on Discord]
    D --> E[Contact Maintainer]
```

---

## Common Error Messages

| Error Message                        | Likely Cause                        | Solution                                 |
|--------------------------------------|-------------------------------------|------------------------------------------|
| `ModuleNotFoundError`                | Missing Python dependency           | Run `pip install -r requirements.txt`    |
| `Address already in use`             | Port conflict                       | Change port in config or command         |
| `Permission denied`                  | File or directory permissions       | Check file permissions, run as admin     |
| `API key not set`                    | Missing API key for a module        | Set API key in web UI                    |
| `Database locked`                    | SQLite concurrency issue            | Restart SpiderFoot, avoid multiple runs  |

---

## Getting More Help

If you can't resolve your issue, visit the [GitHub Issues page](https://github.com/poppopjmp/spiderfoot/issues) or join the Discord community for support. Please provide detailed information about your environment and the problem (OS, Python version, Docker version, error messages, steps to reproduce, etc.).

---

## Wiki & Further Reading

- [Official Documentation](https://github.com/poppopjmp/spiderfoot/wiki)
- [User Guide](user_guide.md)
- [API Reference](api_reference.md)
- [Modules Index](modules.md)
- [Developer Guide](developer_guide.md)
- [Advanced Topics](advanced.md)

---

## Module Reference

A full, detailed description for each module is available in the `documentation/modules/` folder. Each file describes the module's purpose, usage, required API keys, and example output.

---

Authored by poppopjmp
