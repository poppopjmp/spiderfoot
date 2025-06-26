# Modules

SpiderFoot includes 200+ modules. Popular modules:

- `sfp_dnsresolve`: DNS resolution
- `sfp_ssl`: SSL certificate analysis
- `sfp_whois`: WHOIS information
- `sfp_portscan_tcp`: Port scanning
- `sfp_threatcrowd`: Threat intelligence

## Module Commands
- List all: `python sf.py -M`
- Help: `python sf.py -M <module>`
- Run: `python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl`

See the webapp for a full module index.
