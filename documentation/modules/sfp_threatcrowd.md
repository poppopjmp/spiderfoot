# sfp_threatcrowd

**Purpose:**
Queries the ThreatCrowd API for information about domains, IPs, and emails, including related infrastructure and threat intelligence. Useful for mapping relationships and identifying malicious assets.

**Category:** Threat Intelligence / Infrastructure Mapping

---

## Usage

- Enabled for domain, IP, and email targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_threatcrowd
```

## Output Example

```pre
Domain: example.com
Related IPs: 1.2.3.4, 5.6.7.8
Related Domains: badsite.com, evil.com
Malicious: Yes
```

## API Keys Required

None

## Tips

- Use to uncover infrastructure relationships and threat actor activity.
- Combine with sfp_virustotal and sfp_shodan for deeper context.

---

*Authored by poppopjmp*
