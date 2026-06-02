# sfp_email

**Purpose:**
Extracts and analyzes email addresses related to the target from web pages, breaches, and public sources. Useful for identifying exposed accounts and potential phishing risks.

**Category:** Data Gathering / Exposure Analysis

---

## Usage

- Enabled for domain, person, and organization targets.
- Can be run from the web UI or CLI:

```sh
curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "modules": ["sfp_email"]}'
```

## Output Example

```pre
Domain: example.com
Emails Found: admin@example.com, support@example.com
Sources: Web, breach data
```

## API Keys Required

None (some enrichment modules may require keys)

## Tips

- Use to discover exposed or public-facing email addresses.
- Combine with sfp_dehashed for breach exposure analysis.

---

*Authored by poppopjmp*
