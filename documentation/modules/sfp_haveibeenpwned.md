# sfp_haveibeenpwned

**Purpose:**
Checks HaveIBeenPwned for breaches and exposures related to the target email or domain. Useful for identifying compromised accounts and risk assessment.

**Category:** Threat Intelligence / Data Breach

---

## Usage

- Enabled for email and domain targets.
- Can be run from the web UI or CLI:

```sh
curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "user@example.com", "modules": ["sfp_haveibeenpwned"]}'
```

## Output Example

```pre
Email: user@example.com
Breaches Found: 5
Sources: HaveIBeenPwned
Details: Passwords, personal info exposed
```

## API Keys Required

- HaveIBeenPwned API key (optional, for more results)

## Tips

- Use to assess breach exposure for users and organizations.
- Combine with sfp_email and sfp_dehashed for comprehensive risk analysis.

---

Authored by poppopjmp
