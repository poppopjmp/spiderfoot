# sfp_whois

**Purpose:**
Performs WHOIS lookups for domains and IP addresses, extracting registration details, ownership, and contact information. Useful for attribution, asset discovery, and identifying domain age or changes.

**Category:** Data Gathering / Attribution

---

## Usage
- Enabled by default for domain and IP targets.
- Can be run from the web UI or CLI:
  ```sh
  curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "modules": ["sfp_whois"]}'
  ```

## Output Example
```
Domain: example.com
Registrar: Example Registrar, Inc.
Registrant: John Doe
Creation Date: 2010-01-01
Expiration Date: 2026-01-01
```

## API Keys Required
None (for most TLDs; some may require keys for advanced data)

## Tips
- Use to identify domain owners, registration changes, and expiration risks.
- Combine with sfp_dnsresolve and sfp_ssl for full context.

---

*Authored by poppopjmp*
