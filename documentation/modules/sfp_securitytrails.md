# sfp_securitytrails

**Purpose:**
Integrates with the SecurityTrails API to gather passive DNS, WHOIS, and infrastructure data for the target domain or IP. Useful for asset discovery, historical analysis, and threat intelligence.

**Category:** Threat Intelligence / Asset Discovery

---

## Usage

- Enabled for domain and IP targets.
- Can be run from the web UI or CLI:

```sh
curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "modules": ["sfp_securitytrails"]}'
```

## Output Example

```pre
Domain: example.com
Passive DNS: 93.184.216.34, 93.184.216.35
WHOIS: Registrar, creation date, etc.
Related Domains: dev.example.com, mail.example.com
```

## API Keys Required

- SecurityTrails API key (required)

## Tips

- Use to enrich asset inventory and discover related infrastructure.
- Combine with sfp_dnsresolve and sfp_whois for full mapping.

---

Authored by poppopjmp
