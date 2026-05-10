# sfp_alienvault

**Purpose:**
Queries AlienVault OTX for threat intelligence, indicators of compromise, and reputation data related to the target domain, IP, or email. Useful for threat detection and enrichment.

**Category:** Threat Intelligence / IOC Enrichment

---

## Usage

- Enabled for domain, IP, and email targets.
- Can be run from the web UI or CLI:

```sh
curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "modules": ["sfp_alienvault"]}'
```

## Output Example

```pre
Domain: example.com
OTX Pulses: 2
Indicators: malicious, phishing
Related IPs: 1.2.3.4, 5.6.7.8
```

## API Keys Required

- AlienVault OTX API key (required)

## Tips

- Use to correlate threat intelligence and enrich investigations.
- Combine with sfp_virustotal and sfp_shodan for deeper context.

---

Authored by poppopjmp
