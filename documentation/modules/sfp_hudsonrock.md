# sfp_hudsonrock

**Purpose:**
Queries Hudson Rock's Cavalier OSINT API for infostealer intelligence. Searches for compromised credentials, infected machines, and stealer malware data associated with domains, emails, usernames, and phone numbers. Hudson Rock aggregates data from millions of computers compromised by infostealer malware worldwide.

**Category:** Leaks, Dumps and Breaches

---

## Usage

- No API key required — uses Hudson Rock's free OSINT endpoint.
- Watches for `DOMAIN_NAME`, `INTERNET_NAME`, `EMAILADDR`, `USERNAME`, and `PHONE_NUMBER` events.
- Can be run from the web UI or CLI:
  ```sh
  python sf.py -s example.com -t DOMAIN_NAME -m sfp_hudsonrock
  python sf.py -s user@example.com -t EMAILADDR -m sfp_hudsonrock
  ```

## Watched Events

| Event Type | Cavalier API Endpoint |
|---|---|
| `DOMAIN_NAME` / `INTERNET_NAME` | `search-by-domain` |
| `EMAILADDR` | `search-by-email` |
| `USERNAME` | `search-by-username` |
| `PHONE_NUMBER` | `search-by-username` |

## Produced Events

| Event Type | Description |
|---|---|
| `RAW_RIR_DATA` | Domain-level summary (total compromised, employees/users/third-parties, stealer families, password strength stats) and individual stealer machine records |
| `EMAILADDR_COMPROMISED` | Email found associated with infostealer-compromised machine |
| `PHONE_NUMBER_COMPROMISED` | Phone number found associated with infostealer-compromised machine |
| `MALICIOUS_INTERNET_NAME` | Domain with employee credentials compromised by infostealers |

## Output Example (Domain)

```
Hudson Rock Infostealer Intelligence for example.com
Total compromised credentials: 1247
Employees: 89 | Users: 1102 | Third-parties: 56
Top stealer families: RedLine: 412, Lumma: 298, Raccoon: 187, Vidar: 95
Employee passwords: 89 total, 48.8% weak, 29.2% strong
User passwords: 1102 total, 67.0% weak, 20.7% strong
```

## Output Example (Email)

```
user@example.com [Hudson Rock - Infostealer]
Hudson Rock [user@example.com]: Date: 2026-01-15T10:00:00.000Z | Host: DESKTOP-ABC | OS: Windows 11 | Stealer: Lumma | Malware: C:\Users\test\malware.exe | IP: 192.168.1.1 | AV: Windows Defender
```

## Options

| Option | Default | Description |
|---|---|---|
| `delay` | `1` | Delay in seconds between API requests to avoid rate-limiting |
| `max_stealers` | `50` | Maximum number of stealer records to process per query (0 = unlimited) |

## API Keys Required

- **None** — Hudson Rock's Cavalier OSINT API is free and requires no authentication.

## Tips

- Combine with `sfp_haveibeenpwned` and `sfp_leakcheck` for comprehensive breach/leak coverage.
- Use domain queries to assess organizational exposure to infostealer campaigns.
- Employee credential compromise findings can indicate active risk of account takeover.
- Stealer family data helps identify which malware campaigns targeted an organization.

## References

- [Hudson Rock Free Tools](https://www.hudsonrock.com/free-tools)
- [Cavalier API Documentation](https://cavalier.hudsonrock.com/docs)
- [GitHub Issue #324](https://github.com/poppopjmp/spiderfoot/issues/324)

---

*Module added in response to [Issue #324](https://github.com/poppopjmp/spiderfoot/issues/324) — Hudson Rock Infostealer Intelligence Integration.*
