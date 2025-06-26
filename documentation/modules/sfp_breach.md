# sfp_breach

**Purpose:**
Checks for data breaches and leaked credentials associated with the target email, domain, or username. Useful for identifying compromised accounts and exposure risks.

**Category:** Threat Intelligence / Data Breach

---

## Usage
- Enabled for email, domain, and username targets.
- Can be run from the web UI or CLI:
  ```sh
  python sf.py -s user@example.com -t EMAILADDR -m sfp_breach
  ```

## Output Example
```
Email: user@example.com
Breaches Found: 3
Sources: HaveIBeenPwned, Dehashed
Details: Passwords, personal info exposed
```

## API Keys Required
- HaveIBeenPwned (optional, for more results)
- Dehashed (optional, for more results)

## Tips
- Use to assess risk for users, domains, or organizations.
- Combine with sfp_email, sfp_username for full coverage.

---

*Authored by poppopjmp*
