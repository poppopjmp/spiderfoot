# Getting Started

This guide will help you set up and run your first scan with SpiderFoot.

1. [Installation](installation.md)
2. [Quick Start](quickstart.md)
3. [Configuration](configuration.md)

For a basic scan:

```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois
```

For the web interface, run:

```sh
python sf.py -l 127.0.0.1:5001
```

Then open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.
