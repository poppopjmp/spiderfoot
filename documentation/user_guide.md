# User Guide

## Web Interface
- Start the server: `python sf.py -l 127.0.0.1:5001`
- Access via browser: [http://127.0.0.1:5001](http://127.0.0.1:5001)
- Use "New Scan" for single targets
- Use "Workspaces" for multi-target scans

## CLI Usage
- List modules: `python sf.py -M`
- Help for a module: `python sf.py -M sfp_dnsresolve`
- Run scan: `python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl`

See [Modules](modules.md) for more details.
