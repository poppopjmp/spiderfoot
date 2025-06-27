# sfp_dnsbrute

**Purpose:**
Performs DNS brute-forcing to discover subdomains and hidden infrastructure related to the target domain. Useful for attack surface mapping and asset discovery.

**Category:** Reconnaissance / Asset Discovery

---

## Usage

- Enabled for domain targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsbrute
```

## Output Example

```pre
Domain: example.com
Subdomains Found: dev.example.com, mail.example.com, vpn.example.com
```

## API Keys Required

None

## Tips

- Use to uncover hidden or forgotten subdomains.
- Combine with sfp_dnsresolve and sfp_dnsdumpster for comprehensive mapping.

---

Authored by poppopjmp
