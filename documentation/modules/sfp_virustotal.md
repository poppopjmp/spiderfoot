# sfp_virustotal

**Purpose:**
Integrates with the VirusTotal API to check domains, IPs, and files for malware, reputation, and threat intelligence. Useful for identifying malicious assets and correlating threat data.

**Category:** Threat Intelligence / Malware Analysis

---

## Usage

- Enabled for domain, IP, and file hash targets.
- Can be run from the web UI or CLI:

```sh
curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "modules": ["sfp_virustotal"]}'
```

## Output Example

```pre
Domain: example.com
Detections: 2/70
Malicious: Yes
Categories: phishing, malware
```

## API Keys Required

- VirusTotal API key (required)

## Tips

- Use to quickly check if a domain, IP, or file is flagged as malicious.
- Combine with sfp_shodan and sfp_breach for comprehensive threat context.

---

*Authored by poppopjmp*
