# sfp_hibp

**Purpose:**
Checks HaveIBeenPwned for breaches and exposures related to the target email or domain. Useful for identifying compromised accounts and risk assessment.

**Category:** Threat Intelligence / Data Breach

---

## Usage

- Enabled for email and domain targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s user@example.com -t EMAILADDR -m sfp_hibp
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
- Combine with sfp_email and sfp_breach for comprehensive risk analysis.

---

Authored by poppopjmp
