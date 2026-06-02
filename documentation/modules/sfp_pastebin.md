# sfp_pastebin

**Purpose:**
Searches Pastebin for leaks, credentials, and mentions related to the target domain, email, or username. Useful for breach detection and exposure analysis.

**Category:** Threat Intelligence / Data Leak

---

## Usage

- Enabled for domain, email, and username targets.
- Can be run from the web UI or CLI:

```sh
curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "modules": ["sfp_pastebin"]}'
```

## Output Example

```pre
Domain: example.com
Leaks Found: 2
Paste URLs: https://pastebin.com/abc123, https://pastebin.com/xyz789
```

## API Keys Required

- Pastebin API key (optional, for higher rate limits)

## Tips

- Use to detect credential leaks and sensitive data exposure.
- Combine with sfp_dehashed and sfp_email for comprehensive risk analysis.

---

Authored by poppopjmp
