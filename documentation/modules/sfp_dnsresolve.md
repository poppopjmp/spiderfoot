# sfp_dnsresolve

**Purpose:**
Resolves DNS records for the target domain or host, including A, AAAA, MX, NS, TXT, and CNAME records. Used for asset discovery, infrastructure mapping, and identifying related services.

**Category:** Data Gathering

---

## Usage
- Enabled by default for domain and hostname targets.
- Can be run from the web UI or CLI:
  ```sh
  python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve
  ```

## Output Example
```
A record: 93.184.216.34
MX record: mail.example.com
NS record: ns1.example.com
TXT record: v=spf1 include:_spf.example.com ~all
```

## API Keys Required
None

## Tips
- Combine with other modules (e.g., sfp_ssl, sfp_whois) for deeper asset mapping.
- Useful for identifying mail servers, SPF/DKIM records, and infrastructure relationships.

---

*Authored by poppopjmp*
