# sfp_arin

**Purpose:**
Queries ARIN for network, ASN, and contact information related to the target IP or ASN. Useful for infrastructure mapping and attribution.

**Category:** Infrastructure Mapping / Attribution

---

## Usage

- Enabled for IP and ASN targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s 8.8.8.8 -t IP_ADDRESS -m sfp_arin
```

## Output Example

```pre
IP: 8.8.8.8
ASN: AS15169 (Google LLC)
Org: Google LLC
Contact: admin@google.com
```

## API Keys Required

None

## Tips

- Use to map network ownership and attribution.
- Combine with sfp_ipinfo and sfp_whois for full context.

---

Authored by poppopjmp
