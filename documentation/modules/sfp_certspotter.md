# sfp_certspotter

**Purpose:**
Queries the CertSpotter API for SSL/TLS certificate transparency logs related to the target domain. Useful for discovering new subdomains and monitoring certificate issuance.

**Category:** Security Analysis / Asset Discovery

---

## Usage

- Enabled for domain targets.
- Can be run from the web UI or CLI:

```sh
curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "modules": ["sfp_certspotter"]}'
```

## Output Example

```pre
Domain: example.com
Certificates Found: 3
Subdomains: dev.example.com, mail.example.com
```

## API Keys Required

None (public API)

## Tips

- Use to monitor for unauthorized certificate issuance.
- Combine with sfp_sslcert and sfp_dnsresolve for full context.

---

Authored by poppopjmp
