# sfp_ssl

**Purpose:**
Analyzes SSL/TLS certificates for the target host, extracting certificate details, issuer, validity, and subject alternative names. Useful for identifying related domains, certificate misconfigurations, and expired certificates.

**Category:** Data Gathering / Security Analysis

---

## Usage
- Enabled by default for domain and hostname targets supporting HTTPS.
- Can be run from the web UI or CLI:
  ```sh
  python sf.py -s example.com -t DOMAIN_NAME -m sfp_ssl
  ```

## Output Example
```
Certificate Subject: CN=example.com
Issuer: Let's Encrypt Authority X3
Valid From: 2025-01-01
Valid To: 2025-04-01
Subject Alt Names: example.com, www.example.com
```

## API Keys Required
None

## Tips
- Use to detect expired or soon-to-expire certificates.
- Helps identify all domains covered by a certificate (SANs).
- Combine with sfp_dnsresolve for full asset mapping.

---

*Authored by poppopjmp*
