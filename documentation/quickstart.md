# Quick Start

## Web Interface
1. Start SpiderFoot: `python sf.py -l 127.0.0.1:5001`
2. Open [http://127.0.0.1:5001](http://127.0.0.1:5001)
3. Click "New Scan", enter a target, select type and modules, and run.

## CLI Example
```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois
```

## Workspaces
```sh
python sfworkflow.py create-workspace "My Assessment"
python sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME
python sfworkflow.py multi-scan ws_abc123 --modules sfp_dnsresolve,sfp_ssl
```

See [Configuration](configuration.md) for API keys and settings.
