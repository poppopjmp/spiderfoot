# sfp_dnsdumpster

**Purpose:**
Queries DNSDumpster for passive DNS and subdomain enumeration related to the target domain. Useful for asset discovery and attack surface mapping.

**Category:** Reconnaissance / Asset Discovery

---

## Usage

- Enabled for domain targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsdumpster
```

## Output Example

```pre
Domain: example.com
Subdomains Found: mail.example.com, dev.example.com
IP Addresses: 93.184.216.34, 93.184.216.35
```

## API Keys Required

None

## Tips

- Use to enumerate subdomains and related infrastructure.
- Combine with sfp_dnsresolve and sfp_shodan for full mapping.

---

Authored by poppopjmp
