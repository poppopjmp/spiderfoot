# sfp_github

**Purpose:**
Searches GitHub for code, repositories, and mentions related to the target domain, email, or username. Useful for identifying exposed credentials, code leaks, and digital footprint.

**Category:** Data Gathering / Exposure Analysis

---

## Usage

- Enabled for domain, email, and username targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_github
```

## Output Example

```pre
Domain: example.com
Repositories Found: github.com/user/repo1, github.com/user/repo2
Mentions: 5
Secrets Detected: Yes
```

## API Keys Required

- GitHub API key (optional, for higher rate limits)

## Tips

- Use to discover code leaks, credentials, and mentions of your assets.
- Combine with sfp_email and sfp_breach for full exposure analysis.

---

Authored by poppopjmp
